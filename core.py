import telebot, time, requests, base64, os, json
from groq import Groq
from googlesearch import search
import ollama
from vision import describe_image, download_telegram_photo
import re


# ==========================================
#           Provider Flags
# ==========================================
LOCAL = True
API   = False

# Safety check — if both are off, panic
if not LOCAL and not API:
    raise RuntimeError(
        "\033[91m[KERNEL PANIC]\033[0m No AI provider enabled. "
        "Set LOCAL=True or API=True in core.py."
    )

# ==========================================
#            Configurations
# ==========================================
TOKEN = ""
GROQ_KEY = ""

ADMIN_ID = []
BANNED = []
MAT = []
GROUP_ID = 0
EMOJI_ENABLED = False

# Groq config
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Local config
OLLAMA_MODEL = ""

client = Groq(api_key=GROQ_KEY)
bot = telebot.TeleBot(TOKEN)
START_TIME = time.time()

is_crashed = False
crash_time = 0
modes = {}
history = {}

#Instructions
BASE_INSTRUCTION = ""
ADMIN_INSTRUCTION = ""

# ==========================================
#           Search Tool(s)
# ==========================================
def search_internet(query):
    print(f"\033[94m[GOOGLE SEARCH]\033[0m {query}")
    try:
        results = search(query, num_results=3, lang="ru")
        res_list = [str(r) for r in results]
        return "Files from internet:\n" + "\n".join(res_list) if res_list else "I dont find any information."
    except Exception as e:
        return f"Search error: {e}"

# ==========================================
#           Provider Router
# ==========================================
def ask_llm(messages, system_prompt, tools=None):
    """Send a chat request to either Ollama or Groq."""
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    # --- Local Ollama ---
    if LOCAL:
        try:
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=full_messages,
                options={
                    "temperature": 0.8,
                    "top_p": 0.9,
                    "repeat_penalty": 1.15,
                }
            )
            return response['message']['content'], None
        except Exception as e:
            print(f"\033[91m[LOCAL ERROR]\033[0m {e}")
            if not API:
                raise

    # --- Groq API ---
    if API:
        try:
            kwargs = {
                "model": GROQ_MODEL,
                "messages": full_messages,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = client.chat.completions.create(**kwargs)
            msg = response.choices[0].message
            return msg.content, msg.tool_calls
        except Exception as e:
            print(f"\033[91m[API ERROR]\033[0m {e}")
            raise

    raise RuntimeError("[KERNEL PANIC] No provider available.")

def strip_emoji(text):
    """Remove all emoji from text if EMOJI_ENABLED is False."""
    if EMOJI_ENABLED:
        return text
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r"", text)

# ==========================================
#           Handlers
# ==========================================
@bot.message_handler(content_types=['text'])
def handle_text(m):
    global is_crashed, crash_time
    uid = m.from_user.id

    if m.date < START_TIME or uid in BANNED: return

    if m.text and m.text.startswith('!'):
        if uid in ADMIN_ID:
            broadcast_txt = m.text[1:].strip()
            try:
                bot.send_message(GROUP_ID, broadcast_txt)
                bot.delete_message(m.chat.id, m.message_id)
                print(f"\033[95m[BROADCAST]\033[0m Sent: {broadcast_txt}")
            except: pass
            return

    txt = m.text.lower() if m.text else ""

    if is_crashed:
        if time.time() - crash_time < 30: return
        else: is_crashed = False

    print(f">>> [ID: {uid}] | {m.from_user.first_name}: {m.text}")

    if any(r in txt for r in MAT):
        bot.reply_to(m, "[Write text here...]")
        is_crashed, crash_time = True, time.time()
        return

    if uid not in history: history[uid] = []

    if uid in ADMIN_ID:
        if "/session admin" in txt:
            modes[uid] = "admin"
            bot.reply_to(m, "[SYSTEM]: Admin mode ON")
            return
        elif "/session normal" in txt:
            modes[uid] = "normal"
            bot.reply_to(m, "[SYSTEM]: Admin mode OFF")
            return

    is_admin = (uid in ADMIN_ID)
    mode = modes.get(uid, "normal")
    instr = ADMIN_INSTRUCTION if (is_admin and mode == "admin") else BASE_INSTRUCTION

    if "archie" in txt or (is_admin and mode == "admin"):
        history[uid].append({"role": "user", "content": m.text})
        history[uid] = history[uid][-10:]

        try:
            # Tool definition (only used by Groq)
            tools = [{
                "type": "function",
                "function": {
                    "name": "search_internet",
                    "description": "Search in Google",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"]
                    }
                }
            }]

            ans, tool_calls = ask_llm(history[uid], instr, tools=tools if API else None)

            if tool_calls:
                # Groq tool calls
                history[uid].append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls
                })

                for tool in tool_calls:
                    try:
                        args = json.loads(tool.function.arguments)
                        query = args.get("query")
                        res = search_internet(query)
                    except:
                        res = "Error with request passing"

                    history[uid].append({
                        "role": "tool",
                        "tool_call_id": tool.id,
                        "name": "search_internet",
                        "content": res
                    })

                final = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[{"role": "system", "content": instr}] + history[uid]
                )
                ans = final.choices[0].message.content

            if ans:
                bot.reply_to(m, ans)
                history[uid].append({"role": "assistant", "content": ans})

        except Exception as e:
            print(f"Error: {e}")
            bot.reply_to(m, "[Unable to get a response from the server]")

# ==========================================
#          Vision Handler
# ==========================================

@bot.message_handler(content_types=['photo'])
def handle_photo(m):
    uid = m.from_user.id

    if m.date < START_TIME or uid in BANNED:
        return

    if uid not in history:
        history[uid] = []

    # Get largest photo
    photo = m.photo[-1]
    file_id = photo.file_id

    # Download
    save_path = f"/tmp/archie_photo_{uid}.jpg"
    downloaded = download_telegram_photo(bot, file_id, save_path)

    if not downloaded:
        bot.reply_to(m, "[ERROR] Could not download image.")
        return

    bot.reply_to(m, "[i] Analyzing image...")

    # Describe
    description = describe_image(save_path)
    caption = m.caption or ""

    # Build message for LLM
    user_message = f"[User sent an image. Description: {description}]"
    if caption:
        user_message += f"\n[Caption: {caption}]"

    history[uid].append({"role": "user", "content": user_message})
    history[uid] = history[uid][-10:]

    try:
        instr = BASE_INSTRUCTION
        ans, _ = ask_llm(history[uid], instr)

        if ans:
            ans = strip_emoji(ans)
            bot.reply_to(m, ans)
            history[uid].append({"role": "assistant", "content": ans})

    except Exception as e:
        print(f"\033[91m[LLM ERROR]\033[0m {e}")
        bot.reply_to(m, "[ERROR] Could not process image.")

if __name__ == "__main__":
    print("")
    print(f"[i] Provider: {'Local (Ollama)' if LOCAL else 'Groq API'}")
    bot.infinity_polling(skip_pending=True)
