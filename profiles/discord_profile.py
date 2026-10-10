"""
Archie — Discord Profile
==========================
New. Mirrors the Telegram profile's behavior (admin session mode,
banned users, trigger-word cooldown, broadcast, image description)
using discord.py.

Requires `discord.py` (installed by install.sh when this profile is
selected) and a bot with the "Message Content Intent" enabled in the
Discord Developer Portal — without it, on_message never sees text.

DISCORD_TOKEN / DISCORD_ADMIN_ID / DISCORD_BROADCAST_CHANNEL_ID are
filled in by install.sh from arxh.conf.
"""

import os
import tempfile
import time

import ai_core

DISCORD_TOKEN = "REPLACE_ME_DISCORD_TOKEN"
DISCORD_ADMIN_ID = []
DISCORD_BROADCAST_CHANNEL_ID = 0


def run():
    try:
        import discord
    except ImportError:
        print("[ERROR] discord.py is not installed.")
        print("        Run: pip install discord.py")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print("")
        print(f"[i] Provider: {ai_core.provider_label()}")
        print("[i] Profile: Discord")
        print(f"[✓] Logged in as {client.user}")

    @client.event
    async def on_message(message):
        global_is_crashed = ai_core.is_crashed

        if message.author == client.user:
            return

        uid = message.author.id
        if uid in ai_core.BANNED:
            return

        if message.content.startswith('!'):
            if uid in DISCORD_ADMIN_ID:
                broadcast_txt = message.content[1:].strip()
                channel = client.get_channel(DISCORD_BROADCAST_CHANNEL_ID) or message.channel
                try:
                    await channel.send(broadcast_txt)
                    await message.delete()
                    print(f"\033[95m[BROADCAST]\033[0m Sent: {broadcast_txt}")
                except Exception:
                    pass
                return

        txt = message.content.lower() if message.content else ""

        if global_is_crashed:
            if time.time() - ai_core.crash_time < 30:
                return
            else:
                ai_core.is_crashed = False

        print(f">>> [ID: {uid}] | {message.author.name}: {message.content}")

        if any(r in txt for r in ai_core.MAT):
            await message.reply("[Write text here...]")
            ai_core.is_crashed, ai_core.crash_time = True, time.time()
            return

        is_admin = uid in DISCORD_ADMIN_ID

        if is_admin:
            if "/session admin" in txt:
                ai_core.modes[uid] = "admin"
                await message.reply("[SYSTEM]: Admin mode ON")
                return
            elif "/session normal" in txt:
                ai_core.modes[uid] = "normal"
                await message.reply("[SYSTEM]: Admin mode OFF")
                return

        instr = ai_core.instruction_for(uid, is_admin)
        content = message.content

        # Basic image support via attachments (mirrors Telegram vision handler)
        if message.attachments:
            try:
                from vision import describe_image
                import requests as _requests

                att = message.attachments[0]
                save_path = os.path.join(tempfile.gettempdir(), f"archie_discord_{uid}.jpg")
                r = _requests.get(att.url, timeout=30)
                r.raise_for_status()
                with open(save_path, "wb") as f:
                    f.write(r.content)

                description = describe_image(save_path)
                content = f"[User sent an image. Description: {description}]"
                if message.content:
                    content += f"\n[Caption: {message.content}]"
            except Exception as e:
                print(f"\033[91m[VISION ERROR]\033[0m {e}")

        should_respond = (
            "archie" in txt
            or (is_admin and ai_core.modes.get(uid) == "admin")
            or bool(message.attachments)
        )

        if should_respond:
            try:
                ans = ai_core.run_with_tools(uid, content, instr)
                if ans:
                    await message.reply(ai_core.strip_emoji(ans))
            except Exception as e:
                print(f"Error: {e}")
                await message.reply("[Unable to get a response from the server]")

    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    run()
