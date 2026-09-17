import time
import random
import threading
from utils import send_message, answer_callback, is_jailed, extract_amount
from database import get_conn, release_conn, get_user, update_user
from config import CLAIM_COOLDOWN, STEAL_COOLDOWN, STEAL_WARNINGS_LIMIT, JAIL_SECONDS, JAIL_RANSOM, MAIN_GROUP_USERNAME
from admin import handle_admin_commands

def process_message(msg):
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

    if stripped == "طلا":
        if is_jailed(u):
            send_message(chat_id, "🚔 در زندان هستید!", reply_id); release_conn(conn); return
        now = time.time()
        if now - u['last_claim'] < CLAIM_COOLDOWN:
            send_message(chat_id, "🔴 هنوز وقت دریافت طلا نرسیده!", reply_id); release_conn(conn); return
        amount = random.randint(80, 250)
        update_user(user_id, {"gold": u['gold'] + amount, "last_claim": now}, conn)
        send_message(chat_id, f"💰 شما {amount} طلا گرفتید!", reply_id)

    elif stripped == "دزدی":
        if is_jailed(u):
            send_message(chat_id, "🚔 در زندان هستید!", reply_id); release_conn(conn); return

        reply_to = msg.get("reply_to_message")
        if not reply_to:
            send_message(chat_id, "ریپلای کن روی فرد و دزدی بزن.", reply_id); release_conn(conn); return

        target_id = reply_to.get("from", {}).get("id")
        if target_id == user_id:
            send_message(chat_id, "نمیتونی از خودت بدزنی!", reply_id); release_conn(conn); return

        now = time.time()
        if now - u['last_steal'] < STEAL_COOLDOWN:
            warnings = u['steal_warnings'] + 1
            if warnings >= STEAL_WARNINGS_LIMIT:
                update_user(user_id, {"jail_until": now + JAIL_SECONDS, "steal_warnings": 0}, conn)
                send_message(chat_id, f"🚔 پافشاری کردی! زندان 10 دقیقه. فدیه: {JAIL_RANSOM} طلا", reply_id)
            else:
                update_user(user_id, {"steal_warnings": warnings}, conn)
                send_message(chat_id, f"⏳ 30 ثانیه نرفته! اخطار {warnings} از {STEAL_WARNINGS_LIMIT}.", reply_id)
            release_conn(conn); return

        target = get_user(target_id, conn)
        if target['gold'] <= 0:
            send_message(chat_id, "این کاربر طلا نداره!", reply_id); release_conn(conn); return

        steal_amount = min(random.randint(30, 100), target['gold'])
        update_user(target_id, {"gold": target['gold'] - steal_amount}, conn)
        update_user(user_id, {"gold": u['gold'] + steal_amount, "last_steal": now, "steal_warnings": 0}, conn)
        send_message(chat_id, f"🥷 دزدی موفق! {steal_amount} طلا گرفتی.", reply_id)

    release_conn(conn)

def process_callback(cb):
    cb_id = cb["id"]
    chat_id = cb["message"]["chat"]["id"]
    user_id = cb.get("from", {}).get("id")
    data = cb.get("data", "")
    msg_id = cb["message"]["message_id"]

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
        # درج یا آپدیت رأی کاربر
        cur.execute("""
            INSERT INTO event_votes (event_id, user_id, choice) VALUES (%s, %s, %s)
            ON CONFLICT (user_id, event_id) DO UPDATE SET choice=%s
        """, (event_id, user_id, choice, choice))
        conn.commit()
        answer_callback(cb_id, f"انتخاب شما ثبت شد: {choice}", False)

    release_conn(conn)
