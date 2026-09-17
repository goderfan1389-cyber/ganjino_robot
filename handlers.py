import time
import random
from utils import send_message, answer_callback, is_jailed, extract_amount
from database import get_conn, release_conn, get_user, update_user
from config import CLAIM_COOLDOWN, STEAL_COOLDOWN, STEAL_WARNINGS_LIMIT, JAIL_SECONDS, JAIL_RANSOM, ITEMS
from admin import handle_admin_commands

START_TEXT = "🤖 به ربات طلا خوش آمدید!\nبرای دیدن موجودی خود بنویسید: کیف"
SHOP_TEXT = """🛒 فروشگاه ربات:

🛡 سپر — 100 طلا
🔪 چاقو — 100 طلا
🎭 ماسک — 100 طلا
🧲 آهنربا — 100 طلا
🎫 بلیط آزادی — 47 طلا

برای خرید: خرید [نام آیتم]"""

def process_message(msg):
    try:
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")
        user = msg.get("from", {})
        user_id = user.get("id")
        chat_type = msg.get("chat", {}).get("type", "private")
        reply_id = msg["message_id"] if chat_type in ("group", "supergroup") else None

        if not text or user_id is None: return
        
        conn = get_conn()
        u = get_user(user_id, conn)
        
        if u['name'] != user.get("first_name", "کاربر"):
            update_user(user_id, {"name": user.get("first_name", "کاربر")}, conn)

        if handle_admin_commands(msg, u, conn, reply_id):
            release_conn(conn)
            return

        stripped = text.strip()

        if stripped == "/start":
            send_message(chat_id, START_TEXT, reply_to_message_id=reply_id)

        elif stripped == "کیف":
            items_str = "\n".join([f"{ITEMS[k]['emoji']} {k} × {v}" for k, v in u['items'].items()])
            if not items_str: items_str = "خالی"
            send_message(chat_id, f"💼 کیف طلا:\n\n🪙 کیسه طلا: {u['gold']:,}\n🏦 خزانه: {u['bank']:,}\n\n🎒 آیتم‌ها:\n{items_str}", reply_to_message_id=reply_id)

        elif stripped == "طلا":
            if is_jailed(u):
                send_message(chat_id, "🚔 در زندان هستید!", reply_to_message_id=reply_id); release_conn(conn); return
            now = time.time()
            if now - u['last_claim'] < CLAIM_COOLDOWN:
                send_message(chat_id, "🔴 هنوز وقت دریافت طلا نرسیده!", reply_to_message_id=reply_id); release_conn(conn); return
            amount = random.randint(80, 250)
            update_user(user_id, {"gold": u['gold'] + amount, "last_claim": now}, conn)
            send_message(chat_id, f"💰 شما {amount} طلا گرفتید!", reply_to_message_id=reply_id)

        elif stripped == "روزانه":
            if is_jailed(u):
                send_message(chat_id, "🚔 در زندان هستید!", reply_to_message_id=reply_id); release_conn(conn); return
            now = time.time()
            if now - u.get('last_daily', 0) < 86400:
                send_message(chat_id, "🔴 هنوز وقت دریافت جایزه روزانه نرسیده!", reply_to_message_id=reply_id); release_conn(conn); return
            amount = random.randint(300, 800)
            update_user(user_id, {"gold": u['gold'] + amount, "last_daily": now}, conn)
            send_message(chat_id, f"🎁 جایزه روزانه شما: {amount} طلا!", reply_to_message_id=reply_id)

        elif stripped == "دزدی":
            if is_jailed(u):
                send_message(chat_id, "🚔 در زندان هستید!", reply_to_message_id=reply_id); release_conn(conn); return

            reply_to = msg.get("reply_to_message")
            if not reply_to:
                send_message(chat_id, "ریپلای کن روی فرد و دزدی بزن.", reply_to_message_id=reply_id); release_conn(conn); return

            target_id = reply_to.get("from", {}).get("id")
            if target_id == user_id:
                send_message(chat_id, "نمیتونی از خودت بدزنی!", reply_to_message_id=reply_id); release_conn(conn); return

            now = time.time()
            if now - u['last_steal'] < STEAL_COOLDOWN:
                warnings = u['steal_warnings'] + 1
                if warnings >= STEAL_WARNINGS_LIMIT:
                    update_user(user_id, {"jail_until": now + JAIL_SECONDS, "steal_warnings": 0}, conn)
                    send_message(chat_id, f"🚔 پافشاری کردی! زندان 10 دقیقه. فدیه: {JAIL_RANSOM} طلا", reply_to_message_id=reply_id)
                else:
                    update_user(user_id, {"steal_warnings": warnings}, conn)
                    send_message(chat_id, f"⏳ 30 ثانیه نرفته! اخطار {warnings} از {STEAL_WARNINGS_LIMIT}.", reply_to_message_id=reply_id)
                release_conn(conn); return

            target = get_user(target_id, conn)
            if target['gold'] <= 0:
                send_message(chat_id, "این کاربر طلا نداره!", reply_to_message_id=reply_id); release_conn(conn); return

            steal_amount = min(random.randint(30, 100), target['gold'])
            update_user(target_id, {"gold": target['gold'] - steal_amount}, conn)
            update_user(user_id, {"gold": u['gold'] + steal_amount, "last_steal": now, "steal_warnings": 0}, conn)
            send_message(chat_id, f"🥷 دزدی موفق! {steal_amount} طلا گرفتی.", reply_to_message_id=reply_id)

        elif stripped == "فروشگاه":
            send_message(chat_id, SHOP_TEXT, reply_to_message_id=reply_id)

        elif stripped.startswith("خرید "):
            item_name = stripped[5:].strip()
            if item_name not in ITEMS:
                send_message(chat_id, "❌ آیتم پیدا نشد.", reply_to_message_id=reply_id); release_conn(conn); return
            price = ITEMS[item_name]["price"]
            if u['gold'] < price:
                send_message(chat_id, "❌ طلا کافی ندارید.", reply_to_message_id=reply_id); release_conn(conn); return
            u['gold'] -= price
            u['items'][item_name] = u['items'].get(item_name, 0) + 1
            update_user(user_id, {"gold": u['gold'], "items": u['items']}, conn)
            send_message(chat_id, f"✅ شما {item_name} را خریدید.", reply_to_message_id=reply_id)

        elif stripped.startswith("واریز "):
            amount = extract_amount(text, "واریز")
            if amount is None or amount <= 0 or u['gold'] < amount:
                send_message(chat_id, "❌ مبلغ نامعتبر یا کافی نیست.", reply_to_message_id=reply_id); release_conn(conn); return
            u['gold'] -= amount
            u['bank'] += amount
            update_user(user_id, {"gold": u['gold'], "bank": u['bank']}, conn)
            send_message(chat_id, f"✅ {amount} طلا به خزانه واریز شد.", reply_to_message_id=reply_id)

        elif stripped.startswith("برداشت "):
            amount = extract_amount(text, "برداشت")
            if amount is None or amount <= 0 or u['bank'] < amount:
                send_message(chat_id, "❌ مبلغ نامعتبر یا خزانه کافی نیست.", reply_to_message_id=reply_id); release_conn(conn); return
            u['bank'] -= amount
            u['gold'] += amount
            update_user(user_id, {"gold": u['gold'], "bank": u['bank']}, conn)
            send_message(chat_id, f"✅ {amount} طلا از خزانه برداشت شد.", reply_to_message_id=reply_id)

        release_conn(conn)
    except Exception as e:
        print("🔴 ERROR in process_message:", e)

def process_callback(cb):
    try:
        cb_id = cb["id"]
        chat_id = cb["message"]["chat"]["id"]
        user_id = cb.get("from", {}).get("id")
        data = cb.get("data", "")

        conn = get_conn()
        u = get_user(user_id, conn)

        if data.startswith("vote_"):
            parts = data.split("_")
            event_id, opt_idx = int(parts[1]), int(parts[2])
            cur = conn.cursor()
            cur.execute("SELECT options, deadline FROM events WHERE event_id=%s AND status='active'", (event_id,))
            row = cur.fetchone()
            if not row:
                answer_callback(cb_id, "مسابقه پیدا نشد.", True); release_conn(conn); return
            options, deadline = row
            if time.time() > deadline:
                answer_callback(cb_id, "زمان مسابقه به پایان رسیده!", True); release_conn(conn); return
            
            choice = options[opt_idx]
            cur.execute("""
                INSERT INTO event_votes (event_id, user_id, choice) VALUES (%s, %s, %s)
                ON CONFLICT (user_id, event_id) DO UPDATE SET choice=%s
            """, (event_id, user_id, choice, choice))
            conn.commit()
            answer_callback(cb_id, f"انتخاب شما ثبت شد: {choice}", False)

        release_conn(conn)
    except Exception as e:
        print("🔴 ERROR in process_callback:", e)
