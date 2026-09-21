#!/usr/bin/env python3
"""
Archie Vision Module
Handles image downloading and description using a vision model.
"""

import os
import requests
import ollama

# ==========================================
#           CONFIG
# ==========================================
VISION_ENABLED = True
VISION_MODEL = "llava:7b"

# ==========================================
#           DESCRIBE IMAGE
# ==========================================
def describe_image(image_path):
    """Describe an image using the vision model."""
    if not VISION_ENABLED:
        return "[VISION DISABLED]"

    if not os.path.exists(image_path):
        return f"[ERROR] Image not found: {image_path}"

    try:
        response = ollama.chat(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": "Describe this image in detail. What objects, people, text, or scenes do you see?",
                "images": [image_path]
            }]
        )
        return response['message']['content']
    except Exception as e:
        print(f"\033[91m[VISION ERROR]\033[0m {e}")
        return f"[VISION ERROR] {e}"


def download_telegram_photo(bot, file_id, save_path):
    """Download a photo from Telegram."""
    try:
        file_info = bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
        response = requests.get(file_url, timeout=30)
        response.raise_for_status()

        with open(save_path, "wb") as f:
            f.write(response.content)

        return save_path
    except Exception as e:
        print(f"\033[91m[DOWNLOAD ERROR]\033[0m {e}")
        return None