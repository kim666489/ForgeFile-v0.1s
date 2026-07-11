import json
import os

# ─────────────────────────────────────────────
#  DEFAULT GRAMMAR  (embedded fallback)
# ─────────────────────────────────────────────

DEFAULT_GRAMMAR = {
  "_config": {
    "line_terminator": ";",
    "stmt_separator": ",",
    "tab_size": 4,
    "keep_newline": False
  },
  "rules": {
    "INT":    {"collect": {"ASSIGN": {"collectint":    {"end": [";", "LetInt_Cmd"]}}}},
    "STRING": {"collect": {"ASSIGN": {"collectstring": {"end": [";", "LetString_Cmd"]}}}},
    "FLOAT":  {"collect": {"ASSIGN": {"collectfloat":  {"end": [";", "LetFloat_Cmd"]}}}},
    "DOUBLE": {"collect": {"ASSIGN": {"collectdouble": {"end": [";", "LetDouble_Cmd"]}}}},
    "CHAR":   {"collect": {"ASSIGN": {"collectchar":   {"end": [";", "LetChar_Cmd"]}}}},
    "BOOL":   {"collect": {"ASSIGN": {"collectbool":   {"end": [";", "LetBool_Cmd"]}}}},
    "AUTO":   {"collect": {"ASSIGN": {"collectauto":   {"end": [";", "LetAuto_Cmd"]}}}},
    "IDENTIFIER":  {"ASSIGN":  {"collectexpr":         {"end": [";", "Assign_Cmd"]}}}
  }
}

rule_data_template = {
    "_config": {
        "line_terminator": ";",
        "stmt_separator": "/",
        "tab_size": 4,
        "keep_newline": False
    },
    # ── error policy ──────────────────────────────────────────────────────
    # กำหนดว่าแต่ละประเภท error จะ exit (หยุด) หรือ warn (พิมพ์ warning แล้วข้ามต่อ)
    "_error_policy": {
        "unknown_token":      "exit",   # token ที่ lexer ไม่รู้จัก
        "type_error":         "exit",   # token ผิดประเภทใน collect
        "unclosed_bracket":   "exit",   # วงเล็บไม่ปิด
        "unclosed_string":    "exit",   # string literal ไม่ปิด
        "invalid_char":       "exit",   # char literal ผิด format
        "unknown_operator":   "warn",   # operator ไม่รู้จัก
        "rule_not_matched":   "warn",   # token ไม่ match rule ใดเลย
        "schema_violation":   "exit"    # rule.json ผิด schema
    },
    "rules": {},
    "lexer": {
        "keyword": {},
        "operator": {
            "+": "PLUS",  "-": "MINUS", "*": "MUL",  "/": "DIV",
            "=": "ASSIGN","==":"EQ",    "!=":"NEQ",
            ">": "GT",    "<": "LT",   ">=":"GTE",   "<=":"LTE"
        },
        "symbol": {
            "(": "LPAREN",  ")": "RPAREN",
            "{": "LBRACE",  "}": "RBRACE",
            "[": "LBRACKET","]": "RBRACKET",
            ";": "SEMICOLON", ",": "COMMA",
            ":": "COLON"
        }
    },
    "normalizer": {
        # ── collect_types ─────────────────────────────────────────────────
        # กำหนด token type ที่อนุญาตในแต่ละ collect mode
        # null = รับทุกอย่าง (no filter)
        "collect_types": {
            "collectint":    ["INT"],
            "collectfloat":  ["FLOAT", "INT"],
            "collectdouble": ["FLOAT", "INT"],
            "collectstring": ["STRING"],
            "collectchar":   ["CHAR"],
            "collectbool":   ["BOOL"],
            "collectauto":   ["INT","FLOAT","STRING","CHAR","BOOL","IDENTIFIER",
                            "LBRACKET","RBRACKET","LBRACE","RBRACE","COMMA","COLON"],
            "collectexpr":   ["INT","FLOAT","STRING","CHAR","BOOL","IDENTIFIER",
                            "PLUS","MINUS","MUL","DIV","LPAREN","RPAREN",
                            "EQ","NEQ","GT","LT","GTE","LTE"],
            "collectlist":   ["INT","FLOAT","STRING","CHAR","BOOL","IDENTIFIER",
                            "COMMA","LBRACKET","RBRACKET"],
            "collectmap":    ["INT","FLOAT","STRING","CHAR","BOOL","IDENTIFIER","COMMA","COLON","LBRACE","RBRACE","LBRACKET","RBRACKET"],
            "collectcode":   None,
            "collect":       None,
            "collectfunc":   ["INT","FLOAT","STRING","CHAR","BOOL","IDENTIFIER","COMMA","LPAREN","RPAREN"]
        },

        # ── collect_brackets ──────────────────────────────────────────────
        # กำหนด bracket เปิด/ปิดของแต่ละ collect mode
        # รองรับได้ทั้ง token type (เช่น "LBRACKET") และ custom char (เช่น "#")
        #
        # รูปแบบขยาย (object):
        #   "open":  token_type หรือ {"char": "#", "token": "HASH_OPEN"}
        #   "close": token_type หรือ {"char": "#", "token": "HASH_CLOSE"}
        #   "same":  true  → ใช้ตัวเดียวกันเป็นทั้ง open และ close (เช่น ## ... ##)
        #
        # รูปแบบย่อ (array [open, close]):
        #   ["LBRACKET", "RBRACKET"]  → เหมือนเดิม backward compatible
        "collect_brackets": {
            "collectlist": ["LBRACKET", "RBRACKET"],
            "collectfunc": ["LPAREN",   "RPAREN"],
            "collectmap":  ["LBRACE",   "RBRACE"],
            "collectcode": ["LBRACE",   "RBRACE"],
            "collectexpr": None
        },

        # ── collect_delimiters ────────────────────────────────────────────
        # กำหนด delimiter สำหรับแยก element ใน list และ key:value ใน map
        # สามารถกำหนดแยกต่อหาก collect mode ได้
        #
        # item_sep   = ตัวคั่นระหว่าง element (default "COMMA")
        # kv_sep     = ตัวคั่น key:value (default "COLON")  [ใช้ใน map เท่านั้น]
        # entry_sep  = ตัวคั่นระหว่าง entry ใน map (default เหมือน item_sep)
        "collect_delimiters": {
            "collectlist": {
                "item_sep": "COMMA"
            },
            "collectmap": {
                "item_sep": "COMMA",
                "kv_sep":   "COLON"
            },
            "collectfunc": {
                "item_sep": "COMMA"
            }
        },

        # ── collect_string_modes ──────────────────────────────────────────
        # กำหนด string literal แบบ custom
        # แต่ละ entry คือ collect mode ที่ใช้ string style พิเศษ
        #
        # open / close: char ที่ใช้ครอบ string (ถ้า same=true ใช้อันเดียวกัน)
        # token:        ชื่อ token type ที่จะ emit
        # multichar:    true = open/close อาจเป็นมากกว่า 1 ตัวอักษร (เช่น "##")
        # escape:       map ของ escape sequence (null = ไม่มี escape)
        "collect_string_modes": {
            # ตัวอย่าง: string ที่ใช้ ## แทน ""
            # "collectrawstr": {
            #     "open":      "##",
            #     "close":     "##",
            #     "token":     "RAWSTRING",
            #     "multichar": true,
            #     "escape":    null
            # }
        },

        # ── collect_expr_mode ─────────────────────────────────────────────
        # collect mode ที่ใช้ expression parser (รองรับ operator, parentheses)
        "collect_expr_mode": [
            "collectint", "collectfloat", "collectdouble",
            "collectstring", "collectchar", "collectbool",
            "collectauto", "collectexpr"
        ]
    }
}

# ─────────────────────────────────────────────
#  RUNTIME STATE  (โหลดจาก rule.json)
# ─────────────────────────────────────────────

COLLECT_TYPES    = {}
COLLECT_BRACKETS = {}
COLLECT_DELIMITERS = {}
COLLECT_EXPR_MODE  = set()
CUSTOM_STRING_MODES = {}   # ← mode ที่ใช้ string literal พิเศษ
ERROR_POLICY = {}          # ← policy ของแต่ละ error type
grammar_path = "./rule.json"
lexer_rule   = None

# ── default builtin ───────────────────────────────────────────────────────
_BUILTIN_COLLECT_TYPES = {
    "collectint":    {"INT"},
    "collectfloat":  {"FLOAT", "INT"},
    "collectdouble": {"FLOAT", "INT"},
    "collectstring": {"STRING"},
    "collectchar":   {"CHAR"},
    "collectbool":   {"BOOL"},
    "collectauto":   {"INT","FLOAT","STRING","CHAR","BOOL","IDENTIFIER",
                      "LBRACKET","RBRACKET","LBRACE","RBRACE","COMMA","COLON"},
    "collectexpr":   {"INT","FLOAT","STRING","CHAR","BOOL","IDENTIFIER",
                      "PLUS","MINUS","MUL","DIV","LPAREN","RPAREN",
                      "EQ","NEQ","GT","LT","GTE","LTE"},
    "collectlist":   {"INT","FLOAT","STRING","CHAR","BOOL","IDENTIFIER",
                      "COMMA","LBRACKET","RBRACKET"},
    "collectmap":    {"INT","FLOAT","STRING","CHAR","BOOL","IDENTIFIER",
                      "COMMA","COLON","LBRACE","RBRACE","LBRACKET","RBRACKET"},
    "collectcode":   None,
    "collect":       None,
    "collectfunc": {"INT","FLOAT","STRING","CHAR","BOOL","IDENTIFIER","COMMA","LPAREN","RPAREN"},
}

_BUILTIN_COLLECT_BRACKETS = {
    "collectlist":   ("LBRACKET", "RBRACKET"),
    "collectfunc":   ("LPAREN", "RPAREN"),
    "collectmap":    ("LBRACE",   "RBRACE"),
    "collectcode":   ("LBRACE",   "RBRACE"),
    "collectexpr":   None,
}

_BUILTIN_COLLECT_DELIMITERS = {
    "collectlist": {"item_sep": "COMMA"},
    "collectmap":  {"item_sep": "COMMA", "kv_sep": "COLON"},
    "collectfunc": {"item_sep": "COMMA"},
}

_BUILTIN_COLLECT_EXPR_MODE = {
    "collectint", "collectfloat", "collectdouble",
    "collectstring", "collectchar", "collectbool",
    "collectauto", "collectexpr",
}

_DEFAULT_ERROR_POLICY = {
    "unknown_token":    "exit",
    "type_error":       "exit",
    "unclosed_bracket": "exit",
    "unclosed_string":  "exit",
    "invalid_char":     "exit",
    "unknown_operator": "warn",
    "rule_not_matched": "warn",
    "schema_violation": "exit",
}

# ── helper: แปลง collect_brackets entry ────────────────────────────────

def _parse_bracket_entry(entry):
    """
    แปลง entry ใน collect_brackets ให้เป็น tuple (open_spec, close_spec)
    open_spec / close_spec คือ:
      - str   → token type เดิม (backward compat)
      - dict  → {"char": ..., "token": ...}  custom char bracket
      - None  → ไม่มี bracket
    """
    if entry is None:
        return None

    # รูปแบบ array  ["LBRACKET", "RBRACKET"]
    if isinstance(entry, list):
        if len(entry) != 2:
            raise ValueError(f"collect_brackets array must have exactly 2 elements, got {entry!r}")
        return (entry[0], entry[1])

    # รูปแบบ object ขยาย
    if isinstance(entry, dict):
        same = entry.get("same", False)
        open_spec  = entry.get("open")
        close_spec = entry.get("close") if not same else open_spec
        return (open_spec, close_spec)

    raise TypeError(f"Invalid collect_brackets entry: {entry!r}")


# ── validate rule.json schema ────────────────────────────────────────────

_SCHEMA_REQUIRED_KEYS = ["_config", "rules", "lexer", "normalizer"]

def _validate_schema(rule_data, policy):
    errors = []
    for key in _SCHEMA_REQUIRED_KEYS:
        if key not in rule_data:
            errors.append(f"Missing required key: '{key}'")

    norm = rule_data.get("normalizer", {})
    for sub in ["collect_types", "collect_brackets", "collect_expr_mode"]:
        if sub not in norm:
            errors.append(f"normalizer missing key: '{sub}'")

    if errors:
        msg = "[SchemaError] rule.json has schema violations:\n" + \
              "\n".join(f"  • {e}" for e in errors)
        _handle_error("schema_violation", msg, policy)


# ── error handler ────────────────────────────────────────────────────────

def _handle_error(error_type, message, policy=None):
    if policy is None:
        policy = ERROR_POLICY or _DEFAULT_ERROR_POLICY
    action = policy.get(error_type, "exit")
    if action == "exit":
        raise RuntimeError(message)
    else:
        print(f"[Warning] {message}")


# ── load_rule ────────────────────────────────────────────────────────────

def load_rule(path="./rule.json"):
    global lexer_rule, COLLECT_TYPES, COLLECT_BRACKETS, COLLECT_DELIMITERS
    global COLLECT_EXPR_MODE, CUSTOM_STRING_MODES, ERROR_POLICY, grammar_path

    with open(path, "r", encoding="utf-8") as f:
        rule_data = json.load(f)

    # โหลด error policy ก่อน เพราะจะใช้ใน validate
    raw_policy = rule_data.get("_error_policy", {})
    ERROR_POLICY = {**_DEFAULT_ERROR_POLICY, **raw_policy}

    # validate schema
    _validate_schema(rule_data, ERROR_POLICY)

    lexer_rule   = rule_data["lexer"]
    norm         = rule_data["normalizer"]
    grammar_path = path

    # ── collect_types: แปลง list → set, รองรับ null ──────────────────────
    raw_ct = norm.get("collect_types", {})
    COLLECT_TYPES = {}
    for mode, types in raw_ct.items():
        COLLECT_TYPES[mode] = set(types) if types is not None else None

    # ── collect_brackets: แปลงทุก entry ──────────────────────────────────
    raw_cb = norm.get("collect_brackets", {})
    COLLECT_BRACKETS = {}
    for mode, entry in raw_cb.items():
        COLLECT_BRACKETS[mode] = _parse_bracket_entry(entry)

    # ── collect_delimiters (optional) ─────────────────────────────────────
    raw_cd = norm.get("collect_delimiters", {})
    # merge กับ builtin default
    COLLECT_DELIMITERS = {**_BUILTIN_COLLECT_DELIMITERS}
    for mode, conf in raw_cd.items():
        COLLECT_DELIMITERS[mode] = {
            **_BUILTIN_COLLECT_DELIMITERS.get(mode, {}),
            **conf
        }

    # ── collect_string_modes (optional) ───────────────────────────────────
    CUSTOM_STRING_MODES = norm.get("collect_string_modes", {}) or {}

    # ── collect_expr_mode ─────────────────────────────────────────────────
    expr_list = norm.get("collect_expr_mode", [])
    COLLECT_EXPR_MODE = set(expr_list) if isinstance(expr_list, list) else set()


def create_rule_template(rule_name):
    with open(f"./{rule_name}.json", "w", encoding="utf-8") as f:
        json.dump(rule_data_template, f, indent=4, ensure_ascii=False)
    print(f"[Info] Created {rule_name}.json")
    print("[Warning] If you have a JSON file with the same name, please be careful not to overwrite the data.")


# ─────────────────────────────────────────────
#  TOKEN
# ─────────────────────────────────────────────

class Token:
    def __init__(self, type_, value, pos, line=0, col=0, tab=0):
        self.type  = type_
        self.value = value
        self.pos   = pos
        self.line  = line
        self.col   = col
        self.tab   = tab

    def __repr__(self):
        return f"{self.type}:{self.value!r}(L{self.line},C{self.col},tab={self.tab})"


# ─────────────────────────────────────────────
#  LEXER
# ─────────────────────────────────────────────

class Lexer:
    def __init__(self, code, tab_size=4):
        self.code     = code
        self.pos      = 0
        self.line     = 0
        self.col      = 0
        self.tab_size = tab_size

        self.current_char = code[0] if code else None
        self.buffer       = ""
        self.tokens       = []
        self._line_tab    = 0

        self.KEYWORDS  = lexer_rule["keyword"]  if lexer_rule else {}
        self.OPERATORS = lexer_rule["operator"] if lexer_rule else {}
        self.SYMBOLS   = lexer_rule["symbol"]   if lexer_rule else {}

        # ── custom string literals ─────────────────────────────────────────
        # สร้าง lookup: open_char → mode_config
        self._custom_strings = {}
        for mode, cfg in CUSTOM_STRING_MODES.items():
            open_ch = cfg.get("open", "")
            if open_ch:
                self._custom_strings[open_ch] = {**cfg, "_mode": mode}

        # เรียงจากยาวสุดไปสั้นสุด (เพื่อ match multichar ก่อน)
        self._custom_string_openers = sorted(
            self._custom_strings.keys(), key=len, reverse=True
        )

        self.state = self.state_start
        self._calc_line_tab()

    def _calc_line_tab(self):
        p = self.pos
        spaces = 0
        while p < len(self.code) and self.code[p] in (' ', '\t'):
            spaces += self.tab_size if self.code[p] == '\t' else 1
            p += 1
        self._line_tab = spaces // self.tab_size

    def advance(self):
        if self.current_char == '\n':
            self.line += 1
            self.col   = 0
        else:
            self.col  += 1
        self.pos += 1
        if self.pos < len(self.code):
            self.current_char = self.code[self.pos]
            if self.col == 0:
                self._calc_line_tab()
        else:
            self.current_char = None

    def peek(self, offset=1):
        nxt = self.pos + offset
        return self.code[nxt] if nxt < len(self.code) else None

    def peek_str(self, length):
        """peek หลายตัวอักษร"""
        return self.code[self.pos: self.pos + length]

    def emit(self, type_, value):
        self.tokens.append(Token(type_, value, self.pos,
                                 self.line, self.col, self._line_tab))

    def run(self):
        while self.state:
            self.state()
        self.emit("EOF", None)
        return self.tokens

    # ── state_start: ตรวจ custom string openers ก่อน ──────────────────────

    def state_start(self):
        if self.current_char is None:
            self.state = None
            return
        if self.current_char == '\n':
            self.emit("NEWLINE", "\\n")
            self.advance()
            return
        if self.current_char in (' ', '\t', '\r'):
            self.advance()
            return

        self.buffer = ""

        # ── ลอง match custom string opener (multichar) ───────────────────
        for opener in self._custom_string_openers:
            if self.peek_str(len(opener)) == opener:
                cfg = self._custom_strings[opener]
                # กิน opener
                for _ in opener:
                    self.advance()
                self._state_custom_string = cfg
                self.state = self._state_custom_string_body
                return

        if self.current_char.isalpha() or self.current_char == "_":
            self.state = self.state_identifier
        elif self.current_char.isdigit():
            self.state = self.state_number
        elif self.current_char == '"':
            self.advance()
            self.state = self.state_string
        elif self.current_char == "'":
            self.advance()
            self.state = self.state_char
        elif self.current_char == "/":
            self.state = self.state_slash
        elif self.current_char in "+-*=!<>":
            self.state = self.state_operator
        elif self.current_char in self.SYMBOLS:
            self.state = self.state_symbol
        else:
            msg = f"Unknown char at line {self.line}, col {self.col}: {self.current_char!r}"
            _handle_error("unknown_token", msg)

    # ── custom string body ────────────────────────────────────────────────

    def _state_custom_string_body(self):
        """อ่าน custom string จนกว่าจะเจอ close sequence"""
        cfg      = self._state_custom_string
        close_ch = cfg.get("close", cfg.get("open", ""))
        token_t  = cfg.get("token", "STRING")
        escape   = cfg.get("escape")   # dict หรือ None

        while True:
            if self.current_char is None:
                msg = f"Unclosed custom string (opener={cfg.get('open')!r}) at line {self.line}"
                _handle_error("unclosed_string", msg)
                break

            # ตรวจ close sequence
            if self.peek_str(len(close_ch)) == close_ch:
                for _ in close_ch:
                    self.advance()
                self.emit(token_t, self.buffer)
                self.state = self.state_start
                return

            # escape
            if escape and self.current_char == "\\":
                self.advance()
                esc_val = escape.get(self.current_char, self.current_char)
                self.buffer += esc_val
                self.advance()
                continue

            self.buffer += self.current_char
            self.advance()

    def state_identifier(self):
        if self.current_char and (self.current_char.isalnum() or self.current_char == "_"):
            self.buffer += self.current_char
            self.advance()
        else:
            tok = self.KEYWORDS.get(self.buffer, "IDENTIFIER")
            self.emit(tok, self.buffer)
            self.state = self.state_start

    def state_number(self):
        has_dot = False
        has_exp = False
        while self.current_char:
            c = self.current_char
            if c.isdigit():
                self.buffer += c
            elif c == "." and not has_dot:
                has_dot = True; self.buffer += c
            elif c in "eE" and not has_exp:
                has_exp = True; self.buffer += c
                if self.peek() in "+-":
                    self.advance(); self.buffer += self.current_char
            else:
                break
            self.advance()
        if has_dot or has_exp:
            self.emit("FLOAT", float(self.buffer))
        else:
            self.emit("INT", int(self.buffer))
        self.state = self.state_start

    def state_string(self):
        if self.current_char is None:
            _handle_error("unclosed_string", f"Unclosed string at line {self.line}, col {self.col}")
            self.state = self.state_start
            return
        if self.current_char == '"':
            self.emit("STRING", self.buffer)
            self.advance()
            self.state = self.state_start
            return
        if self.current_char == "\\":
            self.advance()
            esc = {"n":"\n","t":"\t",'"':'"',"\\":"\\"}
            self.buffer += esc.get(self.current_char, self.current_char)
        else:
            self.buffer += self.current_char
        self.advance()

    def state_char(self):
        if self.current_char is None:
            _handle_error("unclosed_string", f"Unclosed char literal at line {self.line}, col {self.col}")
            self.state = self.state_start
            return
        value = self.current_char
        self.advance()
        if self.current_char != "'":
            _handle_error("invalid_char",
                f"Invalid char literal at line {self.line}, col {self.col} — expected closing \"'\"")
            self.state = self.state_start
            return
        self.advance()
        self.emit("CHAR", value)
        self.state = self.state_start

    def state_slash(self):
        if self.peek() == "/":
            self.advance(); self.advance()
            self.state = self.state_comment_line
        elif self.peek() == "*":
            self.advance(); self.advance()
            self.state = self.state_comment_block
        else:
            self.emit("DIV", "/")
            self.advance()
            self.state = self.state_start

    def state_comment_line(self):
        while self.current_char and self.current_char != "\n":
            self.advance()
        self.state = self.state_start

    def state_comment_block(self):
        while self.current_char:
            if self.current_char == "*" and self.peek() == "/":
                self.advance(); self.advance(); break
            self.advance()
        self.state = self.state_start

    def state_operator(self):
        op = self.current_char
        self.advance()
        if self.current_char == "=":
            op += "="; self.advance()
        tok = self.OPERATORS.get(op)
        if not tok:
            _handle_error("unknown_operator",
                f"Unknown operator {op!r} at line {self.line}, col {self.col}")
            self.state = self.state_start
            return
        self.emit(tok, op)
        self.state = self.state_start

    def state_symbol(self):
        sym = self.current_char
        self.advance()
        self.emit(self.SYMBOLS[sym], sym)
        self.state = self.state_start


# ─────────────────────────────────────────────
#  POSITION HELPERS
# ─────────────────────────────────────────────

def coerce_value(token):
    if token.type == "INT":   return int(token.value)
    if token.type == "FLOAT": return float(token.value)
    if token.type == "BOOL":  return token.value == "true"
    return token.value


def coerce_token(token):
    return {
        "value": coerce_value(token),
        "line":  token.line,
        "col":   token.col,
    }


# ─────────────────────────────────────────────
#  DELIMITER HELPERS
# ─────────────────────────────────────────────

def _get_item_sep(cmd_name):
    """คืน token type ของ item separator สำหรับ collect mode นี้"""
    return COLLECT_DELIMITERS.get(cmd_name, {}).get("item_sep", "COMMA")

def _get_kv_sep(cmd_name):
    """คืน token type ของ key-value separator สำหรับ collect mode นี้"""
    return COLLECT_DELIMITERS.get(cmd_name, {}).get("kv_sep", "COLON")


# ─────────────────────────────────────────────
#  PARSE LIST / MAP  (custom delimiter aware)
# ─────────────────────────────────────────────

def _parse_list_tokens(raw_tokens, open_type, close_type, item_sep="COMMA"):
    result  = []
    current = []
    depth   = 0

    for tok in raw_tokens:
        if tok.type == open_type:
            depth += 1
            current.append(tok)
        elif tok.type == close_type:
            depth -= 1
            if depth < 0:
                _handle_error("unclosed_bracket",
                    f"Unbalanced brackets in list at line {tok.line}, col {tok.col}")
                break
            current.append(tok)
        elif tok.type == item_sep and depth == 0:
            if current:
                result.append(_eval_token_seq(current, open_type, close_type, item_sep))
            current = []
        else:
            current.append(tok)

    if current:
        result.append(_eval_token_seq(current, open_type, close_type, item_sep))
    return result


def _eval_token_seq(tokens, open_type, close_type, item_sep="COMMA"):
    if not tokens:
        return None

    if tokens[0].type == open_type and tokens[-1].type == close_type:
        inner = tokens[1:-1]
        if open_type in ("LBRACKET",):
            return _parse_list_tokens(inner, open_type, close_type, item_sep)
        if open_type in ("LBRACE",):
            return _parse_map_tokens(inner, open_type, close_type)

    if len(tokens) == 1:
        return coerce_token(tokens[0])

    return [coerce_token(t) for t in tokens]


def _parse_map_tokens(raw_tokens, open_type="LBRACE", close_type="RBRACE",
                      item_sep="COMMA", kv_sep="COLON"):
    result     = {}
    depth      = 0
    key        = None
    val_tokens = []
    phase      = "key"

    for tok in raw_tokens:
        if tok.type in ("LBRACE", "LBRACKET"):
            depth += 1
            if phase == "val":
                val_tokens.append(tok)
        elif tok.type in ("RBRACE", "RBRACKET"):
            depth -= 1
            if phase == "val":
                val_tokens.append(tok)
        elif tok.type == kv_sep and depth == 0 and phase == "key":
            phase = "val"
        elif tok.type == item_sep and depth == 0:
            if key is not None:
                result[key] = _eval_token_seq(val_tokens, "LBRACE", "RBRACE")
            key = None; val_tokens = []; phase = "key"
        else:
            if phase == "key":
                key = coerce_value(tok)
            else:
                val_tokens.append(tok)

    if key is not None:
        result[key] = _eval_token_seq(val_tokens, "LBRACE", "RBRACE")
    return result


# ─────────────────────────────────────────────
#  NORMALIZER
# ─────────────────────────────────────────────

class Normalizer:
    def __init__(self, tokens):
        _raw_tokens = tokens
        self.pos  = 0
        self.ir   = []

        # ── โหลด grammar ──────────────────────
        script_dir = os.path.dirname(os.path.abspath(__file__)) \
                      if "__file__" in globals() else os.getcwd()
        _candidates = [grammar_path,
                       os.path.join(script_dir, grammar_path),
                       os.path.join(os.getcwd(), grammar_path)]
        grammar = None
        for _p in _candidates:
            if os.path.isfile(_p):
                with open(_p, "r", encoding="utf-8") as f:
                    grammar = json.load(f)
                break
        if grammar is None:
            grammar = DEFAULT_GRAMMAR

        cfg = grammar.get("_config", {})
        self.line_terminator = cfg.get("line_terminator", ";")
        self.tab_size        = cfg.get("tab_size", 4)
        self.rules           = grammar.get("rules", {})
        self.stmt_separator  = cfg.get("stmt_separator", None)
        self._sep_token_type = self._resolve_sep_type(self.stmt_separator)
        self._current_tab    = None

        # ── error policy ──────────────────────
        raw_policy = grammar.get("_error_policy", {})
        self._error_policy = {**_DEFAULT_ERROR_POLICY, **raw_policy}

        # ── กรอง token ────────────────────────
        keep_newline = cfg.get("keep_newline", False)
        _exclude = {"EOF"} if keep_newline else {"NEWLINE", "EOF"}
        self.tokens = [t for t in _raw_tokens if t.type not in _exclude] + \
                      [t for t in _raw_tokens if t.type == "EOF"]

    @staticmethod
    def _resolve_sep_type(sep_char):
        if sep_char is None:
            return None
        _SYMBOLS_REV = {
            ",": "COMMA", ";": "SEMICOLON", ":": "COLON",
            "(": "LPAREN", ")": "RPAREN",
            "{": "LBRACE", "}": "RBRACE",
            "[": "LBRACKET", "]": "RBRACKET",
        }
        return _SYMBOLS_REV.get(sep_char, None)

    def _err(self, error_type, message):
        _handle_error(error_type, message, self._error_policy)

    def peek(self, k=0):
        idx = self.pos + k
        return self.tokens[idx] if idx < len(self.tokens) else None

    def consume(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    @staticmethod
    def _loc(tok):
        if tok is None:
            return "end of input"
        return f"line {tok.line}, col {tok.col}"

    def _is_terminator(self, tok):
        if tok is None:
            return False
        if self.line_terminator == "NEWLINE":
            return tok.type == "NEWLINE"
        return tok.value == self.line_terminator

    def _is_separator(self, tok):
        if tok is None or self._sep_token_type is None:
            return False
        if self._sep_token_type == self.line_terminator:
            return False
        return tok.type == self._sep_token_type

    def _is_stmt_end(self, tok):
        return self._is_terminator(tok) or self._is_separator(tok)

    # ── _resolve_bracket: หา (open_type_str, close_type_str) ─────────────
    # รองรับทั้ง token-type string และ custom-char dict

    def _resolve_bracket_token_type(self, spec):
        """
        spec อาจเป็น str (token type) หรือ dict {"char": ..., "token": ...}
        คืน token type string เพื่อใช้ match กับ tok.type
        """
        if isinstance(spec, str):
            return spec
        if isinstance(spec, dict):
            return spec.get("token", "UNKNOWN")
        return str(spec)

    # ── collect with custom bracket ───────────────────────────────────────

    def _collect_until_close(self, open_spec, close_spec, allowed, cmd_name):
        open_type  = self._resolve_bracket_token_type(open_spec)
        close_type = self._resolve_bracket_token_type(close_spec)

        open_tok = self.peek()
        if open_tok is None or open_tok.type != open_type:
            self._err("unclosed_bracket",
                f"[SyntaxError] {cmd_name}: expected '{open_type}' "
                f"but got {open_tok!r} at {self._loc(open_tok)}")
            return []
        self.consume()

        depth      = 1
        is_map     = cmd_name in ("collectmap",)
        is_list    = cmd_name in ("collectlist",)
        raw_tokens = []

        item_sep = _get_item_sep(cmd_name)
        kv_sep   = _get_kv_sep(cmd_name)

        while True:
            tok = self.peek()
            if tok is None or tok.type == "EOF":
                self._err("unclosed_bracket",
                    f"[SyntaxError] {cmd_name}: unclosed '{open_type}' "
                    f"(opened at {self._loc(open_tok)}) — reached end of input")
                break
            if tok.type == open_type:
                depth += 1
                raw_tokens.append(self.consume())
            elif tok.type == close_type:
                depth -= 1
                if depth == 0:
                    self.consume()
                    break
                else:
                    raw_tokens.append(self.consume())
            else:
                if allowed is not None and tok.type not in allowed:
                    self._err("type_error",
                        f"[TypeError] {cmd_name}: unexpected token {tok.type!r} "
                        f"(value={tok.value!r}) at {self._loc(tok)}, "
                        f"allowed: {sorted(t for t in allowed)}")
                    self.consume()
                    continue
                raw_tokens.append(self.consume())

        if is_list:
            return _parse_list_tokens(raw_tokens, open_type, close_type, item_sep)
        elif is_map:
            return _parse_map_tokens(raw_tokens, open_type, close_type, item_sep, kv_sep)
        else:
            return [coerce_token(t) for t in raw_tokens]

    # ── collectcode ───────────────────────────────────────────────────────

    def _collect_code_block(self):
        bracket = COLLECT_BRACKETS.get("collectcode", ("LBRACE", "RBRACE"))
        if bracket is None:
            open_type, close_type = "LBRACE", "RBRACE"
        else:
            open_spec, close_spec = bracket
            open_type  = self._resolve_bracket_token_type(open_spec)
            close_type = self._resolve_bracket_token_type(close_spec)

        open_tok = self.peek()
        if open_tok is None or open_tok.type != open_type:
            self._err("unclosed_bracket",
                f"[SyntaxError] collectcode: expected '{open_type}' "
                f"but got {open_tok!r} at {self._loc(open_tok)}")
            return []
        self.consume()

        depth      = 1
        block_toks = []

        while True:
            tok = self.peek()
            if tok is None or tok.type == "EOF":
                self._err("unclosed_bracket",
                    f"[SyntaxError] collectcode: unclosed '{open_type}' "
                    f"(opened at {self._loc(open_tok)}) — reached end of input")
                break
            if tok.type == open_type:
                depth += 1
                block_toks.append(self.consume())
            elif tok.type == close_type:
                depth -= 1
                if depth == 0:
                    self.consume()
                    break
                else:
                    block_toks.append(self.consume())
            else:
                block_toks.append(self.consume())

        if block_toks:
            last = block_toks[-1]
            eof_sentinel = Token("EOF", None, last.pos + 1, last.line, last.col + 1, last.tab)
        else:
            eof_sentinel = Token("EOF", None, open_tok.pos + 1,
                                 open_tok.line, open_tok.col + 1, open_tok.tab)
        block_toks.append(eof_sentinel)

        sub = Normalizer.__new__(Normalizer)
        sub.tokens          = block_toks
        sub.pos             = 0
        sub.ir              = []
        sub.line_terminator = self.line_terminator
        sub.tab_size        = self.tab_size
        sub.rules           = self.rules
        sub.stmt_separator  = self.stmt_separator
        sub._sep_token_type = self._sep_token_type
        sub._current_tab    = None
        sub._error_policy   = self._error_policy

        return sub.parse()

    # ── _collect_expr ─────────────────────────────────────────────────────

    def _collect_expr(self, cmd_name):
        allowed          = COLLECT_TYPES.get(cmd_name)
        expr_passthrough = {"LPAREN","RPAREN","PLUS","MINUS","MUL","DIV",
                            "EQ","NEQ","GT","LT","GTE","LTE","COMMA"}
        data  = []
        depth = 0

        while True:
            tok = self.peek()
            if tok is None or tok.type == "EOF":
                break

            if depth == 0:
                if self._is_terminator(tok):
                    self.consume()
                    self._current_tab = None
                    break
                if self._is_separator(tok):
                    self.consume()
                    break

            if tok.type == "LPAREN":
                depth += 1
                data.append(coerce_token(self.consume()))
                continue

            if tok.type == "RPAREN":
                if depth == 0:
                    break
                depth -= 1
                data.append(coerce_token(self.consume()))
                continue

            if allowed is not None and tok.type not in allowed and tok.type not in expr_passthrough:
                self._err("type_error",
                    f"[TypeError] {cmd_name}: unexpected token {tok.type!r} "
                    f"(value={tok.value!r}) at {self._loc(tok)}, "
                    f"allowed: {sorted(allowed)}")
                self.consume()
                continue

            data.append(coerce_token(self.consume()))

        if depth != 0:
            self._err("unclosed_bracket",
                f"[SyntaxError] {cmd_name}: unbalanced parentheses "
                f"near {self._loc(self.peek())}")
        return data

    # ── _collect_simple ───────────────────────────────────────────────────

    def _collect_simple(self, cmd_name):
        allowed = COLLECT_TYPES.get(cmd_name)
        data    = []
        while True:
            tok = self.peek()
            if tok is None or tok.type == "EOF":
                break
            if self._is_terminator(tok):
                self.consume()
                self._current_tab = None
                break
            if self._is_separator(tok):
                self.consume()
                break
            if allowed is not None and tok.type not in allowed:
                self._err("type_error",
                    f"[TypeError] {cmd_name}: unexpected token {tok.type!r} "
                    f"(value={tok.value!r}) at {self._loc(tok)}, "
                    f"allowed: {sorted(allowed)}")
                self.consume()
                continue
            data.append(coerce_token(self.consume()))
        return data

    # ── _collect dispatcher ───────────────────────────────────────────────

    def _collect(self, cmd_name, tab):
        if cmd_name == "collectcode":
            return self._collect_code_block()

        if cmd_name in COLLECT_EXPR_MODE:
            return self._collect_expr(cmd_name)

        bracket = COLLECT_BRACKETS.get(cmd_name)
        if bracket is not None:
            open_spec, close_spec = bracket
            allowed = COLLECT_TYPES.get(cmd_name)
            return self._collect_until_close(open_spec, close_spec, allowed, cmd_name)

        return self._collect_simple(cmd_name)

    # ── rule walker ───────────────────────────────────────────────────────

    def _walk_rule(self, rule_node, tab, accumulated=None):
        if accumulated is None:
            accumulated = []

        # ── รองรับ "alternatives": [ {collect_mode: child}, … ] ──────────
        # ใช้เมื่อต้องการลองหลาย collect mode จาก token เดียวกัน
        if "alternatives" in rule_node:
            for alt in rule_node["alternatives"]:
                saved_pos = self.pos
                result = self._walk_rule(alt, tab, list(accumulated))
                if result is not None:
                    return result
                self.pos = saved_pos
            return None

        for key, child in rule_node.items():

            # ── "end" → emit action ──────────────────────────────────────
            if key == "end":
                action = child[1] if len(child) > 1 else "Unknown_Cmd"
                tok = self.peek()
                if tok and self._is_terminator(tok):
                    self.consume()
                    self._current_tab = None
                elif tok and self._is_separator(tok):
                    self.consume()
                return action, accumulated

            # ── "collect" → กิน token ถัดไป 1 ตัว ────────────────────────
            if key == "collect":
                tok = self.peek()
                if tok is None or tok.type == "EOF":
                    return None
                accumulated = accumulated + [coerce_token(self.consume())]
                return self._walk_rule(child, tab, accumulated)

            # ── collect mode (collectint, collectlist, …) ─────────────────
            if key in COLLECT_TYPES and key != "collect":
                saved_pos = self.pos
                try:
                    data = self._collect(key, tab)
                except (RuntimeError, TypeError, SyntaxError):
                    self.pos = saved_pos
                    continue

                if key == "collectcode":
                    combined = accumulated + [data]
                else:
                    combined = accumulated + (data if isinstance(data, list) else [data])
                return self._walk_rule(child, tab, combined)

            # ── token type match ──────────────────────────────────────────
            tok = self.peek()
            if tok is None:
                continue

            if tok.type == key:
                self.consume()
                result = self._walk_rule(child, tab, accumulated)
                if result is not None:
                    return result
                # ย้อน token กลับ แล้วลอง key ถัดไป
                self.pos -= 1
                continue

        return None

    # ── main parse loop ───────────────────────────────────────────────────

    def parse(self):
        while True:
            tok = self.peek()
            if tok is None or tok.type == "EOF":
                break

            if self._current_tab is None:
                self._current_tab = tok.tab

            tab = self._current_tab

            stmt_line = tok.line
            stmt_col  = tok.col

            rule = self.rules.get(tok.type)
            if rule is None:
                _handle_error("rule_not_matched",
                    f"[Warning] No rule matched for token {tok.type!r} "
                    f"(value={tok.value!r}) at {self._loc(tok)}",
                    self._error_policy)
                self.consume()
                continue

            self.consume()
            result = self._walk_rule(rule, tab)
            if result is not None:
                action, data = result
                self.ir.append({
                    "action": action,
                    "data":   data,
                    "tab":    tab,
                    "line":   stmt_line,
                    "col":    stmt_col,
                })

        return self.ir
