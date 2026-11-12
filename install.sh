#!/usr/bin/env bash
# ==========================================
#           ARXH INSTALLER
# ==========================================

GREEN='\033[92m'
CYAN='\033[96m'
RED='\033[91m'
YELLOW='\033[93m'
MAGENTA='\033[95m'
BOLD='\033[1m'
RESET='\033[0m'

set -e
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

CONFIG_FILE="$PROJECT_DIR/arxh.conf"
source "$PROJECT_DIR/scripts/init_compat.sh"



echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║       ██     ██                                          ║"
echo "║                ██                                        ║"
echo "║              ██                                          ║"
echo "║       ██       ██                                        ║"
echo "║              ██                                          ║"
echo "║                                                          ║"
echo "║  > installer :3 • v0.6                                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${RESET}"

# --- Check config exists ---
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[!] arxh.conf not found!"
    echo "[i] Run: ./setup.sh first"
    exit 1
fi

# --- Load config ---
echo "[i] Loading config from arxh.conf..."
source "$CONFIG_FILE"
PROFILE_TYPE="${PROFILE_TYPE:-telegram}"
echo "[✓] Loaded: $BOT_NAME | Profile=$PROFILE_TYPE | Local=$LOCAL | API=$API"
echo ""

# --- Ollama models folder ---
export OLLAMA_MODELS="$PROJECT_DIR/MODELS"
mkdir -p "$OLLAMA_MODELS"
echo "[i] Ollama models folder: $OLLAMA_MODELS"
echo ""

# --- 1: System deps ---
echo "[1/4] Installing system dependencies..."
DISTRO="$(source "$PROJECT_DIR/scripts/init_compat.sh" && detect_distro)"
PM="$(source "$PROJECT_DIR/scripts/init_compat.sh" && detect_package_manager)"
echo "[i] Detected distro: $DISTRO, package manager: $PM"

install_system_deps() {
    case "$PM" in
        pacman)
            sudo pacman -Sy --needed --noconfirm python python-pip python-virtualenv ollama
            if [ "$PROFILE_TYPE" = "gui" ]; then
                sudo pacman -S --needed --noconfirm tk || echo "[!] Couldn't install tk automatically — install it manually for the GUI profile."
            fi
            ;;
        apt)
            sudo apt update
            sudo apt install -y python3 python3-pip python3-venv
            if [ "$PROFILE_TYPE" = "gui" ]; then
                sudo apt install -y python3-tk || echo "[!] Couldn't install python3-tk automatically — install it manually for the GUI profile."
            fi
            # Ollama: try snap or direct install
            if ! command -v ollama &> /dev/null; then
                curl -fsSL https://ollama.com/install.sh | sh 2>/dev/null || \
                echo "[!] Couldn't install Ollama automatically — install it from https://ollama.com"
            fi
            ;;
        apk)
            sudo apk update
            sudo apk add python3 python3-pip python3-dev
            if [ "$PROFILE_TYPE" = "gui" ]; then
                sudo apk add python3-tk || echo "[!] Couldn't install tkinter automatically — install it manually for the GUI profile."
            fi
            # Ollama: Alpine has a community package or we can build from source
            if ! command -v ollama &> /dev/null; then
                echo "[i] Installing Ollama on Alpine..."
                sudo apk add ollama 2>/dev/null || {
                    echo "[!] Ollama not in Alpine repos. Installing from source..."
                    curl -fsSL https://ollama.com/install.sh | sh 2>/dev/null || \
                    echo "[!] Couldn't install Ollama automatically — install it from https://ollama.com"
                }
            fi
            ;;
        xbps-install)
            sudo xbps-install -Syu
            sudo xbps-install -y python python-pip python-virtualenv
            if [ "$PROFILE_TYPE" = "gui" ]; then
                sudo xbps-install -y python-tk || echo "[!] Couldn't install tk automatically — install it manually for the GUI profile."
            fi
            # Ollama: Void has a package
            if ! command -v ollama &> /dev/null; then
                echo "[i] Installing Ollama on Void..."
                sudo xbps-install -y ollama 2>/dev/null || {
                    echo "[!] Ollama not in Void repos. Installing from source..."
                    curl -fsSL https://ollama.com/install.sh | sh 2>/dev/null || \
                    echo "[!] Couldn't install Ollama automatically — install it from https://ollama.com"
                }
            fi
            ;;
        emerge)
            # Gentoo: use portage for Python, ollama from source
            sudo emerge -av python python-pip python-virtualenv
            if [ "$PROFILE_TYPE" = "gui" ]; then
                sudo emerge -av tk || echo "[!] Couldn't install tk automatically — install it manually for the GUI profile."
            fi
            # Ollama: Gentoo has an ebuild or we can use the official installer
            if ! command -v ollama &> /dev/null; then
                echo "[i] Installing Ollama on Gentoo..."
                sudo emerge -av ollama 2>/dev/null || {
                    echo "[!] Ollama not in Gentoo portage. Installing from source..."
                    curl -fsSL https://ollama.com/install.sh | sh 2>/dev/null || \
                    echo "[!] Couldn't install Ollama automatically — install it from https://ollama.com"
                }
            fi
            ;;
        dnf)
            sudo dnf update -y
            sudo dnf install -y python3 python3-pip python3-virtualenv
            if [ "$PROFILE_TYPE" = "gui" ]; then
                sudo dnf install -y python3-tkinter || echo "[!] Couldn't install tkinter automatically — install it manually for the GUI profile."
            fi
            if ! command -v ollama &> /dev/null; then
                curl -fsSL https://ollama.com/install.sh | sh 2>/dev/null || \
                echo "[!] Couldn't install Ollama automatically — install it from https://ollama.com"
            fi
            ;;
        zypper)
            sudo zypper refresh
            sudo zypper install -y python3 python3-pip python3-virtualenv
            if [ "$PROFILE_TYPE" = "gui" ]; then
                sudo zypper install -y python3-tk || echo "[!] Couldn't install tk automatically — install it manually for the GUI profile."
            fi
            if ! command -v ollama &> /dev/null; then
                curl -fsSL https://ollama.com/install.sh | sh 2>/dev/null || \
                echo "[!] Couldn't install Ollama automatically — install it from https://ollama.com"
            fi
            ;;
        *)
            echo "[!] Unknown package manager. Install Python 3, pip, venv and Ollama manually, then re-run."
            exit 1
            ;;
    esac
}
install_system_deps

# 2: Ollama service (systemd / OpenRC / runit / SysV / none — see scripts/init_compat.sh)
echo "[2/4] Enabling Ollama service..."
enable_and_start_service "ollama"

# Point the actual running daemon at this project's MODELS/ folder.
# (Exporting OLLAMA_MODELS in this script's own shell does nothing —
# 'ollama pull' just talks to the daemon over HTTP, and the daemon
# has its own environment set by whatever started it.)
configure_ollama_models_dir "$OLLAMA_MODELS"

# --- 3: venv + packages ---
echo "[3/4] Creating virtual environment..."
if [ ! -d "$PROJECT_DIR/venv" ]; then
    python3 -m venv "$PROJECT_DIR/venv"
fi
source "$PROJECT_DIR/venv/bin/activate"

echo "[4/4] Installing Python packages..."
pip install --upgrade pip setuptools wheel --break-system-packages
pip install -r requirements.txt --break-system-packages

# Profile-specific dependency
if [ "$PROFILE_TYPE" = "discord" ]; then
    echo "[i] Discord profile selected, installing discord.py..."
    pip install discord.py --break-system-packages
fi
if [ "$PROFILE_TYPE" = "gui" ]; then
    echo "[i] GUI profile selected — Tkinter is part of the system Python package"
    echo "    (installed above); if the GUI fails to launch, install your"
    echo "    distro's tk package manually."
fi

# Create and own the MODELS folder
export OLLAMA_MODELS="$PROJECT_DIR/MODELS"
mkdir -p "$OLLAMA_MODELS/blobs" "$OLLAMA_MODELS/manifests"

# Give the ollama user access
sudo chown -R ollama:ollama "$OLLAMA_MODELS" 2>/dev/null || true
sudo chmod -R 755 "$OLLAMA_MODELS"

# Pull model if local = true
if [ "$LOCAL" = "True" ]; then
    echo ""
    while true; do
        echo "[i] Pulling model: $OLLAMA_MODEL"
        if ollama pull "$OLLAMA_MODEL"; then
            break
        fi
        echo -e "${RED}[FATAL]${RESET} Sorry but model that you choosed are not exist, please write other model (or type 'skip' to continue without pulling):"
        read -p "> " NEW_MODEL
        case "$NEW_MODEL" in
            skip) echo "[!] Skipping pull — install it manually later with: ollama pull <model>"; break ;;
            "")   echo "[!] Model name cannot be empty, try again." ;;
            *)    OLLAMA_MODEL="$NEW_MODEL" ;;
        esac
    done
fi

# --- Fix permissions after pull ---
sudo chown -R "$USER:$USER" "$OLLAMA_MODELS" 2>/dev/null || true
sudo chmod -R 755 "$OLLAMA_MODELS"

# Pull vision model if enabled
if [ "$VISION_ENABLED" = "True" ]; then
    while true; do
        echo "[i] Pulling vision model: $VISION_MODEL"
        if ollama pull "$VISION_MODEL"; then
            break
        fi
        echo -e "${RED}[FATAL]${RESET} Sorry but model that you choosed are not exist, please write other model (or type 'skip' to continue without pulling):"
        read -p "> " NEW_VISION_MODEL
        case "$NEW_VISION_MODEL" in
            skip) echo "[!] Skipping pull — install it manually later with: ollama pull <model>"; break ;;
            "")   echo "[!] Model name cannot be empty, try again." ;;
            *)    VISION_MODEL="$NEW_VISION_MODEL" ;;
        esac
    done
fi

echo ""
echo "[i] Applying config..."

# Values are written with Python's repr(), so quotes, backslashes, $, backticks
# and newlines in instructions/keys can't corrupt the files (or inject shell).
export BASE_INSTRUCTION ADMIN_INSTRUCTION GROQ_KEY GROUP_ID LOCAL API OPENROUTER \
       OPENROUTER_KEY OPENROUTER_MODEL OLLAMA_MODEL EMOJI_ENABLED PROFILE_TYPE \
       ADMIN_IDS BANNED_USERS MAT_WORDS BOT_TOKEN DISCORD_TOKEN DISCORD_CHANNEL_ID \
       VISION_ENABLED VISION_MODEL BOT_NAME

python3 - <<'PY'
import os
import re
import shutil
from pathlib import Path

home = Path.cwd()
env = os.environ


def truthy(value):
    return str(value or "").strip().lower() in ("1", "true", "yes", "on", "y")


def ints(value):
    return [int(x) for x in re.findall(r"-?\d+", value or "")]


def set_line(rel, key, literal):
    path = home / rel
    text = path.read_text(encoding="utf-8")
    new_line = f"{key} = {literal!r}"
    text, count = re.subn(rf"(?m)^{re.escape(key)} = .*$", lambda _: new_line, text, count=1)
    if count == 0:
        raise SystemExit(f"[!] Could not find '{key}' in {rel}")
    path.write_text(text, encoding="utf-8", newline="\n")


profile = env.get("PROFILE_TYPE", "").strip().lower()

# --- ai_core.py (shared config, used by every profile) ---
shutil.copy2("ai_core.py", "ai_core.py.backup")
set_line("ai_core.py", "BASE_INSTRUCTION", env.get("BASE_INSTRUCTION", ""))
set_line("ai_core.py", "ADMIN_INSTRUCTION", env.get("ADMIN_INSTRUCTION", ""))
set_line("ai_core.py", "GROQ_KEY", env.get("GROQ_KEY", ""))
set_line("ai_core.py", "GROUP_ID", (ints(env.get("GROUP_ID")) or [0])[0])
set_line("ai_core.py", "LOCAL", truthy(env.get("LOCAL")))
set_line("ai_core.py", "API", truthy(env.get("API")))
set_line("ai_core.py", "OPENROUTER", truthy(env.get("OPENROUTER")))
set_line("ai_core.py", "OPENROUTER_KEY", env.get("OPENROUTER_KEY", ""))
set_line("ai_core.py", "OPENROUTER_MODEL", env.get("OPENROUTER_MODEL") or "openrouter/auto")
set_line("ai_core.py", "OLLAMA_MODEL", env.get("OLLAMA_MODEL", ""))
set_line("ai_core.py", "EMOJI_ENABLED", truthy(env.get("EMOJI_ENABLED")))
# ADMIN_ID: CLI/GUI have no numeric ID, so it stays empty (the local operator
# is trusted regardless of this list).
admin_ids = ints(env.get("ADMIN_IDS")) if profile in ("telegram", "discord") else []
set_line("ai_core.py", "ADMIN_ID", admin_ids)
set_line("ai_core.py", "BANNED", ints(env.get("BANNED_USERS")))
set_line("ai_core.py", "MAT", [w.strip() for w in (env.get("MAT_WORDS") or "").split(",") if w.strip()])
print("[OK] ai_core.py configured")

# --- Bot name substitution (across all profile files) ---
bot_name = env.get("BOT_NAME", "")
for path in sorted((home / "profiles").glob("*.py")):
    text = path.read_text(encoding="utf-8")
    for old in ("арчи", "Арчи", "АРЧИ"):
        text = text.replace(old, bot_name)
    path.write_text(text, encoding="utf-8", newline="\n")

# --- Profile-specific token wiring ---
if profile == "telegram":
    shutil.copy2("profiles/telegram_profile.py", "profiles/telegram_profile.py.backup")
    set_line("profiles/telegram_profile.py", "TOKEN", env.get("BOT_TOKEN", ""))
    print("[OK] profiles/telegram_profile.py configured")
elif profile == "discord":
    shutil.copy2("profiles/discord_profile.py", "profiles/discord_profile.py.backup")
    set_line("profiles/discord_profile.py", "DISCORD_TOKEN", env.get("DISCORD_TOKEN", ""))
    set_line("profiles/discord_profile.py", "DISCORD_ADMIN_ID", ints(env.get("ADMIN_IDS")))
    set_line("profiles/discord_profile.py", "DISCORD_BROADCAST_CHANNEL_ID",
             (ints(env.get("DISCORD_CHANNEL_ID")) or [0])[0])
    print("[OK] profiles/discord_profile.py configured")
else:
    print("[i] CLI/GUI profile - no bot token needed, nothing to configure there.")

# --- Apply vision config ---
if (home / "vision.py").is_file():
    set_line("vision.py", "VISION_ENABLED", truthy(env.get("VISION_ENABLED")))
    set_line("vision.py", "VISION_MODEL", env.get("VISION_MODEL") or "llava:7b")
    print("[OK] vision.py configured")
PY

# --- archie-agent command ---
install_launcher() {
    local tmp; tmp="$(mktemp)"
    sed "s|@PROJECT_DIR@|$PROJECT_DIR|g" "$PROJECT_DIR/scripts/archie-agent.sh" > "$tmp"
    if [ -w /usr/local/bin ] && install -m 755 "$tmp" /usr/local/bin/archie-agent; then :
    elif sudo install -m 755 "$tmp" /usr/local/bin/archie-agent 2>/dev/null \
      || doas install -m 755 "$tmp" /usr/local/bin/archie-agent 2>/dev/null; then :
    else
        mkdir -p "$HOME/.local/bin"
        install -m 755 "$tmp" "$HOME/.local/bin/archie-agent"
        echo "[!] Installed to ~/.local/bin - make sure it's on your PATH."
    fi
    rm -f "$tmp"
    echo "[✓] Command installed: archie-agent"
}
install_launcher

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  [✓] installation success!                               ║"
echo "║                                                          ║"
echo "║  Next: archie-agent --cli   (or ./start.sh)              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
