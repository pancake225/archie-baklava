"""
Archie — GUI Profile
======================
New. A minimal desktop chat window built with Tkinter (Python's
built-in GUI toolkit — no extra pip dependency, though some minimal
Linux installs need a system package to enable it; see the
ImportError message below). The AI call runs in a background thread
so the window doesn't freeze while waiting for a response.
"""

import threading

import ai_core

GUI_UID = "gui-local-user"


def run():
    try:
        import tkinter as tk
        from tkinter import scrolledtext
    except ImportError:
        print("[ERROR] Tkinter is not installed.")
        print("        Debian/Ubuntu: sudo apt install python3-tk")
        print("        Arch:          sudo pacman -S tk")
        return

    root = tk.Tk()
    root.title("Archie")
    root.geometry("520x640")

    log = scrolledtext.ScrolledText(root, wrap=tk.WORD, state="disabled")
    log.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    entry_frame = tk.Frame(root)
    entry_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

    entry = tk.Entry(entry_frame)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    entry.focus()

    def append_log(who, text):
        log.configure(state="normal")
        log.insert(tk.END, f"{who}: {text}\n\n")
        log.configure(state="disabled")
        log.see(tk.END)

    def send(event=None):
        text = entry.get().strip()
        if not text:
            return
        entry.delete(0, tk.END)
        append_log("you", text)

        if any(r in text.lower() for r in ai_core.MAT):
            append_log("archie", "[Write text here...]")
            return

        def worker():
            instr = ai_core.instruction_for(GUI_UID, True)
            try:
                ans = ai_core.run_with_tools(GUI_UID, text, instr)
                if ans:
                    root.after(0, lambda: append_log("archie", ai_core.strip_emoji(ans)))
            except Exception as e:
                root.after(0, lambda: append_log("[ERROR]", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    send_btn = tk.Button(entry_frame, text="Send", command=send)
    send_btn.pack(side=tk.RIGHT, padx=(6, 0))

    entry.bind("<Return>", send)

    append_log("[SYSTEM]", f"Provider: {'Local (Ollama)' if ai_core.LOCAL else 'Groq API'} | Profile: GUI")

    root.mainloop()


if __name__ == "__main__":
    run()
