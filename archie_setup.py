#!/usr/bin/env python3
"""
Archie setup wizard (cross-platform)
====================================
Same questions as setup.sh, but works on Windows too. Writes arxh.conf in
the same KEY="value" format, so setup.sh / install.sh / start.sh keep working.
"""

import sys
from pathlib import Path

HOME = Path(__file__).resolve().parent
CONF = HOME / "arxh.conf"

INSTRUCTIONS = {
    1: ("You are a helpful, neutral assistant. Answer concisely and clearly.",
        "You are in ADMINISTRATOR mode. Speak seriously and directly."),
    2: ("Ты полезный, нейтральный ассистент. Отвечай кратко и понятно.",
        "Ты в режиме АДМИНИСТРАТОРА. Говори серьёзно и прямо."),
    3: ("You are a silly, chaotic, and slightly unhinged assistant. Use CAPS randomly. "
        "Be weird but helpful. You love your life and being silly",
        "You are in ADMINISTRATOR mode. Even here, you're a little silly, but you get the job done."),
    4: ("", ""),
}


def ask(prompt, default=None, required=False):
    while True:
        val = input(f"{prompt}\n> ").strip()
        if val:
            return val
        if default is not None:
            return default
        if not required:
            return ""
        print("[!] This can't be empty.")


def choose(prompt, options, default=1):
    print(prompt)
    for i, label in enumerate(options, 1):
        print(f"  {i}) {label}")
    val = input("> ").strip()
    return int(val) if val.isdigit() and 1 <= int(val) <= len(options) else default


def yes(prompt):
    return input(f"{prompt} [y/n]\n> ").strip().lower().startswith("y")


def collect_list(title, prompt):
    items = []
    while True:
        print(f"{{{title}}}")
        v = input(f"{prompt} (or 'done' to finish):\n> ").strip()
        if v == "done":
            return items
        if v:
            items.append(v)
            print(f"[OK] Added: {v}")


def q(value):
    """Escape so the file stays valid when sourced by bash."""
    for ch in ("\\", '"', "$", "`"):
        value = value.replace(ch, "\\" + ch)
    return f'"{value}"'


def main():
    print("== Archie setup wizard ==\n")
    profile = {1: "telegram", 2: "discord", 3: "cli", 4: "gui"}[
        choose("[0/10] Select your profile type:", ["Telegram", "Discord", "CLI", "GUI"], 1)]
    print(f"[OK] Profile: {profile}\n")

    bot_name = ask("[1/10] Write your bot name:", required=True)

    bot_token = discord_token = ""
    if profile == "telegram":
        bot_token = ask("[2/10] Write your Telegram bot token:", required=True)
    elif profile == "discord":
        discord_token = ask("[2/10] Write your Discord bot token:", required=True)

    admin_ids, group_id = "local", "0"
    if profile in ("telegram", "discord"):
        admin_ids = ask(f"[3/10] Write your {profile.capitalize()} user ID (admin):", required=True)
        group_id = ask("[4/10] Write your group/broadcast channel ID (or leave empty):", default="0")

    prov = choose("[5/10] Choose your AI provider:",
                  ["Local (Ollama)", "Groq API", "Both (Ollama + Groq fallback)",
                   "OpenRouter", "Local + OpenRouter (fallback)"], 1)
    local, api, openrouter = {
        1: ("True", "False", "False"), 2: ("False", "True", "False"), 3: ("True", "True", "False"),
        4: ("False", "False", "True"), 5: ("True", "False", "True"),
    }[prov]

    groq_key = ask("[6/10] Write your Groq API key:", required=True) if api == "True" else ""
    openrouter_key, openrouter_model = "", "openrouter/auto"
    if openrouter == "True":
        openrouter_key = ask("[6b/10] Write your OpenRouter API key:", required=True)
        openrouter_model = ask("[6b/10] OpenRouter model (default: openrouter/auto):", default="openrouter/auto")
    ollama_model = ask("[7/10] Write your Ollama model (default: llama3.2):", default="llama3.2") \
        if local == "True" else "llama3.2"

    instr = choose("[8/10] Select instructions:",
                   ["Just working (neutral assistant)", "Just working, Russian edition",
                    "Silly", "Skip (you'll write the instruction yourself)"], 1)
    base_instr, admin_instr = INSTRUCTIONS[instr]

    vision_enabled = "True" if choose("[9/10] Enable vision (image description)?",
                                      ["Yes (needs LLaVA or similar)", "No"], 2) == 1 else "False"

    emoji, banned, mat, discord_channel = "True", [], [], "0"
    if yes("[10/10] Configuration finished! Do you wanna extra configure?"):
        emoji = "True" if yes("{extra} Enable emoji?") else "False"
        if yes("{extra} Wanna add banned users?"):
            banned = collect_list("extra/banned-users", "Write banned user's UID")
        if yes("{extra} Wanna add trigger words (model gets angry)?"):
            mat = collect_list("extra/mat", "Write trigger word")
        if profile == "discord":
            discord_channel = ask("{extra} Discord broadcast channel ID (or leave empty):", default="0")

    # Permission defaults for archie-agent. Flags on the command line override these.
    values = [
        ("PROFILE_TYPE", profile), ("BOT_NAME", bot_name), ("BOT_TOKEN", bot_token),
        ("DISCORD_TOKEN", discord_token), ("DISCORD_CHANNEL_ID", discord_channel),
        ("ADMIN_IDS", admin_ids), ("GROUP_ID", group_id), ("LOCAL", local), ("API", api), ("OPENROUTER", openrouter),
        ("GROQ_KEY", groq_key),
        ("OPENROUTER_KEY", openrouter_key), ("OPENROUTER_MODEL", openrouter_model), ("OLLAMA_MODEL", ollama_model),
        ("BASE_INSTRUCTION", base_instr), ("ADMIN_INSTRUCTION", admin_instr),
        ("VISION_ENABLED", vision_enabled), ("VISION_MODEL", "llava:7b"),
        ("EMOJI_ENABLED", emoji), ("BANNED_USERS", ",".join(banned)), ("MAT_WORDS", ",".join(mat)),
    ]
    lines = ["# ==========================================",
             "#           ARXH CONFIG",
             "# ==========================================",
             "# Generated by archie_setup.py", ""]
    lines += [f"{k}={q(v)}" for k, v in values]
    CONF.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    print(f"\n[OK] Config saved to: {CONF}")
    print("Next: install.ps1 (Windows) or ./install.sh (Linux)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\n[!] Cancelled.")
        sys.exit(1)
