import threading
import time
from utils import session
from config import BASE_URL
from database import init_db
from handlers import process_message, process_callback
from games import check_expired_games

def safe_process_message(msg):
    try: process_message(msg)
    except Exception as e: print("🔴 ERROR:", e)

def safe_process_callback(cb):
    try: process_callback(cb)
    except Exception as e: print("🔴 ERROR:", e)

def timeout_loop():
    while True:
        try:
            check_expired_games()
        except Exception as e:
            print("Game Timeout Error:", e)
        time.sleep(15) # هر ۱۵ ثانیه یکبار چک میکنه

def main():
    print("Initializing Database...")
    init_db()
    print("Bot is running...")
    
    # استارت ترد تایم‌اوت بازی‌ها
    threading.Thread(target=timeout_loop, daemon=True).start()
    
    offset = None
    while True:
        params = {"timeout": 15}
        if offset: params["offset"] = offset
        try:
            resp = session.get(f"{BASE_URL}/getUpdates", params=params, timeout=20)
            updates = resp.json().get("result", [])
        except:
            time.sleep(2)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            if "message" in update:
                threading.Thread(target=safe_process_message, args=(update["message"],), daemon=True).start()
            elif "callback_query" in update:
                threading.Thread(target=safe_process_callback, args=(update["callback_query"],), daemon=True).start()

if __name__ == "__main__":
    main()
