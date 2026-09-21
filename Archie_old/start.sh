#!/usr/bin/env bash

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

CONFIG_FILE="$PROJECT_DIR/arxh.conf"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║       ██     ██                                          ║"
echo "║                ██                                        ║"
echo "║              ██                                          ║"
echo "║       ██       ██                                        ║"
echo "║              ██                                          ║"
echo "║                                                          ║"
echo "║  > starter :3   • v0.1                                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

#Check config
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[!] arxh.conf not found!"
    echo "[i] Run: ./setup.sh && ./install.sh first"
    exit 1
fi

source "$CONFIG_FILE"

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

#Check Ollama if LOCAL
if [ "$LOCAL" = "True" ]; then
    echo "[i] LOCAL mode. Checking Ollama..."
    if ! systemctl is-active --quiet ollama; then
        echo "[!] Starting Ollama..."
        doas systemctl start ollama 2>/dev/null || sudo systemctl start ollama
        sleep 2
    fi
    echo "[✓] Ollama is running"
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

echo ""
echo "[i] Starting $BOT_NAME..."
echo ""
python3 "$PROJECT_DIR/core.py"
