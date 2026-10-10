#!/usr/bin/env bash
# ==========================================
#           ARXH LAUNCHER
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
echo "║  >  starter     • v0.5                                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${RESET}"

#Check config
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[!] arxh.conf not found!"
    echo "[i] Run: ./setup.sh && ./install.sh first"
    exit 1
fi

source "$CONFIG_FILE"
PROFILE_TYPE="${PROFILE_TYPE:-}"   # empty means: let main.py ask interactively

#Ollama models folder
export OLLAMA_MODELS="$PROJECT_DIR/MODELS"
echo "[i] Models folder: $OLLAMA_MODELS"

#Check venv
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "[!] venv not found!"
    echo "[i] Run: ./install.sh first"
    exit 1
fi
source "$PROJECT_DIR/venv/bin/activate"

#Check Ollama if LOCAL (works across systemd / OpenRC / runit / SysV / no init system)
if [ "$LOCAL" = "True" ]; then
    echo "[i] LOCAL mode. Checking Ollama..."
    start_service_if_needed "ollama"
    echo "[✓] Ollama is running"
fi

# Check Vision model if enabled
if [ "$VISION_ENABLED" = "True" ]; then
    echo "[i] Vision enabled. Checking model: $VISION_MODEL"
    if ! ollama list | grep -q "$VISION_MODEL"; then
        echo "[!] Vision model not found. Pulling..."
        ollama pull "$VISION_MODEL" || echo "[!] Pull failed."
    fi
    echo "[✓] Vision model ready"
fi

#Check Groq key if API
if [ "$API" = "True" ]; then
    echo "[i] API mode. Checking Groq key..."
    if [ -z "$GROQ_KEY" ] && [ -z "$GROQ_API_KEY" ]; then
        echo "[!] GROQ_KEY is empty!"
    else
        echo "[✓] Groq key detected"
    fi
fi

#Check OpenRouter key if enabled
if [ "$OPENROUTER" = "True" ]; then
    echo "[i] OpenRouter mode. Checking key..."
    if [ -z "$OPENROUTER_KEY" ] && [ -z "$OPENROUTER_API_KEY" ]; then
        echo "[!] OPENROUTER_KEY is empty!"
    else
        echo "[✓] OpenRouter key detected"
    fi
fi

echo ""
echo "[i] Starting $BOT_NAME (profile: ${PROFILE_TYPE:-not set, will ask})..."
echo ""
export ARCHIE_PROFILE_TYPE="$PROFILE_TYPE"
python3 "$PROJECT_DIR/main.py"
