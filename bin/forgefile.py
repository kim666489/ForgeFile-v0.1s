import os
import sys
import json
from Mono_py10 import Lexer, Normalizer, load_rule, create_rule_template
import traceback
import re
import ast

dir_path = os.path.dirname(os.path.abspath(__file__))
running_path = os.getcwd()
forgefile_path = os.path.dirname(dir_path)
config_path = os.path.join(forgefile_path, "config", "config.json")
debug = False
debug_ir = False

SAFE_BUILTINS = { # Don't fix.
    "abs": abs, "min": min, "max": max, "len": len,
    "int": int, "float": float, "str": str, "bool": bool,
    "round": round, "sum": sum,
}

# ── security config (loaded from ../config/config.json) ─────────────────
DEFAULT_SECURITY_CONFIG = {
    "require_confirmation": True,
    "auto_approve_env": "FORGEFILE_YES",
    "dangerous_patterns": [],
}

def load_security_config(path):
    """
    โหลดการตั้งค่าด้าน security จาก config.json
    ถ้าไฟล์หาไม่เจอหรือ parse ไม่ได้ ให้ fallback เป็นค่า default (ปลอดภัยไว้ก่อน)
    และแจ้งเตือนผู้ใช้ให้รู้ตัวว่ากำลังใช้ default อยู่
    """
    if not os.path.exists(path):
        print(f"[WARN] Security config not found at {path}, using built-in defaults.")
        return dict(DEFAULT_SECURITY_CONFIG)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        sec = data.get("security", {})
        merged = {**DEFAULT_SECURITY_CONFIG, **sec}
        # compile ล่วงหน้าเพื่อความเร็ว + เช็คว่า regex ใช้ได้จริง
        compiled = []
        for pat in merged.get("dangerous_patterns", []):
            try:
                compiled.append(re.compile(pat, re.IGNORECASE))
            except re.error as e:
                print(f"[WARN] Skipping invalid dangerous_pattern {pat!r}: {e}")
        merged["_compiled_patterns"] = compiled
        return merged
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARN] Failed to load {path} ({e}), using built-in defaults.")
        return dict(DEFAULT_SECURITY_CONFIG)


SECURITY_CONFIG = load_security_config(config_path)


def is_dangerous_command(command):
    """คืน compiled pattern ตัวแรกที่ match ถ้าคำสั่งเข้าข่ายอันตราย ไม่งั้นคืน None"""
    for pattern in SECURITY_CONFIG.get("_compiled_patterns", []):
        if pattern.search(command):
            return pattern.pattern
    return None


def confirm_dangerous_command(command, matched_pattern):
    """
    ถามยืนยันก่อนรันคำสั่งอันตราย
    ข้ามการถามได้ถ้า:
      - require_confirmation = false ใน config
      - env var (ชื่อตาม auto_approve_env) ถูกตั้งเป็น "1"/"true"
      - ผู้ใช้ส่ง --yes / -y ตอนเรียก forgefile
    คืน True ถ้าอนุญาตให้รัน, False ถ้าปฏิเสธ
    """
    if not SECURITY_CONFIG.get("require_confirmation", True):
        return True

    env_name = SECURITY_CONFIG.get("auto_approve_env", "FORGEFILE_YES")
    if os.environ.get(env_name, "").lower() in ("1", "true", "yes"):
        return True

    if "--yes" in sys.argv or "-y" in sys.argv:
        return True

    print("\n[PERMISSION REQUIRED]")
    print(f"  Command : {command}")
    print(f"  Matched : looks like a potentially destructive pattern ({matched_pattern})")
    try:
        answer = input("  Run this command anyway? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        # ไม่มี interactive input ให้ใช้ได้ (เช่นรันใน CI แบบไม่มี tty) -> ปฏิเสธไว้ก่อนเพื่อความปลอดภัย
        print("\n[DENIED] No interactive input available; refusing by default.")
        return False

    return answer in ("y", "yes")


class ForgeFile:
    def __init__(self,_args):
        self.variable = {}
        self.args = _args[1:]
        self.ir = []
        self.pc = 0
        self.mapping_function = {
            "shell_cmd":self.shell_cmd,
            "create_func":self.create_func,
            "call_func":self.call_func,
            "run_python":self.run_python,
            "let_cmd":self.let_cmd,
            "evel_cmd":self.evel_cmd,
            "not_let_cmd":self.not_let_cmd,
            "if_statement":self.if_statement,
        }
        self.func = {}

    def calc(self, text):
        # 1. ตรวจโครงสร้างนิพจน์ก่อน ว่าเป็นแค่ expression ปกติ ไม่มีการเรียก
        #    คำสั่งอันตราย เช่น import, exec, attribute แปลกๆ
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError as e:
            raise Exception(f"Invalid expression: {e}")

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                raise Exception("Import is not allowed in expression.")
            if isinstance(node, ast.Attribute):
                # กัน __class__, __globals__, __builtins__ ฯลฯ (dunder attribute access)
                if node.attr.startswith("__"):
                    raise Exception("Access to dunder attributes is not allowed.")
            if isinstance(node, ast.Name):
                if node.id.startswith("__"):
                    raise Exception("Access to dunder names is not allowed.")

        # 2. eval โดยตัด __builtins__ เริ่มต้นของ python ทิ้ง แล้วให้ใช้แค่ whitelist เอง
        safe_globals = {"__builtins__": SAFE_BUILTINS}
        return eval(compile(tree, "<calc>", "eval"), safe_globals, self.variable)

    def calc_var_eval(self, text, for_shell=False):
        def repl(m):
            name = m.group(1)
            if name in self.variable:
                value = self.variable[name]
                if for_shell:
                    # ใช้ค่าดิบ ไม่ครอบ quote ไม่ escape backslash
                    return str(value)
                return repr(value)
            return m.group(0)
        return re.sub(r'\$\$(\w+)', repl, text)
        
    def if_statement(self,data):
        value = self.calc_var_eval(data[0]["value"])
        code = data[1]
        yes_no = self.calc(value)
        if yes_no:
            ff = ForgeFile(self.args)
            ff.variable = self.variable
            ff.func = self.func
            ff.ir = code
            ff.running_ir()
            self.variable = ff.variable

    def evel_cmd(self,data):
        if len(data) < 2:
            raise Exception("Bad variable")
        self.variable[data[0]["value"]] = self.calc(data[1]["value"])

    def let_cmd(self,data):
        if len(data) < 2:
            raise Exception("Bad variable")
        self.variable[data[0]["value"]] = self.calc_var_eval(data[1]["value"])

    def not_let_cmd(self,data):
        if len(data) < 2:
            raise Exception("Bad variable")
        if not data[0]["value"] in self.variable:
            self.variable[data[0]["value"]] = self.calc_var_eval(data[1]["value"])

    def run_python(self,data):
        exec(data[0]["value"],self.variable)

    def create_func(self,data):
        if len(data) < 2:
            raise Exception("Bad create Function.")
        func_name = data[0]["value"]
        self.func[func_name] = {"code":data[1]}

    def call_func(self,data):
        if len(data) == 0:
            raise Exception("bad call function.")
        func_name = data[0]["value"]
        
        if not func_name in self.func:
            raise Exception(f"Not {func_name} in function list.")
        _function = self.func[func_name]

        ff = ForgeFile(self.args)
        ff.variable = self.variable
        ff.ir = _function["code"]
        ff.running_ir()
        self.variable = ff.variable

    def shell_cmd(self, data):
        raw_command = data[0]["value"]

        # ใช้ for_shell=True เพื่อไม่ให้ repr() ใส่ quote/escape มาปนกับคำสั่ง
        processed_command = self.calc_var_eval(raw_command, for_shell=True)
        print(processed_command)

        matched = is_dangerous_command(processed_command)
        if matched is not None:
            if not confirm_dangerous_command(processed_command, matched):
                print("[SKIPPED] Command was not confirmed, skipping.")
                return

        parse = processed_command.split(" ")

        if parse[0].strip() in ["try", "_try"]:
            try:
                final_cmd = " ".join(parse[1:])
                os.system(final_cmd)
            except Exception as e:
                print(f"[TRY] {e}")
        else:
            os.system(processed_command)

    def set_variable_cmd(self,_args):
        for cmd in _args:
            parse = cmd.split("=")
            if len(parse) < 2:
                continue
            self.variable[parse[0]] = parse[1]

    def look(self):
        if self.pc < len(self.ir):
            return self.ir[self.pc]
        return None
    
    def next(self,k=1):
        if self.pc+k <= len(self.ir):
            self.pc += k

    def peek(self,k=1):
        if self.pc+k < len(self.ir):
            return self.ir[self.pc+k]
        return None

    def running_ir(self):
        while self.look() != None:
            try:
                node = self.look()
                if node["action"] in self.mapping_function:
                    func = self.mapping_function[node["action"]]
                    func(node["data"])
            except Exception as e:
                print(f"[ERROR] {e} in {node['line']+1}:{node['col']+1}")
                sys.exit(1)
                if debug:
                    traceback.print_exc()
            self.next()

    def running_cmd(self):
        if len(self.args) < 1:
            sys.exit()
        func_args = [a for a in self.args if len(a.split("=")) <= 1 and a not in ("--yes", "-y")]

        if len(func_args) < 1:
            sys.exit()

        func_name = func_args[0]

        if not func_name in self.func:
            print(f"[ERROR] Not {func_name} in function.")
            sys.exit(1)

        _function = self.func[func_name]
        ff = ForgeFile(self.args)
        ff.variable = self.variable
        ff.ir = _function["code"]
        ff.func = self.func
        ff.running_ir()
        ff.running_cmd()
        self.variable = ff.variable

    def parser_run(self):
        load_rule(os.path.join(forgefile_path,"ForgeFileRule.json"))
        program_path = os.path.join(running_path,"forgefile")
        if not os.path.exists(program_path):
            print("[ERROR] Not forgefile in folder.")
            sys.exit(1)
        try:
            with open(program_path,"r",encoding="utf-8") as f:
                program = f.read()
            tokens = Lexer(program).run()
            ir = Normalizer(tokens).parse()
            if debug_ir:
                print(ir)
            self.ir = ir

        except Exception as e:
            print(f"[ERROR] {e}")
            if debug:
                traceback.print_exception()
            sys.exit(1)

if __name__ == "__main__":
    args = sys.argv
    if debug:
        print(f"[CONFIG] ForgeFile in {forgefile_path}")
        print(f"[CONFIG] Running in {running_path}")
        os.system(f"ls {running_path}")
    try:
        forgefile = ForgeFile(args)
        forgefile.parser_run()
        forgefile.set_variable_cmd(args)
        forgefile.running_ir()
        forgefile.running_cmd()
    except KeyboardInterrupt:
        print("[ForgeFile] stoped.")
        sys.exit(1)