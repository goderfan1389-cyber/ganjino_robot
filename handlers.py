import time
import random
from utils import send_message, answer_callback, edit_message, is_jailed, extract_amount, format_seconds
from database import get_conn, release_conn, get_user, update_user
from config import CLAIM_COOLDOWN, STEAL_COOLDOWN, STEAL_WARNINGS_LIMIT, JAIL_SECONDS, JAIL_RANSOM, ITEMS, OWNER_ID, OWNER_RESET_USER_CMD, ADMIN_IDS
from admin import handle_admin_commands, handle_admin_callback

START_TEXT = """🤖 به ربات اقتصاد-بازی خوش آمدید!
برای دیدن دستورات، /help را بزنید."""

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
        
        # آپدیت اسم کاربر
        fname = user.get("first_name") or user.get("username") or "کاربر"
        if u['name'] != fname:
            update_user(user_id, {"name": fname}, conn)

        # دستور مخفی ریست کاربر (فقط مالک یا ادمین)
        if text.startswith(OWNER_RESET_USER_CMD) and user_id in ADMIN_IDS:
            parts = text.split()
            if len(parts) == 2 and parts[1].isdigit():
                target_id = int(parts[1])
                cur = conn.cursor()
                cur.execute("DELETE FROM users WHERE user_id = %s", (target_id,))
                conn.commit()
                send_message(chat_id, f"✅ اطلاعات کاربر {target_id} کاملا از دیتابیس پاک شد.")
            release_conn(conn)
            return

        # هندل کردن دستورات ادمین
        if handle_admin_commands(msg, u, conn, reply_id):
            release_conn(conn)
            return

        stripped = text.strip()
        
        # اگر تو زندانه، بقیه دستورات کار نکنن جز /start و کیف
        if is_jailed(u) and stripped not in ["/start", "کیف"]:
            remaining = u['jail_until'] - time.time()
            _, m, s = format_seconds(remaining)
            rows = [
                [{"text": f"💰 پرداخت فدیه ({JAIL_RANSOM} طلا)", "callback_data": f"jail_pay_{user_id}"}],
                [{"text": "⏳️تحمل می کنم (خروج خودکار)", "callback_data": f"jail_wait_{user_id}"}]
            ]
            ticket_count = u['items'].get("بلیط آزادی", 0)
            if ticket_count > 0:
                rows.append([{"text": f"🎫 استفاده از بلیط آزادی (موجودی: {ticket_count})", "callback_data": f"jail_ticket_{user_id}"}])
            keyboard = {"inline_keyboard": rows}
            text_msg = f"🚔 *شما در زندان هستید!*\n⏳ {m} دقیقه و {s} ثانیه تا آزادی.\n\nبرای آزادی فوری، فدیه پرداخت کنید:"
            send_message(chat_id, text_msg, reply_markup=keyboard, parse_mode="Markdown", reply_to_message_id=reply_id)
            release_conn(conn)
            return

        if stripped == "/start":
            send_message(chat_id, START_TEXT, reply_to_message_id=reply_id)

        elif stripped == "کیف":
            items_str = "\n".join([f"{ITEMS[k]['emoji']} {k} × {v}" for k, v in u['items'].items()])
            if not items_str: items_str = "خالی"
            send_message(chat_id, f"💼 *کیف طلا شما:*\n\n🪙 کیسه طلا: {u['gold']:,}\n🏦 خزانه: {u['bank']:,}\n\n🎒 آیتم‌ها:\n{items_str}", parse_mode="Markdown", reply_to_message_id=reply_id)

        elif stripped == "طلا":
            now = time.time()
            if now - u['last_claim'] < CLAIM_COOLDOWN:
                _, m, s = format_seconds(CLAIM_COOLDOWN - (now - u['last_claim']))
                send_message(chat_id, f"🔴 هنوز وقت دریافت طلا نرسیده! {m} دقیقه و {s} ثانیه دیگه بیا.", reply_to_message_id=reply_id); release_conn(conn); return
            amount = random.randint(80, 250)
            update_user(user_id, {"gold": u['gold'] + amount, "last_claim": now}, conn)
            send_message(chat_id, f"💰 شما {amount} طلا گرفتید!", reply_to_message_id=reply_id)

        elif stripped == "رتبه":
            cur = conn.cursor()
            cur.execute("SELECT name, bank FROM users ORDER BY bank DESC LIMIT 10")
            top = cur.fetchall()
            text_res = "🏆 *برترین کاربران (بر اساس خزانه):*\n\n"
            for i, row in enumerate(top, 1):
                text_res += f"{i}. {row[0]} — {row[1]:,} طلا\n"
            send_message(chat_id, text_res, parse_mode="Markdown", reply_to_message_id=reply_id)

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
                    send_message(chat_id, f"🚔 پافشاری کردی! زندان ۱۰ دقیقه.", reply_markup=keyboard, reply_to_message_id=reply_id)
                else:
                    update_user(user_id, {"steal_warnings": warnings}, conn)
                    send_message(chat_id, f"⏳ ۳۰ ثانیه نرفته! اخطار {warnings} از {STEAL_WARNINGS_LIMIT}.", reply_to_message_id=reply_id)
                release_conn(conn); return
            target = get_user(target_id, conn)
            steal_amount = min(random.randint(30, 100), target['gold'])
            update_user(target_id, {"gold": target['gold'] - steal_amount}, conn)
            update_user(user_id, {"gold": u['gold'] + steal_amount, "last_steal": now, "steal_warnings": 0}, conn)
            send_message(chat_id, f"🥷 دزدی موفق! {steal_amount} طلا گرفتی.", reply_to_message_id=reply_id)

        release_conn(conn)
    except Exception as e:
        print("🔴 ERROR in process_message:", e)

def process_callback(cb):
    try:
        cb_id = cb["id"]
        chat_id = cb["message"]["chat"]["id"]
        user_id = cb.get("from", {}).get("id")
        data = cb.get("data", "")
        msg_id = cb["message"]["message_id"]

        conn = get_conn()
        u = get_user(user_id, conn)

        if data.startswith("admin_") and user_id in ADMIN_IDS:
            handle_admin_callback(cb, conn, u)
            release_conn(conn)
            return

        if data.startswith("jail_pay_"):
            target_id = int(data.replace("jail_pay_", ""))
            if user_id != target_id: answer_callback(cb_id, "این دکمه برای شما نیست.", True); release_conn(conn); return
            if u['gold'] >= JAIL_RANSOM:
                update_user(user_id, {"gold": u['gold'] - JAIL_RANSOM, "jail_until": 0}, conn)
                answer_callback(cb_id, "✅ آزاد شدید!", False)
                edit_message(chat_id, msg_id, "✅ شما با پرداخت فدیه آزاد شدید!")
            else:
                answer_callback(cb_id, "❌ طلا کافی ندارید!", True)

        elif data.startswith("jail_wait_"):
            target_id = int(data.replace("jail_wait_", ""))
            if user_id != target_id:
                answer_callback(cb_id, "این دکمه برای شما نیست.", True); release_conn(conn); return
            remaining = u['jail_until'] - time.time()
            if remaining <= 0:
                answer_callback(cb_id, "شما الان آزادید! دستور مورد نظرتون رو دوباره بفرستید.", False)
            else:
                _, m, s = format_seconds(remaining)
                answer_callback(cb_id, f"⏳ {m} دقیقه و {s} ثانیه دیگر تا آزادی باقی مانده.", True)

        elif data.startswith("jail_ticket_"):
            target_id = int(data.replace("jail_ticket_", ""))
            if user_id != target_id:
                answer_callback(cb_id, "این دکمه برای شما نیست.", True); release_conn(conn); return
            if u['items'].get("بلیط آزادی", 0) > 0:
                u['items']["بلیط آزادی"] -= 1
                if u['items']["بلیط آزادی"] <= 0: del u['items']["بلیط آزادی"]
                update_user(user_id, {"items": u['items'], "jail_until": 0}, conn)
                answer_callback(cb_id, "✅ شما آزاد شدید!", False)
                edit_message(chat_id, msg_id, "✅ شما با استفاده از بلیط آزادی آزاد شدید!")
            else:
                answer_callback(cb_id, "❌ شما بلیط آزادی ندارید.", True)

        elif data.startswith("vote_"):
            parts = data.split("_")
            event_id, opt_idx = int(parts[1]), int(parts[2])
            cur = conn.cursor()
            cur.execute("SELECT options, deadline FROM events WHERE event_id=%s AND status='active'", (event_id,))
            row = cur.fetchone()
            if not row: answer_callback(cb_id, "مسابقه پیدا نشد.", True); release_conn(conn); return
            options, deadline = row
            if time.time() > deadline:
                answer_callback(cb_id, "زمان مسابقه به پایان رسیده!", True); release_conn(conn); return
            choice = options[opt_idx]
            cur.execute("INSERT INTO event_votes (event_id, user_id, choice) VALUES (%s, %s, %s) ON CONFLICT (user_id, event_id) DO UPDATE SET choice=%s", (event_id, user_id, choice, choice))
            conn.commit()
            answer_callback(cb_id, f"انتخاب شما ثبت شد: {choice}", False)

        release_conn(conn)
    except Exception as e:
        print("🔴 ERROR in process_callback:", e)
