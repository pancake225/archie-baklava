"""
Archie Agent Tools
==================
Permission-gated tools the LLM can call. Everything is OFF by default;
archie_agent.py flips the switches in PERMS from the command line:

    --allow-access-to-files      -> list_dir, read_file, find_files, grep_files
    --allow-access-to-internet   -> search_internet, fetch_url
    --allow-access-to-apply      -> write_file, replace_in_file (implies files)
    --allow-shell                -> run_command
    --allow-email                -> fetch_email

NOTE: this is a permission layer, not a sandbox. Path checks keep the
agent inside the workdir, but run_command can do anything your user can.
"""

import fnmatch
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
        self.email = False              # email reading via IMAP
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
            "email": self.email,
        }


PERMS = Permissions()

FLAG_FOR = {
    "files": "--allow-access-to-files",
    "internet": "--allow-access-to-internet",
    "apply": "--allow-access-to-apply",
    "shell": "--allow-shell",
    "email": "--allow-email",
}

# Folders that are never interesting to the model and can be huge.
IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build", ".idea",
    ".vscode",
}
MAX_GREP_FILE = 1_000_000  # skip files bigger than ~1 MB
MAX_FIND_RESULTS = 500
MAX_GREP_RESULTS = 200


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


def _as_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on", "y")


def _as_int(value, default, low, high):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = default
    return max(low, min(value, high))


def _walk_files(root):
    """Walk root without following symlinks or descending into noise folders."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in IGNORED_DIRS and not (Path(dirpath) / d).is_symlink()
        )
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if not p.is_symlink():
                yield p


# ==========================================
#           Tools: internet
# ==========================================
def search_internet(query):
    print(f"\033[94m[Searching...]\033[0m {query}")
    try:
        from googlesearch import search
        lang = os.environ.get("ARCHIE_SEARCH_LANG", "en")
        results = search(query, num_results=3, lang=lang)
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


def find_files(pattern="*", path="."):
    """Find files by shell-style glob (e.g. '*.py', 'src/**/*.json')."""
    root = _resolve(path)
    if not root.is_dir():
        return f"[ERROR] Not a directory: {root}"
    pattern = str(pattern or "*").strip() or "*"
    if os.path.isabs(pattern):
        return "[ERROR] Pattern must be relative, e.g. '*.py' or 'src/**/*.py'."

    matches = []
    truncated = False
    for p in _walk_files(root):
        rel = p.relative_to(root).as_posix()
        if fnmatch.fnmatch(p.name, pattern) or fnmatch.fnmatch(rel, pattern):
            matches.append(rel)
            if len(matches) >= MAX_FIND_RESULTS:
                truncated = True
                break

    if not matches:
        return f"No files matching {pattern!r} in {root}."
    more = f"\n...[stopped at {MAX_FIND_RESULTS} results]" if truncated else ""
    return f"{len(matches)} match(es) for {pattern!r} in {root}:\n" + "\n".join(matches) + more


def grep_files(pattern, path=".", glob="*", max_results=50):
    """Search file contents with a Python regular expression."""
    root = _resolve(path)
    if not root.is_dir():
        return f"[ERROR] Not a directory: {root}"
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return f"[ERROR] Invalid regex: {e}"

    glob = str(glob or "*").strip() or "*"
    limit = _as_int(max_results, 50, 1, MAX_GREP_RESULTS)
    results = []

    for p in _walk_files(root):
        if not fnmatch.fnmatch(p.name, glob):
            continue
        try:
            if p.stat().st_size > MAX_GREP_FILE:
                continue
            data = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = p.relative_to(root).as_posix()
        for lineno, line in enumerate(data.splitlines(), 1):
            if rx.search(line):
                results.append(f"{rel}:{lineno}: {line.strip()[:300]}")
                if len(results) >= limit:
                    return "\n".join(results) + f"\n...[stopped at {limit} matches]"

    if not results:
        return f"No matches for {pattern!r} in {root} (glob {glob!r})."
    return "\n".join(results)


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
#           Tools: email
# ==========================================
def _decode_part(part):
    payload = part.get_payload(decode=True)
    if payload is None:
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _email_body(msg):
    """Prefer text/plain, fall back to text/html, and handle nested multiparts."""
    plain = ""
    html = ""
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_maintype() == "multipart":
            continue
        ctype = part.get_content_type()
        if ctype == "text/plain" and not plain:
            plain = _decode_part(part)
        elif ctype == "text/html" and not html:
            html = _decode_part(part)
    if plain.strip():
        return plain.strip()
    if html.strip():
        return _html_to_text(html)
    return ""


def _parse_email_message(msg):
    """Best-effort parse of an email into subject/from/to/date/body."""
    return {
        "subject": str(msg.get("Subject", "") or ""),
        "from": str(msg.get("From", "") or ""),
        "to": str(msg.get("To", "") or ""),
        "date": str(msg.get("Date", "") or ""),
        "body": _email_body(msg),
    }


def fetch_email(mailbox="INBOX", limit=10, unread_only=True, user_id=None):
    """
    Fetch emails from a mailbox via IMAP (read-only; messages stay unread).
    Credentials come from ARCHIE_MAIL_HOST / ARCHIE_MAIL_USER /
    ARCHIE_MAIL_PASSWORD. Returns the most recent `limit` messages that match.
    """
    import imaplib
    import email as email_module

    host = os.environ.get("ARCHIE_MAIL_HOST", "")
    user = user_id or os.environ.get("ARCHIE_MAIL_USER", "")
    password = os.environ.get("ARCHIE_MAIL_PASSWORD", "")

    if not host or not user or not password:
        return "[ERROR] Email not configured. Set ARCHIE_MAIL_HOST, ARCHIE_MAIL_USER, ARCHIE_MAIL_PASSWORD."

    mailbox = str(mailbox or "INBOX").strip().strip('"') or "INBOX"
    limit = _as_int(limit, 10, 1, 50)
    unread_only = _as_bool(unread_only, True)
    criteria = "UNSEEN" if unread_only else "ALL"

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(host, timeout=30)
        mail.login(user, password)
        status, _ = mail.select(f'"{mailbox}"', readonly=True)
        if status != "OK":
            return f"[ERROR] Could not open mailbox {mailbox!r}."

        status, messages = mail.search(None, criteria)
        if status != "OK":
            return f"[ERROR] IMAP search failed: {status}"
        ids = messages[0].split()
        if not ids:
            return "No new emails found." if unread_only else "No emails found."

        fetched = []
        for num in ids[-limit:]:
            status, data = mail.fetch(num, "(RFC822)")
            if status != "OK" or not data:
                continue
            raw = next((item[1] for item in data if isinstance(item, tuple)), None)
            if raw is None:
                continue
            fetched.append(_parse_email_message(email_module.message_from_bytes(raw)))

        if not fetched:
            return "No new emails found." if unread_only else "No emails found."

        out = [f"Emails ({len(fetched)} found in {mailbox}):"]
        for m in fetched:
            out.append(
                f"Subject: {m['subject']}\nFrom: {m['from']}\nTo: {m['to']}\n"
                f"Date: {m['date']}\nBody: {m['body'][:1000]}"
            )
        return _clip("\n\n".join(out))
    except Exception as e:
        return f"[ERROR] Email fetch failed: {e}"
    finally:
        if mail is not None:
            try:
                mail.logout()
            except Exception:
                pass


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
_INT = {"type": "integer"}
_BOOL = {"type": "boolean"}

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
    "find_files": {
        "perm": "files", "fn": find_files,
        "spec": _spec("find_files",
                      "Find files by glob pattern, e.g. '*.py' or 'src/**/*.json'",
                      {"pattern": _S, "path": _S}, ["pattern"]),
    },
    "grep_files": {
        "perm": "files", "fn": grep_files,
        "spec": _spec("grep_files",
                      "Search file contents with a regular expression",
                      {"pattern": _S, "path": _S, "glob": _S, "max_results": _INT}, ["pattern"]),
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
    "fetch_email": {
        "perm": "email", "fn": fetch_email,
        "spec": _spec("fetch_email",
                      "Read emails from your mailbox via IMAP (does not mark them as read)",
                      {"mailbox": _S, "limit": _INT, "unread_only": _BOOL}, []),
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
