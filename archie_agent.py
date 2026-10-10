#!/usr/bin/env python3
"""
archie-agent — cross-platform launcher (Linux / macOS / Windows)
=================================================================
Reads arxh.conf directly (no sed, no bash needed), applies command-line
flags on top, then starts the chosen profile.

Precedence: command-line flag  >  environment variable  >  arxh.conf  >  defaults
"""

import argparse
import importlib
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

__version__ = "0.5"

HOME = Path(os.environ.get("ARCHIE_HOME") or Path(__file__).resolve().parent)
sys.path.insert(0, str(HOME))

PROFILES = {
    "telegram": "profiles.telegram_profile",
    "discord": "profiles.discord_profile",
    "cli": "profiles.cli_profile",
    "gui": "profiles.gui_profile",
}

PROVIDER_MAP = {  # name -> (local, groq, openrouter)
    "local": (True, False, False),
    "groq": (False, True, False),
    "api": (False, True, False),  # old name for groq
    "openrouter": (False, False, True),
    "both": (True, True, False),
    "local+openrouter": (True, False, True),
    "all": (True, True, True),
}

EXAMPLES = """\
examples:
  archie-agent --cli
  archie-agent --cli --allow-access-to-files --allow-access-to-internet
  archie-agent --cli --allow-access-to-apply --workdir ~/projects/site
  archie-agent --cli --allow-all --yes            # no questions asked (be careful)
  archie-agent --telegram --provider api --read-only
  archie-agent --cli --provider openrouter --openrouter-model openrouter/auto
  archie-agent --cli --model llama3.2 --no-emoji --admin
  archie-agent --show-permissions --allow-access-to-files
"""


# ==========================================
#           Small helpers
# ==========================================
def setup_console():
    if os.name == "nt":
        os.system("")  # turns on ANSI colors in cmd.exe / PowerShell
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "on", "y")


def ints(v):
    return [int(x) for x in re.findall(r"-?\d+", v or "")]


def load_conf(path):
    """Parse the KEY="value" file written by setup.sh / archie_setup.py."""
    conf = {}
    if not path.is_file():
        return conf
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        if len(val) >= 2 and val[0] == val[-1] == '"':
            val = re.sub(r'\\([\\"$`])', r"\1", val[1:-1])
        elif len(val) >= 2 and val[0] == val[-1] == "'":
            val = val[1:-1]
        conf[key] = val
    return conf


# ==========================================
#           Argument parser
# ==========================================
def build_parser():
    p = argparse.ArgumentParser(
        prog="archie-agent",
        description="Run Archie from anywhere, with explicit permissions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXAMPLES,
    )

    g = p.add_argument_group("interface (default: PROFILE_TYPE from arxh.conf, else --cli)")
    m = g.add_mutually_exclusive_group()
    for name in PROFILES:
        m.add_argument(f"--{name}", dest="profile", action="store_const", const=name,
                       help=f"run the {name} profile")

    a = p.add_argument_group("permissions (everything is OFF unless you allow it)")
    a.add_argument("--allow-access-to-files", action="store_true", default=None,
                   help="let Archie list and read files inside the workdir")
    a.add_argument("--allow-access-to-internet", action="store_true", default=None,
                   help="let Archie search Google and fetch web pages")
    a.add_argument("--allow-access-to-apply", action="store_true", default=None,
                   help="let Archie apply changes: create/edit files (implies --allow-access-to-files)")
    a.add_argument("--allow-shell", action="store_true", default=None,
                   help="let Archie run shell commands in the workdir")
    a.add_argument("--allow-all", action="store_true", default=None,
                   help="files + internet + apply + shell")
    a.add_argument("--read-only", action="store_true", default=None,
                   help="force-disable apply and shell, whatever else is set")
    a.add_argument("-y", "--yes", action="store_true", default=None,
                   help="auto-approve write/shell actions (Telegram/Discord/GUI can't ask, so they need this)")
    a.add_argument("--workdir", metavar="DIR",
                   help="folder Archie may touch (default: current directory)")
    a.add_argument("--unrestricted-paths", action="store_true", default=None,
                   help="allow file tools outside --workdir")
    a.add_argument("--shell-timeout", type=int, metavar="SEC",
                   help="kill shell commands after SEC seconds (default 30)")

    b = p.add_argument_group("model / behavior")
    b.add_argument("--provider", choices=list(PROVIDER_MAP),
                   help="local = Ollama, groq (or api) = Groq, openrouter = OpenRouter, "
                        "both = local+groq, local+openrouter, all = all three (tried in that order)")
    b.add_argument("--model", metavar="NAME", help="Ollama model, e.g. llama3.2")
    b.add_argument("--groq-model", metavar="NAME", help="Groq model name")
    b.add_argument("--openrouter-model", metavar="NAME", help="OpenRouter model id, e.g. openrouter/auto")
    b.add_argument("--openrouter-key", metavar="KEY",
                   help="OpenRouter API key (prefer the OPENROUTER_API_KEY env var)")
    b.add_argument("--groq-key", metavar="KEY",
                   help="Groq API key (prefer the GROQ_API_KEY env var — flags end up in shell history)")
    b.add_argument("--system-prompt", metavar="TEXT", help="replace the base instruction")
    b.add_argument("--admin", action="store_true", default=None, help="CLI: start in admin mode")
    b.add_argument("--emoji", action=argparse.BooleanOptionalAction, default=None, help="allow emoji in replies")
    b.add_argument("--vision", action=argparse.BooleanOptionalAction, default=None, help="image description")
    b.add_argument("--vision-model", metavar="NAME", help="Ollama vision model, e.g. llava:7b")
    b.add_argument("--token", metavar="TOKEN", help="Telegram/Discord bot token (overrides arxh.conf)")

    o = p.add_argument_group("misc")
    o.add_argument("--config", metavar="FILE", help="path to arxh.conf (default: next to archie_agent.py)")
    o.add_argument("--show-permissions", action="store_true", help="print the effective settings and exit")
    o.add_argument("--no-ollama-autostart", action="store_true", help="don't try to start 'ollama serve'")
    o.add_argument("--version", action="store_true", help="print version and exit")
    return p


# ==========================================
#           Permissions
# ==========================================
def resolve_perms(a, conf):
    def pick(flag, key, env):
        if flag is not None:
            return bool(flag)
        if env in os.environ:
            return truthy(os.environ[env])
        return truthy(conf.get(key, "False"))

    files = pick(a.allow_access_to_files, "ALLOW_FILES", "ARCHIE_ALLOW_FILES")
    internet = pick(a.allow_access_to_internet, "ALLOW_INTERNET", "ARCHIE_ALLOW_INTERNET")
    apply_ = pick(a.allow_access_to_apply, "ALLOW_APPLY", "ARCHIE_ALLOW_APPLY")
    shell = pick(a.allow_shell, "ALLOW_SHELL", "ARCHIE_ALLOW_SHELL")
    if a.allow_all:
        files = internet = apply_ = shell = True
    if apply_:
        files = True
    if a.read_only:
        apply_ = shell = False
    return {"files": files, "internet": internet, "apply": apply_, "shell": shell}


def print_summary(profile, perms, workdir, ai_core, auto_yes, unrestricted):
    def mark(b):
        return "\033[92mON \033[0m" if b else "\033[90moff\033[0m"

    print(f"\033[92m[archie-agent {__version__}]\033[0m profile={profile} "
          f"provider={ai_core.provider_label()} model={ai_core.primary_model()}")
    print(f"  files    {mark(perms['files'])}   internet {mark(perms['internet'])}")
    print(f"  apply    {mark(perms['apply'])}   shell    {mark(perms['shell'])}")
    if perms["files"] or perms["apply"] or perms["shell"]:
        scope = "ANYWHERE" if unrestricted else str(workdir)
        print(f"  workdir  {scope}")
    if (perms["apply"] or perms["shell"]) and auto_yes:
        print("  \033[93m--yes: changes and commands run WITHOUT asking\033[0m")
    print("")


# ==========================================
#           Ollama autostart
# ==========================================
def ollama_up():
    try:
        urllib.request.urlopen("http://127.0.0.1:11434", timeout=1.5).read()
        return True
    except Exception:
        return False


def ensure_ollama():
    if ollama_up():
        return True
    exe = shutil.which("ollama")
    if not exe and os.name == "nt":
        cand = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if cand.is_file():
            exe = str(cand)
    if not exe:
        print("\033[93m[!]\033[0m Ollama not found. Install it from https://ollama.com or use --provider api.")
        return False

    if "OLLAMA_MODELS" not in os.environ and (HOME / "MODELS").is_dir():
        os.environ["OLLAMA_MODELS"] = str(HOME / "MODELS")

    print("[i] Ollama isn't running — starting it...")
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        kw["creationflags"] = 0x08000000 | 0x00000008  # CREATE_NO_WINDOW | DETACHED_PROCESS
    else:
        kw["start_new_session"] = True
    try:
        subprocess.Popen([exe, "serve"], **kw)
    except Exception as e:
        print(f"\033[93m[!]\033[0m Couldn't start Ollama: {e}")
        return False
    for _ in range(30):
        time.sleep(0.5)
        if ollama_up():
            return True
    print("\033[93m[!]\033[0m Ollama didn't come up in time.")
    return False


# ==========================================
#           Main
# ==========================================
def main():
    setup_console()
    args = build_parser().parse_args()

    if args.version:
        print(f"archie-agent {__version__}")
        return 0

    conf = load_conf(Path(args.config).expanduser() if args.config else HOME / "arxh.conf")
    if not conf and not args.config:
        print(f"\033[93m[!]\033[0m No arxh.conf in {HOME} — using built-in defaults. Run the setup wizard first.")

    profile = args.profile or os.environ.get("ARCHIE_PROFILE_TYPE") or conf.get("PROFILE_TYPE") or "cli"
    if profile not in PROFILES:
        print(f"[!] Unknown profile '{profile}'. Choose one of: {', '.join(PROFILES)}")
        return 2

    try:
        import ai_core
        import agent_tools
    except ImportError as e:
        print(f"[!] Missing dependency: {e}")
        print("    Run the installer again (install.sh on Linux/macOS, install.ps1 on Windows).")
        return 1

    # --- config file -> ai_core ---
    ov = {}
    if "LOCAL" in conf:
        ov["LOCAL"] = truthy(conf["LOCAL"])
    if "API" in conf:
        ov["API"] = truthy(conf["API"])
    if "OPENROUTER" in conf:
        ov["OPENROUTER"] = truthy(conf["OPENROUTER"])
    if conf.get("OPENROUTER_KEY"):
        ov["OPENROUTER_KEY"] = conf["OPENROUTER_KEY"]
    if conf.get("OPENROUTER_MODEL"):
        ov["OPENROUTER_MODEL"] = conf["OPENROUTER_MODEL"]
    if conf.get("GROQ_KEY"):
        ov["GROQ_KEY"] = conf["GROQ_KEY"]
    if conf.get("OLLAMA_MODEL"):
        ov["OLLAMA_MODEL"] = conf["OLLAMA_MODEL"]
    if conf.get("BASE_INSTRUCTION"):
        ov["BASE_INSTRUCTION"] = conf["BASE_INSTRUCTION"]
    if conf.get("ADMIN_INSTRUCTION"):
        ov["ADMIN_INSTRUCTION"] = conf["ADMIN_INSTRUCTION"]
    if "EMOJI_ENABLED" in conf:
        ov["EMOJI_ENABLED"] = truthy(conf["EMOJI_ENABLED"])
    if "GROUP_ID" in conf:
        ov["GROUP_ID"] = (ints(conf["GROUP_ID"]) or [0])[0]
    if "BANNED_USERS" in conf:
        ov["BANNED"] = ints(conf["BANNED_USERS"])
    if "MAT_WORDS" in conf:
        ov["MAT"] = [w.strip() for w in conf["MAT_WORDS"].split(",") if w.strip()]
    admin_ids = ints(conf.get("ADMIN_IDS", ""))
    if profile in ("telegram", "discord"):
        ov["ADMIN_ID"] = admin_ids

    # --- flags -> ai_core (win over config) ---
    if args.provider:
        ov["LOCAL"], ov["API"], ov["OPENROUTER"] = PROVIDER_MAP[args.provider]
    if args.model:
        ov["OLLAMA_MODEL"] = args.model
    if args.groq_model:
        ov["GROQ_MODEL"] = args.groq_model
    if args.groq_key:
        ov["GROQ_KEY"] = args.groq_key
    if args.openrouter_model:
        ov["OPENROUTER_MODEL"] = args.openrouter_model
    if args.openrouter_key:
        ov["OPENROUTER_KEY"] = args.openrouter_key
    if args.system_prompt:
        ov["BASE_INSTRUCTION"] = args.system_prompt
    if args.emoji is not None:
        ov["EMOJI_ENABLED"] = args.emoji
    try:
        ai_core.configure(**ov)
    except RuntimeError as e:
        print(e)
        return 1

    # --- vision ---
    try:
        import vision
        if "VISION_ENABLED" in conf:
            vision.VISION_ENABLED = truthy(conf["VISION_ENABLED"])
        if conf.get("VISION_MODEL"):
            vision.VISION_MODEL = conf["VISION_MODEL"]
        if args.vision is not None:
            vision.VISION_ENABLED = args.vision
        if args.vision_model:
            vision.VISION_MODEL = args.vision_model
    except ImportError:
        pass

    # --- permissions ---
    perms = resolve_perms(args, conf)
    P = agent_tools.PERMS
    P.files, P.internet, P.apply, P.shell = perms["files"], perms["internet"], perms["apply"], perms["shell"]
    P.auto_yes = bool(args.yes)
    P.unrestricted_paths = bool(args.unrestricted_paths)
    P.interactive = profile == "cli" and sys.stdin.isatty()
    if args.shell_timeout:
        P.shell_timeout = args.shell_timeout
    if args.workdir:
        wd = Path(args.workdir).expanduser().resolve()
        if not wd.is_dir():
            print(f"[!] --workdir is not a directory: {wd}")
            return 2
        P.workdir = wd
    else:
        P.workdir = Path.cwd()

    print_summary(profile, perms, P.workdir, ai_core, P.auto_yes, P.unrestricted_paths)
    if args.show_permissions:
        return 0

    if (perms["apply"] or perms["shell"]) and not P.interactive and not P.auto_yes:
        print("\033[93m[i]\033[0m This profile can't ask for approval, so writes/commands will be denied. "
              "Add --yes if you really want them to run.\n")

    if ai_core.LOCAL and not args.no_ollama_autostart:
        ensure_ollama()

    # --- load profile + tokens ---
    mod = importlib.import_module(PROFILES[profile])
    if profile == "telegram":
        token = args.token or conf.get("BOT_TOKEN")
        if token:
            mod.TOKEN = token
        if mod.TOKEN.startswith("REPLACE_ME"):
            print("[!] No Telegram token. Run the setup wizard or pass --token.")
            return 1
    elif profile == "discord":
        token = args.token or conf.get("DISCORD_TOKEN")
        if token:
            mod.DISCORD_TOKEN = token
        if mod.DISCORD_TOKEN.startswith("REPLACE_ME"):
            print("[!] No Discord token. Run the setup wizard or pass --token.")
            return 1
        mod.DISCORD_ADMIN_ID = admin_ids
        mod.DISCORD_BROADCAST_CHANNEL_ID = (ints(conf.get("DISCORD_CHANNEL_ID", "")) or [0])[0]
    elif profile == "cli" and args.admin:
        ai_core.modes[mod.CLI_UID] = "admin"

    mod.run()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[i] Bye.")
