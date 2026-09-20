#!/usr/bin/env bash
# ==========================================
#           ARXH INSTALLER
# ==========================================

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
echo "║  > installer :3 • v0.1                                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# --- Check config exists ---
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[!] arxh.conf not found!"
    echo "[i] Run: ./setup.sh first"
    exit 1
fi

# --- Load config ---
echo "[i] Loading config from arxh.conf..."
source "$CONFIG_FILE"
echo "[✓] Loaded: $BOT_NAME | Local=$LOCAL | API=$API"
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
elif command -v apt &> /dev/null; then
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
else
    echo "[!] Unknown package manager."
    exit 1
fi

# 2: Ollama service
echo "[2/4] Enabling Ollama service..."
doas systemctl enable --now ollama 2>/dev/null || sudo systemctl enable --now ollama 2>/dev/null || true

# --- 3: venv + packages ---
echo "[3/4] Creating virtual environment..."
if [ ! -d "$PROJECT_DIR/venv" ]; then
    python3 -m venv "$PROJECT_DIR/venv"
fi
source "$PROJECT_DIR/venv/bin/activate"

echo "[4/4] Installing Python packages..."
pip install --upgrade pip setuptools wheel
pip install -r "$PROJECT_DIR/requirements.txt"

# Pull model if local = true
if [ "$LOCAL" = "True" ]; then
    echo ""
    echo "[i] Pulling model: $OLLAMA_MODEL"
    ollama pull "$OLLAMA_MODEL" || echo "[!] Pull failed. Do it manually later."
fi

echo ""
echo "[i] Apply config to core.py..."

cp core.py core.py.backup

sed -i "s/арчи/$BOT_NAME/g" core.py
sed -i "s/Арчи/$BOT_NAME/g" core.py
sed -i "s/АРЧИ/$BOT_NAME/g" core.py

sed -i "s|^BASE_INSTRUCTION = .*|BASE_INSTRUCTION = \"$BASE_INSTRUCTION\"|" core.py
sed -i "s|^ADMIN_INSTRUCTION = .*|ADMIN_INSTRUCTION = \"$ADMIN_INSTRUCTION\"|" core.py
sed -i "s|^TOKEN = .*|TOKEN = \"$BOT_TOKEN\"|" core.py
sed -i "s|^GROQ_KEY = .*|GROQ_KEY = \"$GROQ_KEY\"|" core.py
sed -i "s|^ADMIN_ID = .*|ADMIN_ID = [$ADMIN_IDS]|" core.py
sed -i "s|^GROUP_ID = .*|GROUP_ID = $GROUP_ID|" core.py
sed -i "s|^LOCAL = .*|LOCAL = $LOCAL|" core.py
sed -i "s|^API   = .*|API   = $API|" core.py
sed -i "s|^API = .*|API = $API|" core.py
sed -i "s|^OLLAMA_MODEL = .*|OLLAMA_MODEL = \"$OLLAMA_MODEL\"|" core.py

echo "[✓] core.py configured"
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  [✓] installation success!                               ║"
echo "║                                                          ║"
echo "║  Next: ./start.sh                                        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""