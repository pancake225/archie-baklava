#!/usr/bin/env python3
"""
Archie — Main Entrypoint
==========================
Reads PROFILE_TYPE (via the ARCHIE_PROFILE_TYPE env var, set by
start.sh from arxh.conf) and launches the matching profile module.
If it's missing — e.g. an old config from before profiles existed —
shows the interactive "select your profile type" menu instead.
"""

import os
import importlib

PROFILE_TYPE = os.environ.get("ARCHIE_PROFILE_TYPE", "").strip().lower()

PROFILES = {
    "telegram": "profiles.telegram_profile",
    "discord": "profiles.discord_profile",
    "cli": "profiles.cli_profile",
    "gui": "profiles.gui_profile",
}


def prompt_for_profile():
    print("[0/10] Before we start: Please select your profile type:")
    print("  1) Telegram")
    print("  2) Discord")
    print("  3) CLI")
    print("  4) GUI")
    choice = input("> ").strip()
    return {
        "1": "telegram",
        "2": "discord",
        "3": "cli",
        "4": "gui",
    }.get(choice, "telegram")


def main():
    profile = PROFILE_TYPE if PROFILE_TYPE in PROFILES else prompt_for_profile()
    module = importlib.import_module(PROFILES[profile])
    module.run()


if __name__ == "__main__":
    main()
