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
if command -v pacman &> /dev/null; then
    sudo pacman -Sy --needed --noconfirm python python-pip python-virtualenv ollama
    if [ "$PROFILE_TYPE" = "gui" ]; then
        sudo pacman -S --needed --noconfirm tk || echo "[!] Couldn't install tk automatically — install it manually for the GUI profile."
    fi
elif command -v apt &> /dev/null; then
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
    if [ "$PROFILE_TYPE" = "gui" ]; then
        sudo apt install -y python3-tk || echo "[!] Couldn't install python3-tk automatically — install it manually for the GUI profile."
    fi
else
    echo "[!] Unknown package manager. Install Python 3, pip, venv and Ollama manually, then re-run."
    exit 1
fi

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

# --- ai_core.py (shared config, used by every profile) ---
cp ai_core.py ai_core.py.backup

sed -i "s|^BASE_INSTRUCTION = .*|BASE_INSTRUCTION = \"$BASE_INSTRUCTION\"|" ai_core.py
sed -i "s|^ADMIN_INSTRUCTION = .*|ADMIN_INSTRUCTION = \"$ADMIN_INSTRUCTION\"|" ai_core.py
sed -i "s|^GROQ_KEY = .*|GROQ_KEY = \"$GROQ_KEY\"|" ai_core.py
sed -i "s|^GROUP_ID = .*|GROUP_ID = $GROUP_ID|" ai_core.py
sed -i "s|^LOCAL = .*|LOCAL = $LOCAL|" ai_core.py
sed -i "s|^API = .*|API = $API|" ai_core.py
sed -i "s|^OPENROUTER = .*|OPENROUTER = ${OPENROUTER:-False}|" ai_core.py
sed -i "s|^OPENROUTER_KEY = .*|OPENROUTER_KEY = \"${OPENROUTER_KEY:-}\"|" ai_core.py
sed -i "s|^OPENROUTER_MODEL = .*|OPENROUTER_MODEL = \"${OPENROUTER_MODEL:-openrouter/auto}\"|" ai_core.py
sed -i "s|^OLLAMA_MODEL = .*|OLLAMA_MODEL = \"$OLLAMA_MODEL\"|" ai_core.py
sed -i "s|^EMOJI_ENABLED = .*|EMOJI_ENABLED = $EMOJI_ENABLED|" ai_core.py

# ADMIN_ID: for cli/gui there's no numeric Telegram/Discord ID, so leave it empty
# (the CLI/GUI profiles treat the local operator as trusted regardless of this list)
if [ "$PROFILE_TYPE" = "telegram" ] || [ "$PROFILE_TYPE" = "discord" ]; then
    sed -i "s|^ADMIN_ID = .*|ADMIN_ID = [$ADMIN_IDS]|" ai_core.py
else
    sed -i "s|^ADMIN_ID = .*|ADMIN_ID = []|" ai_core.py
fi

sed -i "s|^BANNED = .*|BANNED = [$BANNED_USERS]|" ai_core.py

if [ -n "$MAT_WORDS" ]; then
    MAT_FORMATTED=$(echo "$MAT_WORDS" | sed "s/,/','/g")
    sed -i "s|^MAT = .*|MAT = ['$MAT_FORMATTED']|" ai_core.py
else
    sed -i "s|^MAT = .*|MAT = []|" ai_core.py
fi

echo "[✓] ai_core.py configured"

# --- Bot name substitution (across all profile files) ---
for f in profiles/*.py; do
    sed -i "s/арчи/$BOT_NAME/g; s/Арчи/$BOT_NAME/g; s/АРЧИ/$BOT_NAME/g" "$f"
done

# --- Profile-specific token wiring ---
if [ "$PROFILE_TYPE" = "telegram" ]; then
    cp profiles/telegram_profile.py profiles/telegram_profile.py.backup
    sed -i "s|^TOKEN = .*|TOKEN = \"$BOT_TOKEN\"|" profiles/telegram_profile.py
    echo "[✓] profiles/telegram_profile.py configured"
elif [ "$PROFILE_TYPE" = "discord" ]; then
    cp profiles/discord_profile.py profiles/discord_profile.py.backup
    sed -i "s|^DISCORD_TOKEN = .*|DISCORD_TOKEN = \"$DISCORD_TOKEN\"|" profiles/discord_profile.py
    sed -i "s|^DISCORD_ADMIN_ID = .*|DISCORD_ADMIN_ID = [$ADMIN_IDS]|" profiles/discord_profile.py
    sed -i "s|^DISCORD_BROADCAST_CHANNEL_ID = .*|DISCORD_BROADCAST_CHANNEL_ID = ${DISCORD_CHANNEL_ID:-0}|" profiles/discord_profile.py
    echo "[✓] profiles/discord_profile.py configured"
else
    echo "[i] CLI/GUI profile — no bot token needed, nothing to configure there."
fi

# --- Apply vision config ---
if [ -f "$PROJECT_DIR/vision.py" ]; then
    sed -i "s|^VISION_ENABLED = .*|VISION_ENABLED = $VISION_ENABLED|" vision.py
    sed -i "s|^VISION_MODEL = .*|VISION_MODEL = \"$VISION_MODEL\"|" vision.py
    echo "[✓] vision.py configured"
fi

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