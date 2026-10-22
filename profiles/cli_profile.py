"""
Archie — CLI Profile
======================
A local terminal chat interface — no Telegram/Discord token needed.
Useful for headless boxes, debugging, or a non-daemon setup where you
just want to talk to Archie directly.
"""

from pathlib import Path

import agent_tools
import ai_core

CLI_UID = "cli-local-user"


def _print_help():
    print("    /session admin   - switch to admin instruction mode")
    print("    /session normal  - switch back to normal mode")
    print("    /image <path>    - describe a local image (requires vision model)")
    print("    /tools           - show tools enabled for this session")
    print("    /history         - show recent conversation history")
    print("    /clear           - forget the current conversation")
    print("    exit | quit      - leave")


def _print_tools():
    names = [t["function"]["name"] for t in agent_tools.tool_schemas()]
    if not names:
        print("[i] No tools enabled. Restart with --allow-access-to-files, "
              "--allow-access-to-internet, --allow-access-to-apply, --allow-shell "
              "or --allow-email.")
        return
    print("[i] Enabled tools: " + ", ".join(names))


def _print_history():
    entries = ai_core.history.get(CLI_UID) or []
    if not entries:
        print("[i] No history yet.")
        return
    for msg in entries[-6:]:
        who = "you" if msg.get("role") == "user" else "archie"
        content = str(msg.get("content") or "").replace("\n", " ")
        print(f"{who}> {content[:500]}")


def run():
    print("")
    print(f"[i] Provider: {ai_core.provider_label()} | mode: {ai_core.mode_label()}")
    print("[i] Profile: CLI")
    print("[i] Type your message and press Enter. Commands:")
    _print_help()
    print("")

    is_admin = True  # local terminal access = trusted operator

    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[i] Bye.")
            break

        if not text:
            continue

        if text.lower() in ("exit", "quit"):
            print("[i] Bye.")
            break

        if text == "/help":
            _print_help()
            continue

        if text == "/tools":
            _print_tools()
            continue

        if text == "/history":
            _print_history()
            continue

        if text == "/clear":
            ai_core.history.pop(CLI_UID, None)
            print("[SYSTEM]: Conversation cleared")
            continue

        if text == "/session admin":
            ai_core.modes[CLI_UID] = "admin"
            print("[SYSTEM]: Admin mode ON")
            continue
        elif text == "/session normal":
            ai_core.modes[CLI_UID] = "normal"
            print("[SYSTEM]: Admin mode OFF")
            continue

        if text.startswith("/image "):
            path = text[len("/image "):].strip()
            try:
                from vision import describe_image
                image_path = Path(path).expanduser()
                if not image_path.is_absolute():
                    image_path = agent_tools.PERMS.workdir / image_path
                description = describe_image(str(image_path))
                text = f"[User sent an image. Description: {description}]"
            except Exception as e:
                print(f"[ERROR] Could not process image: {e}")
                continue

        if any(r in text.lower() for r in ai_core.MAT):
            print("archie> [Write text here...]")
            continue

        instr = ai_core.instruction_for(CLI_UID, is_admin)

        try:
            ans = ai_core.run_with_tools(CLI_UID, text, instr)
            if ans:
                print(f"archie> {ai_core.strip_emoji(ans)}")
        except Exception as e:
            print(f"[ERROR] Unable to get a response: {e}")


if __name__ == "__main__":
    run()
