# ForgeFile

**ForgeFile** is a build-automation tool inspired by `Makefile`, but with cleaner, more expressive syntax and built-in scripting features — variables, conditionals, functions, and inline Python — without giving up the simplicity of a plain text build script.

```
notlet MODE = ""

if ##$$MODE == "run"## {
    shell ##echo "Hello World"##
}
```

```bash
forgefile MODE=run
```

---

## ⚠️ Security — Read This First

**ForgeFile executes arbitrary shell commands and Python code by design.** This is not a bug or an oversight — it is exactly how `Makefile`, npm `scripts`, `Justfile`, `Taskfile`, and every other build/task runner works. A forgefile is a program, and running it means running whatever it tells your machine to do.

Concretely:

- `shell ##...##` runs the command directly via `os.system()`.
- `py ##...##` executes arbitrary Python via `exec()`.
- Both have full access to your filesystem, network, and shell — the same access *you* have when you run `forgefile`.

**Only run a forgefile if you trust its source, the same way you would only run a `Makefile`, a shell script, or an npm `postinstall` script from a source you trust.**

Practical guidelines:

- ✅ **Read the forgefile before running it**, especially if you downloaded it from somewhere new. It's plain text — take the 30 seconds.
- ✅ Treat a forgefile you didn't write like you would any other executable script downloaded from the internet.
- ✅ Pin dependencies / forgefiles to a specific commit or release if you're pulling them from a repo, rather than always tracking `main`.
- ❌ Don't run a forgefile from an untrusted source "just to see what it does." If you're curious, read it first.
- ❌ Don't pipe a forgefile straight from a URL into execution (`curl ... | forgefile`-style patterns) without inspecting it first.

If you're integrating ForgeFile into CI or a shared environment, treat it with the same access-control discipline you'd apply to any script with shell access: least privilege, code review before merge, and no execution of forgefiles from unreviewed pull requests in privileged CI contexts.

### What *is* sandboxed

The `if` condition and `eval` expression are evaluated through a restricted evaluator (`calc`) that:
- Only allows single expressions (comparisons, arithmetic, boolean logic) — not arbitrary statements.
- Blocks access to dunder attributes/names (`__class__`, `__globals__`, `__builtins__`, etc.), which are the standard building blocks of Python sandbox-escape techniques.
- Restricts available functions to a small whitelist (`abs`, `min`, `max`, `len`, `int`, `float`, `str`, `bool`, `round`, `sum`).

This exists because `if`/`eval` are meant only for *evaluating conditions and values* — not for running commands. It is **not** a general-purpose security sandbox, and it does not change the fact that `shell` and `py` blocks run with full privileges. Treat the whole language as unrestricted, and use this restriction only as a guard against accidental misuse of `if`/`eval`, not as a safety net for untrusted input.

### Permission prompts for destructive commands

Before running a `shell` command, ForgeFile checks the fully-resolved command (after `$$variable` substitution) against a list of destructive patterns defined in [`config/config.json`](./config/config.json). If a match is found, ForgeFile stops and asks for confirmation before executing:

```
[PERMISSION REQUIRED]
  Command : rm -rf /some/path
  Matched : looks like a potentially destructive pattern (rm\s+(-\w*r\w*f\w*|...)\s+/(\s|$))
  Run this command anyway? [y/N]:
```

Commands that currently require confirmation by default (see `config/config.json` to add/remove):

| Pattern | Why it's flagged |
|---|---|
| `rm -rf /`, `rm -rf ~`, `rm -rf *`, `rm -rf $HOME` | Recursive delete of root, home, or everything in the current directory |
| `mkfs*` on a `/dev/...` device | Reformats a disk, destroying all data on it |
| `dd if=... of=/dev/sd*` or `/dev/nvme*` | Raw disk write — can overwrite a whole drive |
| the classic `:(){ :\|:& };:` shape | Fork bomb — spawns processes until the system is unusable |
| `chmod -R 777 /` | Recursively opens permissions on the entire filesystem |
| `chown -R ... /` | Recursively changes ownership of the entire filesystem |
| `curl ... \| sh` / `\| bash`, `wget ... \| sh` / `\| bash` | Downloads and immediately executes a remote script sight-unseen |
| `sudo rm ...` | Privileged delete |
| `> /dev/sda`, `> /dev/nvme0` | Overwrites a raw block device |
| `shutdown`, `reboot`, `poweroff` | Powers off or restarts the machine |
| `mv ... /dev/null` | Effectively deletes the source by moving it to the null device |
| Windows `format C:` / `del /s /q` | Disk format or recursive silent delete on Windows |

This is a **safety net against accidental mistakes and copy-pasted commands you didn't fully read** — not a security boundary. Someone deliberately writing malicious code can trivially construct an equivalent command that doesn't match these patterns (e.g. building the command from string pieces at runtime, or base64-encoding it). Don't rely on this list to make an untrusted forgefile safe to run — see the section above.

**Configuring the prompt:**

- Turn confirmation off entirely: set `"require_confirmation": false` in `config/config.json`.
- Skip prompts for one run (e.g. in CI): pass `--yes` / `-y` on the command line, or set the environment variable named in `auto_approve_env` (default `FORGEFILE_YES`) to `1`/`true`/`yes`.
- Add your own patterns: edit the `dangerous_patterns` array in `config/config.json` — each entry is a Python regular expression, matched case-insensitively against the fully-resolved shell command.
- If there's no interactive terminal available to answer the prompt (e.g. a detached background process), ForgeFile **refuses the command by default** rather than guessing.

---

## Installation

```bash
git clone https://github.com/<your-org>/forgefile.git
cd forgefile
# (add real install steps here — pip install, symlink to PATH, etc.)
```

## Usage

```bash
forgefile [VAR=value ...] [target]
```

- `VAR=value` pairs are loaded into the script's variable table before execution.
- `target` (optional) calls a function defined with `func` in your forgefile.

## Syntax Reference

Every statement ends with a newline. Code blocks are wrapped in `{ }`. String literals use double-hash delimiters: `##like this##`.

| Keyword  | Purpose                                                | Example |
|----------|---------------------------------------------------------|---------|
| `print`  | Print a value                                            | `print ##Hello##` |
| `shell`  | Run a shell command                                       | `shell ##echo hi##` |
| `let`    | Set a variable (always overwrites)                        | `let NAME = ##value##` |
| `notlet` | Set a variable only if it isn't already set               | `notlet MODE = ##default##` |
| `eval`   | Set a variable to the result of a Python expression        | `eval RESULT = ##1 + 2##` |
| `if`     | Run a code block if a condition is true                    | `if ##$$MODE == "run"## { ... }` |
| `func`   | Define a reusable function/target                          | `func build { ... }` |
| `call`   | Call a previously defined function                          | `call build` |
| `py`     | Run raw Python code (full access — see security note above) | `py ##print(1+1)##` |

### Variables

Prefix a variable name with `$$` to substitute its value into a string (used in `shell` and `if`/`eval` conditions):

```
notlet MODE = ##run##

if ##$$MODE == "run"## {
    shell ##echo "Running in $$MODE mode"##
}
```

### Functions and targets

```
func build {
    shell ##echo "Building..."##
}

call build
```

Command-line arguments that aren't `VAR=value` pairs are treated as target names and invoked automatically, e.g. `forgefile build` runs the `build` function.

## Configuration / Grammar

ForgeFile's lexer and parser rules are data-driven via `ForgeFileRule.json`, so the syntax itself (keywords, operators, string delimiters, etc.) can be customized. See `ForgeFileRule.json` for the full grammar definition, and `Mono_py10.py` for the lexer/normalizer implementation.

Security-related settings (the destructive-command patterns and confirmation behavior described above) live in `config/config.json`, one directory up from the interpreter script:

```
project-root/
├── config/
│   └── config.json       ← security settings
└── ForgeFile/
    ├── forgefile.py       ← interpreter
    ├── Mono_py10.py        ← lexer/normalizer
    └── ForgeFileRule.json  ← language grammar
```

If the file is missing or invalid, ForgeFile falls back to built-in defaults and prints a warning — it will never silently disable confirmation just because the config couldn't be loaded.

## Contributing

Issues and PRs welcome. If you're submitting a change that touches `shell_cmd`, `run_python`, or `calc`, please call out any security implications explicitly in the PR description — these are the highest-sensitivity parts of the codebase.

## License

<!-- add your license here --># ForgeFile-v0.1s
# ForgeFile-v0.1s
# ForgeFile-v0.1s
# ForgeFile-v0.1s
