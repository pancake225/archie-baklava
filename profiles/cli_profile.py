"""
Archie — CLI Profile
======================
New. A local terminal chat interface — no Telegram/Discord token
needed. Useful for headless boxes, debugging, or a non-systemd/
non-daemon setup where you just want to talk to Archie directly.
"""

import ai_core

CLI_UID = "cli-local-user"


def run():
    print("")
    print(f"[i] Provider: {'Local (Ollama)' if ai_core.LOCAL else 'Groq API'}")
    print("[i] Profile: CLI")
    print("[i] Type your message and press Enter. Commands:")
    print("    /session admin   - switch to admin instruction mode")
    print("    /session normal  - switch back to normal mode")
    print("    /image <path>    - describe a local image (requires vision model)")
    print("    exit | quit      - leave")
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
                description = describe_image(path)
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
