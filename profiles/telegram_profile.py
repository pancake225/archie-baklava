"""
Archie — Telegram Profile
==========================
This is your original core.py bot logic, refactored to pull shared
AI/config/history logic from ai_core so it stays in sync with the
other profiles (Discord/CLI/GUI). Behavior is unchanged.

TOKEN is filled in by install.sh from arxh.conf.
"""

import time

import telebot

import ai_core
from vision import describe_image, download_telegram_photo

TOKEN = "REPLACE_ME_TELEGRAM_TOKEN"


def run():
    bot = telebot.TeleBot(TOKEN)

    # ==========================================
    #           Text Handler
    # ==========================================
    @bot.message_handler(content_types=['text'])
    def handle_text(m):
        uid = m.from_user.id

        if m.date < ai_core.START_TIME or uid in ai_core.BANNED:
            return

        if m.text and m.text.startswith('!'):
            if uid in ai_core.ADMIN_ID:
                broadcast_txt = m.text[1:].strip()
                try:
                    bot.send_message(ai_core.GROUP_ID, broadcast_txt)
                    bot.delete_message(m.chat.id, m.message_id)
                    print(f"\033[95m[BROADCAST]\033[0m Sent: {broadcast_txt}")
                except Exception:
                    pass
                return

        txt = m.text.lower() if m.text else ""

        if ai_core.is_crashed:
            if time.time() - ai_core.crash_time < 30:
                return
            else:
                ai_core.is_crashed = False

        print(f">>> [ID: {uid}] | {m.from_user.first_name}: {m.text}")

        if any(r in txt for r in ai_core.MAT):
            bot.reply_to(m, "[Write text here...]")
            ai_core.is_crashed, ai_core.crash_time = True, time.time()
            return

        is_admin = (uid in ai_core.ADMIN_ID)

        if is_admin:
            if "/session admin" in txt:
                ai_core.modes[uid] = "admin"
                bot.reply_to(m, "[SYSTEM]: Admin mode ON")
                return
            elif "/session normal" in txt:
                ai_core.modes[uid] = "normal"
                bot.reply_to(m, "[SYSTEM]: Admin mode OFF")
                return

        instr = ai_core.instruction_for(uid, is_admin)

        if "archie" in txt or (is_admin and ai_core.modes.get(uid) == "admin"):
            try:
                ans = ai_core.run_with_tools(uid, m.text, instr)
                if ans:
                    bot.reply_to(m, ans)
            except Exception as e:
                print(f"Error: {e}")
                bot.reply_to(m, "[Unable to get a response from the server]")

    # ==========================================
    #          Vision Handler
    # ==========================================
    @bot.message_handler(content_types=['photo'])
    def handle_photo(m):
        uid = m.from_user.id

        if m.date < ai_core.START_TIME or uid in ai_core.BANNED:
            return

        photo = m.photo[-1]
        file_id = photo.file_id

        save_path = f"/tmp/archie_photo_{uid}.jpg"
        downloaded = download_telegram_photo(bot, file_id, save_path)

        if not downloaded:
            bot.reply_to(m, "[ERROR] Could not download image.")
            return

        bot.reply_to(m, "[i] Analyzing image...")

        description = describe_image(save_path)
        caption = m.caption or ""

        user_message = f"[User sent an image. Description: {description}]"
        if caption:
            user_message += f"\n[Caption: {caption}]"

        try:
            ans = ai_core.run_with_tools(uid, user_message, ai_core.BASE_INSTRUCTION)
            if ans:
                ans = ai_core.strip_emoji(ans)
                bot.reply_to(m, ans)
        except Exception as e:
            print(f"\033[91m[LLM ERROR]\033[0m {e}")
            bot.reply_to(m, "[ERROR] Could not process image.")

    print("")
    print(f"[i] Provider: {'Local (Ollama)' if ai_core.LOCAL else 'Groq API'}")
    print("[i] Profile: Telegram")
    bot.infinity_polling(skip_pending=True)


if __name__ == "__main__":
    run()
