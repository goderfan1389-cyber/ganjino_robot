import requests
import json
import time
import os
from config import BASE_URL, JOIN_CHANNEL_USERNAME

session = requests.Session()

def send_message(chat_id, text, reply_markup=None, parse_mode=None, reply_to_message_id=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    if parse_mode: payload["parse_mode"] = parse_mode
    if reply_to_message_id: payload["reply_to_message_id"] = reply_to_message_id
    try: return session.post(f"{BASE_URL}/sendMessage", data=payload, timeout=10)
    except: return None

def edit_message(chat_id, message_id, text, reply_markup=None):
    if not message_id: return
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    try: session.post(f"{BASE_URL}/editMessageText", data=payload, timeout=10)
    except: pass

def answer_callback(cb_id, text="", show_alert=True):
    payload = {"callback_query_id": cb_id}
    if text: payload["text"] = text; payload["show_alert"] = show_alert
    try: session.post(f"{BASE_URL}/answerCallbackQuery", data=payload, timeout=10)
    except: pass

def is_jailed(u): return u['jail_until'] > time.time()

def fa_to_en(s): return s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))

def extract_amount(text, keyword):
    text = fa_to_en(text.strip())
    if not text.startswith(keyword): return None
    rem = text[len(keyword):].strip()
    if not rem: return None
    import re
    num = re.sub(r"[^\d]", "", rem.split()[0])
    return int(num) if num else None

def send_document(chat_id, file_path, caption=None):
    url = f"{BASE_URL}/sendDocument"
    try:
        with open(file_path, "rb") as f:
            payload = {"chat_id": chat_id}
            if caption:
                payload["caption"] = caption
            files = {"document": (os.path.basename(file_path), f)}
            return session.post(url, data=payload, files=files, timeout=30)
    except Exception as e:
        print("send_document error:", e)
        return None
