"""
Archie Agent Tools
==================
Permission-gated tools the LLM can call. Everything is OFF by default;
archie_agent.py flips the switches in PERMS from the command line:

    --allow-access-to-files      -> list_dir, read_file
    --allow-access-to-internet   -> search_internet, fetch_url
    --allow-access-to-apply      -> write_file, replace_in_file (implies files)
    --allow-shell                -> run_command

NOTE: this is a permission layer, not a sandbox. Path checks keep the
agent inside the workdir, but run_command can do anything your user can.
"""

import json
import os
import re
import subprocess
from html import unescape
from pathlib import Path


class Permissions:
    def __init__(self):
        self.files = False
        self.internet = False
        self.apply = False
        self.shell = False
        self.auto_yes = False            # --yes: skip approval prompts
        self.interactive = False         # True only for CLI profile on a real terminal
        self.unrestricted_paths = False  # --unrestricted-paths
        self.workdir = Path.cwd()
        self.shell_timeout = 30
        self.max_output = 8000           # chars returned to the model per tool call
        self.max_read = 40000            # chars read_file will return

    def as_dict(self):
        return {
            "files": self.files,
            "internet": self.internet,
            "apply": self.apply,
            "shell": self.shell,
        }


PERMS = Permissions()

FLAG_FOR = {
    "files": "--allow-access-to-files",
    "internet": "--allow-access-to-internet",
    "apply": "--allow-access-to-apply",
    "shell": "--allow-shell",
}


# ==========================================
#           Helpers
# ==========================================
def _clip(text, limit=None):
    limit = limit or PERMS.max_output
    if len(text) > limit:
        return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"
    return text


def _resolve(path):
    p = Path(os.path.expanduser(str(path)))
    if not p.is_absolute():
        p = PERMS.workdir / p
    p = p.resolve()
    if not PERMS.unrestricted_paths:
        try:
            p.relative_to(PERMS.workdir.resolve())
        except ValueError:
            raise PermissionError(
                f"{p} is outside the working directory ({PERMS.workdir}). "
                "The user can allow this with --unrestricted-paths."
            )
    return p


def _confirm(description):
    """Ask the human to approve a risky action."""
    if PERMS.auto_yes:
        return True
    if not PERMS.interactive:
        return False  # no way to ask (Telegram/Discord/GUI) -> deny unless --yes
    try:
        ans = input(f"\n\033[93m[APPROVE?]\033[0m {description}\n  [y/N] > ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return ans in ("y", "yes")


def _html_to_text(html):
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(html)).strip()


# ==========================================
#           Tools: internet
# ==========================================
def search_internet(query):
    print(f"\033[94m[Searching...]\033[0m {query}")
    try:
        from googlesearch import search
        results = search(query, num_results=3, lang="ru")
        res_list = [str(r) for r in results]
        return "Files from internet:\n" + "\n".join(res_list) if res_list else "I dont find any information."
    except Exception as e:
        return f"Search error: {e}"


def fetch_url(url):
    if not re.match(r"^https?://", url, re.I):
        return "[ERROR] Only http(s) URLs are allowed."
    import requests
    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (archie-agent)"})
    r.raise_for_status()
    ctype = r.headers.get("content-type", "")
    text = _html_to_text(r.text) if "html" in ctype else r.text
    return _clip(text)


# ==========================================
#           Tools: files (read)
# ==========================================
def list_dir(path="."):
    p = _resolve(path)
    if not p.is_dir():
        return f"[ERROR] Not a directory: {p}"
    entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    lines = [f"{e.name}/" if e.is_dir() else e.name for e in entries[:200]]
    more = f"\n...and {len(entries) - 200} more" if len(entries) > 200 else ""
    return f"{p}\n" + "\n".join(lines) + more


def read_file(path):
    p = _resolve(path)
    if not p.is_file():
        return f"[ERROR] Not a file: {p}"
    data = p.read_text(encoding="utf-8", errors="replace")
    return _clip(data, PERMS.max_read)


# ==========================================
#           Tools: apply (write)
# ==========================================
def write_file(path, content):
    p = _resolve(path)
    verb = "Overwrite" if p.exists() else "Create"
    if not _confirm(f"{verb} file {p} ({len(content)} chars)"):
        return "[DENIED] User did not approve this change."
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8", newline="\n")
    return f"[OK] Wrote {len(content)} chars to {p}"


def replace_in_file(path, old, new):
    p = _resolve(path)
    if not p.is_file():
        return f"[ERROR] Not a file: {p}"
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        return f"[ERROR] 'old' must match exactly once, found {count} matches."
    if not _confirm(f"Edit {p}: replace {len(old)} chars with {len(new)} chars"):
        return "[DENIED] User did not approve this change."
    p.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    return f"[OK] Edited {p}"


# ==========================================
#           Tools: shell
# ==========================================
def run_command(command):
    if not _confirm(f"Run shell command in {PERMS.workdir}:\n  {command}"):
        return "[DENIED] User did not approve this command."
    try:
        p = subprocess.run(
            command, shell=True, cwd=str(PERMS.workdir),
            capture_output=True, text=True, errors="replace",
            timeout=PERMS.shell_timeout,
        )
    except subprocess.TimeoutExpired:
        return f"[ERROR] Command timed out after {PERMS.shell_timeout}s."
    return _clip(f"exit={p.returncode}\n--- stdout ---\n{p.stdout}\n--- stderr ---\n{p.stderr}")


# ==========================================
#           Registry
# ==========================================
def _spec(name, desc, props, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


_S = {"type": "string"}

REGISTRY = {
    "search_internet": {
        "perm": "internet", "fn": search_internet,
        "spec": _spec("search_internet", "Search in Google", {"query": _S}, ["query"]),
    },
    "fetch_url": {
        "perm": "internet", "fn": fetch_url,
        "spec": _spec("fetch_url", "Download a web page and return its text", {"url": _S}, ["url"]),
    },
    "list_dir": {
        "perm": "files", "fn": list_dir,
        "spec": _spec("list_dir", "List files in a directory inside the working directory", {"path": _S}, []),
    },
    "read_file": {
        "perm": "files", "fn": read_file,
        "spec": _spec("read_file", "Read a text file", {"path": _S}, ["path"]),
    },
    "write_file": {
        "perm": "apply", "fn": write_file,
        "spec": _spec("write_file", "Create or overwrite a file (user approval required)",
                      {"path": _S, "content": _S}, ["path", "content"]),
    },
    "replace_in_file": {
        "perm": "apply", "fn": replace_in_file,
        "spec": _spec("replace_in_file", "Replace one exact text snippet in a file (user approval required)",
                      {"path": _S, "old": _S, "new": _S}, ["path", "old", "new"]),
    },
    "run_command": {
        "perm": "shell", "fn": run_command,
        "spec": _spec("run_command", "Run a shell command in the working directory (user approval required)",
                      {"command": _S}, ["command"]),
    },
}


def tool_schemas():
    """Only the tools the user has allowed."""
    return [t["spec"] for t in REGISTRY.values() if getattr(PERMS, t["perm"])]


def run_tool(name, args):
    tool = REGISTRY.get(name)
    if not tool:
        return f"[ERROR] Unknown tool: {name}"
    if not getattr(PERMS, tool["perm"]):
        return f"[DENIED] '{name}' needs {FLAG_FOR[tool['perm']]}. Tell the user to restart archie-agent with that flag."
    print(f"\033[96m[TOOL]\033[0m {name} {json.dumps(args, ensure_ascii=False)[:200]}")
    try:
        return str(tool["fn"](**args))
    except PermissionError as e:
        return f"[DENIED] {e}"
    except TypeError as e:
        return f"[ERROR] Bad arguments for {name}: {e}"
    except Exception as e:
        return f"[ERROR] {name} failed: {e}"
