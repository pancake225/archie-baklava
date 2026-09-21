#!/usr/bin/env bash

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
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║       ██     ██                                          ║"
echo "║                ██                                        ║"
echo "║              ██                                          ║"
echo "║       ██       ██                                        ║"
echo "║              ██                                          ║"
echo "║                                                          ║"
echo "║  > setup wizard • v0.1                                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${RESET}"

#[1/7] User's bot name
echo "[1/9] Write your bot name:"
read -p "> " BOT_NAME
[ -z "$BOT_NAME" ] && echo "[!] Bot name cannot be empty!" && exit 1
echo ""

#[2/7] User's Telegram token
echo "[2/9] Write your Telegram bot token:"
read -p "> " BOT_TOKEN
[ -z "$BOT_TOKEN" ] && echo "[!] Archie needs bot token!" && exit 1
echo ""

#[3/7] Adding user like admin
echo "[3/9] Write your Telegram user ID (admin):"
read -p "> " ADMIN_IDS
[ -z "$ADMIN_IDS" ] && echo "[!] Admin needed!" && exit 1
echo ""

#[4/7] User's group ID 
echo "[4/9] Write your group ID (or leave empty):"
read -p "> " GROUP_ID
[ -z "$GROUP_ID" ] && GROUP_ID="0"
echo ""

#[5/7] Ask provider
echo "[5/9] Choose your AI provider:"
echo "  1) Local (Ollama)"
echo "  2) Groq API"
echo "  3) Both (fallback)"
read -p "> " PROVIDER_CHOICE
case $PROVIDER_CHOICE in
    1) LOCAL="True";  API="False" ;;
    2) LOCAL="False"; API="True"  ;;
    3) LOCAL="True";  API="True"  ;;
    *) LOCAL="True";  API="False" ;;
esac
echo ""

#[6/7] Asking for groq API key (if api selected)
if [ "$API" = "True" ]; then
    echo "[6/9] Write your Groq API key:"
    read -p "> " GROQ_KEY
else
    GROQ_KEY=""
    echo "[6/9] Skipped (API off)"
fi
echo ""

#[7/7] Asking model (if local selected)
if [ "$LOCAL" = "True" ]; then
    echo "[7/9] Write your Ollama model (default: llama3.2):"
    read -p "> " OLLAMA_MODEL
    [ -z "$OLLAMA_MODEL" ] && OLLAMA_MODEL="llama3.2"
else
    OLLAMA_MODEL="llama3.2"
    echo "[7/9] Skipped (local off)"
fi
echo ""

#[8/8] Select instructions
echo "[8/9] Select instructions:"
echo "  1) Just working (neutral assistant)"
echo "  2) Just working, Russian edition"
echo "  3) Silly (You weirdo why you need silly assistant but okay"
echo "  4) Skip this step (warning: you will need create instruction yourself)"
read -p "> " INSTR_CHOICE

case $INSTR_CHOICE in
    1)
        BASE_INSTRUCTION="You are a helpful, neutral assistant. Answer concisely and clearly."
        ADMIN_INSTRUCTION="You are in ADMINISTRATOR mode. Speak seriously and directly."
        ;;
    2)
        BASE_INSTRUCTION="Ты полезный, нейтральный ассистент. Отвечай кратко и понятно."
        ADMIN_INSTRUCTION="Ты в режиме АДМИНИСТРАТОРА. Говори серьёзно и прямо."
        ;;
    3)
        BASE_INSTRUCTION="You are a silly, chaotic, and slightly unhinged assistant. Use CAPS randomly. Be weird but helpful. You love your life and being silly"
        ADMIN_INSTRUCTION="You are in ADMINISTRATOR mode. Even here, you're a little silly, but you get the job done."
        ;;
    4)
        BASE_INSTRUCTION=""
        ADMIN_INSTRUCTION=""
        echo "[!] Instructions skipped. Edit core.py manually."
        ;;
    *)
        BASE_INSTRUCTION="You are a helpful, neutral assistant."
        ADMIN_INSTRUCTION="You are in ADMINISTRATOR mode."
        ;;
esac
echo ""

#[9/9] Enable vision?
echo "[9/9] Enable vision (image description)?"
echo "  1) Yes (requires LLaVA or Qwen2-VL)"
echo "  2) No"
read -p "> " VISION_CHOICE

case $VISION_CHOICE in
    1) VISION_ENABLED="True";  VISION_MODEL="llava:7b" ;;
    2) VISION_ENABLED="False"; VISION_MODEL="llava:7b" ;;
    *) VISION_ENABLED="False"; VISION_MODEL="llava:7b" ;;
esac
echo ""

# ==========================================
#           EXTRA CONFIGURATION
# ==========================================
echo "[9/9] Configuration Finished! Do you wanna extra configure? [y/n]"
read -p "> " EXTRA_CHOICE

# --- Defaults ---
EMOJI_ENABLED="True"
BANNED_USERS=""
MAT_WORDS=""

if [[ "$EXTRA_CHOICE" =~ ^[Yy]$ ]]; then
    echo ""

    # --- Emoji toggle ---
    echo "{extra/9} Enable emoji? [y/n]"
    read -p "> " EMOJI_CHOICE
    [[ "$EMOJI_CHOICE" =~ ^[Nn]$ ]] && EMOJI_ENABLED="False" || EMOJI_ENABLED="True"
    echo ""

    # --- Banned users ---
    echo "{extra/9} Wanna add banned users? [y/n]"
    read -p "> " BAN_CHOICE
    if [[ "$BAN_CHOICE" =~ ^[Yy]$ ]]; then
        while true; do
            echo "{extra/banned-users}"
            echo "Write banned user's UID (or 'done' to finish):"
            read -p "> " BAN_UID
            [ "$BAN_UID" = "done" ] && break
            [ -z "$BAN_UID" ] && continue
            [ -z "$BANNED_USERS" ] && BANNED_USERS="$BAN_UID" || BANNED_USERS="$BANNED_USERS,$BAN_UID"
            echo "[✓] Added: $BAN_UID"
        done
    fi
    echo ""

    # --- MAT words (trigger words) ---
    echo "{extra/9} Wanna add trigger words (model gets angry)? [y/n]"
    read -p "> " MAT_CHOICE
    if [[ "$MAT_CHOICE" =~ ^[Yy]$ ]]; then
        while true; do
            echo "{extra/mat}"
            echo "Write trigger word (or 'done' to finish):"
            read -p "> " MAT_WORD
            [ "$MAT_WORD" = "done" ] && break
            [ -z "$MAT_WORD" ] && continue
            [ -z "$MAT_WORDS" ] && MAT_WORDS="$MAT_WORD" || MAT_WORDS="$MAT_WORDS,$MAT_WORD"
            echo "[✓] Added: $MAT_WORD"
        done
    fi
    echo ""
fi

# ==========================================
#           WRITE CONFIG
# ==========================================
cat > "$CONFIG_FILE" << EOF
# ==========================================
#           ARXH CONFIG
# ==========================================
# Generated by setup.sh

BOT_NAME="$BOT_NAME"
BOT_TOKEN="$BOT_TOKEN"
ADMIN_IDS="$ADMIN_IDS"
GROUP_ID="$GROUP_ID"
LOCAL="$LOCAL"
API="$API"
GROQ_KEY="$GROQ_KEY"
OLLAMA_MODEL="$OLLAMA_MODEL"
BASE_INSTRUCTION="$BASE_INSTRUCTION"
ADMIN_INSTRUCTION="$ADMIN_INSTRUCTION"
VISION_ENABLED="$VISION_ENABLED"
VISION_MODEL="$VISION_MODEL"
EMOJI_ENABLED="$EMOJI_ENABLED"
BANNED_USERS="$BANNED_USERS"
MAT_WORDS="$MAT_WORDS"
EOF

echo "[✓] Config saved to: $CONFIG_FILE"
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  [✓] Setup success                                       ║"
echo "║                                                          ║"
echo "║  Next: ./install.sh                                      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "WARNING: install.sh will run in 10 seconds!"
sleep 10
bash ./install.sh