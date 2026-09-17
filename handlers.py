import time
import random
import requests
from utils import send_message, answer_callback, edit_message, is_jailed, extract_amount
from database import get_conn, release_conn, get_user, update_user
from config import CLAIM_COOLDOWN, STEAL_COOLDOWN, STEAL_WARNINGS_LIMIT, JAIL_SECONDS, JAIL_RANSOM, ITEMS
from admin import handle_admin_commands, handle_admin_callback

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
    
    # رفع باگ پی‌وی: اگر کاربر اسم نداشت، یوزرنیم یا کلمه کاربر رو بذار
    fname = user.get("first_name") or user.get("username") or "کاربر"
    if u['name'] != fname:
        update_user(user_id, {"name": fname}, conn)

    if handle_admin_commands(msg, u, conn, reply_id):
        release_conn(conn)
        return

    stripped = text.strip()
    
    # اگر تو زندانه، بقیه دستورات کار نکنن جز /start و کیف
    if is_jailed(u) and stripped not in ["/start", "کیف"]:
        keyboard = {"inline_keyboard": [[{"text": f"💰 پرداخت فدیه ({JAIL_RANSOM} طلا)", "callback_data": f"jail_pay_{user_id}"}]]}
        send_message(chat_id, f"🚔 *شما در زندان هستید!*\n⏳ {int(u['jail_until'] - time.time())} ثانیه تا آزادی.\n\nبرای آزادی فوری، فدیه پرداخت کنید:", reply_markup=keyboard, parse_mode="Markdown", reply_to_message_id=reply_id)
        release_conn(conn)
        return

    if stripped == "/start":
        send_message(chat_id, "🤖 به ربات طلا خوش آمدید!\nبرای دیدن موجودی خود بنویسید: کیف", reply_to_message_id=reply_id)

    elif stripped == "کیف":
        items_str = "\n".join([f"{ITEMS[k]['emoji']} {k} × {v}" for k, v in u['items'].items()])
        if not items_str: items_str = "خالی"
        send_message(chat_id, f"💼 *کیف طلا شما:*\n\n🪙 کیسه طلا: {u['gold']:,}\n🏦 خزانه: {u['bank']:,}\n\n🎒 آیتم‌ها:\n{items_str}", parse_mode="Markdown", reply_to_message_id=reply_id)

    elif stripped == "طلا":
        now = time.time()
        if now - u['last_claim'] < CLAIM_COOLDOWN:
            send_message(chat_id, "🔴 هنوز وقت دریافت طلا نرسیده!", reply_to_message_id=reply_id); release_conn(conn); return
        
        amount = random.randint(80, 250)
        update_user(user_id, {"gold": u['gold'] + amount, "last_claim": now, "xp": u.get('xp',0) + 1}, conn)
        send_message(chat_id, f"💰 *تبریک! شما {amount} طلا دریافت کردید!*\n🪙 موجودی کیسه: {u['gold']+amount:,} طلا", parse_mode="Markdown", reply_to_message_id=reply_id)

    elif stripped == "روزانه":
        now = time.time()
        if now - u.get('last_daily', 0) < 86400:
            send_message(chat_id, "🔴 هنوز وقت دریافت جایزه روزانه نرسیده!", reply_to_message_id=reply_id); release_conn(conn); return
        amount = random.randint(300, 800)
        update_user(user_id, {"gold": u['gold'] + amount, "last_daily": now}, conn)
        send_message(chat_id, f"🎁 *جایزه روزانه شما: {amount} طلا!*", parse_mode="Markdown", reply_to_message_id=reply_id)

    elif stripped == "دزدی":
        reply_to = msg.get("reply_to_message")
        if not reply_to:
            send_message(chat_id, "برای دزدی، روی پیام فرد ریپلای کنید و بنویسید دزدی.", reply_to_message_id=reply_id); release_conn(conn); return

        target_id = reply_to.get("from", {}).get("id")
        if target_id == user_id:
            send_message(chat_id, "نمی‌توانید از خودتان بدزدید!", reply_to_message_id=reply_id); release_conn(conn); return

        now = time.time()
        if now - u['last_steal'] < STEAL_COOLDOWN:
            warnings = u['steal_warnings'] + 1
            if warnings >= STEAL_WARNINGS_LIMIT:
                update_user(user_id, {"jail_until": now + JAIL_SECONDS, "steal_warnings": 0}, conn)
                keyboard = {"inline_keyboard": [[{"text": f"💰 پرداخت فدیه ({JAIL_RANSOM} طلا)", "callback_data": f"jail_pay_{user_id}"}]]}
                send_message(chat_id, f"🚔 *پافشاری کردی! زندان ۱۰ دقیقه.*\nفدیه: {JAIL_RANSOM} طلا", reply_markup=keyboard, parse_mode="Markdown", reply_to_message_id=reply_id)
            else:
                update_user(user_id, {"steal_warnings": warnings}, conn)
                send_message(chat_id, f"⏳ *۳۰ ثانیه نرفته!*\nاخطار {warnings} از {STEAL_WARNINGS_LIMIT}.", parse_mode="Markdown", reply_to_message_id=reply_id)
            release_conn(conn); return

        target = get_user(target_id, conn)
        if target['gold'] <= 0:
            send_message(chat_id, "این کاربر طلا در کیسه ندارد!", reply_to_message_id=reply_id); release_conn(conn); return

        steal_amount = min(random.randint(30, 100), target['gold'])
        update_user(target_id, {"gold": target['gold'] - steal_amount}, conn)
        update_user(user_id, {"gold": u['gold'] + steal_amount, "last_steal": now, "steal_warnings": 0}, conn)
        send_message(chat_id, f"🥷 *دزدی موفق!*\n💰 شما {steal_amount} طلا دزدیدید.", parse_mode="Markdown", reply_to_message_id=reply_id)

    elif stripped == "فروشگاه":
        send_message(chat_id, """🛒 فروشگاه ربات:

🛡 سپر — 100 طلا
🔪 چاقو — 100 طلا
🎭 ماسک — 100 طلا
🧲 آهنربا — 100 طلا
🎫 بلیط آزادی — 47 طلا

برای خرید بنویسید: خرید [نام آیتم]""", reply_to_message_id=reply_id)

    elif stripped.startswith("خرید "):
        item_name = stripped[5:].strip()
        if item_name not in ITEMS:
            send_message(chat_id, "❌ همچین آیتمی در فروشگاه نیست.", reply_to_message_id=reply_id); release_conn(conn); return
        price = ITEMS[item_name]["price"]
        if u['gold'] < price:
            send_message(chat_id, "❌ موجودی کیسه طلا کافی نیست.", reply_to_message_id=reply_id); release_conn(conn); return
        u['gold'] -= price
        u['items'][item_name] = u['items'].get(item_name, 0) + 1
        update_user(user_id, {"gold": u['gold'], "items": u['items']}, conn)
        send_message(chat_id, f"✅ شما {ITEMS[item_name]['emoji']} {item_name} را خریدید.", reply_to_message_id=reply_id)

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

def process_callback(cb):
    cb_id = cb["id"]
    chat_id = cb["message"]["chat"]["id"]
    user_id = cb.get("from", {}).get("id")
    data = cb.get("data", "")
    msg_id = cb["message"]["message_id"]

    conn = get_conn()
    u = get_user(user_id, conn)

    # پرداخت فدیه زندان
    if data.startswith("jail_pay_"):
        if u['gold'] >= JAIL_RANSOM:
            update_user(user_id, {"gold": u['gold'] - JAIL_RANSOM, "jail_until": 0}, conn)
            answer_callback(cb_id, "✅ شما آزاد شدید!", False)
            edit_message(chat_id, msg_id, "✅ شما با پرداخت فدیه آزاد شدید!")
        else:
            answer_callback(cb_id, "❌ طلا کافی برای فدیه ندارید!", True)

    # ثبت رأی مسابقه
    elif data.startswith("vote_"):
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
