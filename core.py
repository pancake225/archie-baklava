import telebot, time, requests, base64, os, json
from groq import Groq
from googlesearch import search
import ollama

# ==========================================
#           PROVIDER FLAGS
# ==========================================
LOCAL = False   # Use local Ollama
API   = True    # Use Groq API

# Safety check — if both are off, panic
if not LOCAL and not API:
    raise RuntimeError(
        "\033[91m[KERNEL PANIC]\033[0m No AI provider enabled. "
        "Set LOCAL=True or API=True in archie_7.0.py."
    )

# ==========================================
#           CONFIG
# ==========================================
TOKEN = "" #Telegram Token
GROQ_KEY = "" #Groq api token

ADMIN_ID = [6493585504, 8571414006]
BANNED = [7753558839]
MAT = []
GROUP_ID = -1002673502908

# Groq config
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Local config
OLLAMA_MODEL = "arxh-model"

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
#           INTERNET SEARCH TOOL
# ==========================================
def search_internet(query):
    print(f"\033[94m[GOOGLE SEARCH]\033[0m {query}")
    try:
        results = search(query, num_results=3, lang="ru")
        res_list = [str(r) for r in results]
        return "Данные из интернета:\n" + "\n".join(res_list) if res_list else "Ничего не найдено."
    except Exception as e:
        return f"Ошибка поиска: {e}"

# ==========================================
#           PROVIDER ROUTER
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

# ==========================================
#           HANDLERS
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
        bot.reply_to(m, "[вы меня обидели я не куплю вам шоколадных орешков]")
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

    if "арчи" in txt or (is_admin and mode == "admin"):
        history[uid].append({"role": "user", "content": m.text})
        history[uid] = history[uid][-10:]

        try:
            # Tool definition (only used by Groq)
            tools = [{
                "type": "function",
                "function": {
                    "name": "search_internet",
                    "description": "Поиск в Google",
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
                        res = "Ошибка парсинга запроса."

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
            print(f"Ошибка: {e}")
            bot.reply_to(m, "[Unable to get a response from the server]")

if __name__ == "__main__":
    print("")
    print(f"[i] Provider: {'Local (Ollama)' if LOCAL else 'Groq API'}")
    bot.infinity_polling(skip_pending=True)