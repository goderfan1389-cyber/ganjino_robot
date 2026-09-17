import time
import random
from utils import send_message, answer_callback, edit_message, is_jailed, extract_amount, format_seconds
from database import get_conn, release_conn, get_user, update_user
from config import CLAIM_COOLDOWN, DAILY_COOLDOWN_SECONDS, STEAL_COOLDOWN, STEAL_WARNINGS_LIMIT, JAIL_SECONDS, JAIL_RANSOM, ITEMS, OWNER_ID, OWNER_RESET_USER_CMD, ADMIN_IDS
from admin import handle_admin_commands, handle_admin_callback
from games import create_duel_game, handle_game_callback

START_TEXT = """🤖 به ربات اقتصاد-بازی خوش آمدید!
برای دیدن دستورات، /help را بزنید."""

HELP_TEXT = """📖 راهنمای کامل ربات طلا 🪙

💰 اقتصاد پایه
🔸 طلا — دریافت طلای رایگان (هر ۴ دقیقه یک‌بار)
🔸 روزانه — جایزه روزانه بین ۳۰۰ تا ۸۰۰ طلا (هر ۲۴ ساعت یک‌بار)
🔸 کیف — نمایش کیسه طلا، خزانه، XP و آیتم‌ها

🏦 خزانه
🔸 واریز [مبلغ] — انتقال طلا از کیسه به خزانه
🔸 برداشت [مبلغ] — انتقال طلا از خزانه به کیسه

🤝 تعامل با بقیه
🔸 انتقال [مبلغ] — ریپلای به پیام کسی + این دستور، برای هدیه‌دادن طلا
🔸 دزدی — ریپلای به پیام کسی، برای دزدیدن طلای کیسه‌اش
🚔 هر دزدی ۳۰٪ احتمال دستگیری داره (با آیتم‌ها کمتر میشه)؛ اگه طرف سپر داشته باشه، دزد قطعا دستگیر میشه!

🛒 فروشگاه
🔸 فروشگاه — دیدن لیست آیتم‌ها
🔸 خرید [نام آیتم] — خرید آیتم با طلای کیسه

🏆 رتبه‌بندی
🔸 رتبه — ۱۰ نفر برتر گروه و ۱۰ نفر برتر کل ربات (بر اساس خزانه)

🎮 بازی‌های شرط‌بندی (با کیسه طلا)
🔸 دوز [مبلغ] — بازی دوز (XO) دو نفره ⭕❌
🔸 کازینو [مبلغ] — چالش شانسی ۵۰-۵۰ 🎰
🔸 سنگ کاغذ قیچی [مبلغ] — بازی کلاسیک دو نفره ✂️
🔸 گل یا پوچ [مبلغ] — قایم‌کردن و حدس‌زدن دست 🌸

⏱ توی همه بازی‌های دو نفره هر نوبت فقط ۳۰ ثانیه فرصت دارید؛ دیر بجنبید، طلا میره برای حریف!

برای شروع، از /start استفاده کنید 🚀"""

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
        
        fname = user.get("first_name") or user.get("username") or "کاربر"
        if u['name'] != fname:
            update_user(user_id, {"name": fname}, conn)

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

        if handle_admin_commands(msg, u, conn, reply_id):
            release_conn(conn)
            return

        stripped = text.strip()
        
        if is_jailed(u) and stripped not in ["/start", "کیف", "/help", "کمک"]:
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

        elif stripped == "/help" or stripped == "کمک":
            send_message(chat_id, HELP_TEXT, reply_to_message_id=reply_id)

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
            xp = random.randint(1, 3)
            update_user(user_id, {"gold": u['gold'] + amount, "last_claim": now, "xp": u.get('xp',0) + xp}, conn)
            send_message(chat_id, f"💰 تبریک شما {amount} طلا دریافت کردید! 💰\n\n🎖XP : {u.get('xp',0)+xp}\n\nموجودی کیف طلا شما: {u['gold']+amount:,} طلا\nخزانه : {u['bank']:,} طلا", reply_to_message_id=reply_id)

        elif stripped == "روزانه":
            now = time.time()
            elapsed = now - u.get('last_daily', 0)
            if elapsed < DAILY_COOLDOWN_SECONDS:
                remaining = DAILY_COOLDOWN_SECONDS - elapsed
                h, m, s = format_seconds(remaining)
                reply = f"⏳ شما قبلا جایزه روزانه را گرفته‌اید. لطفا {h} ساعت و {m} دقیقه {s} ثانیه دیگر تلاش کنید."
                send_message(chat_id, reply, reply_to_message_id=reply_id); release_conn(conn); return

            amount = random.randint(300, 800)
            update_user(user_id, {"gold": u['gold'] + amount, "last_daily": now}, conn)
            reply = f"*🎁 جایزه روزانه شما: {amount:,} طلا\n\nکیسه طلا: {u['gold']:,} طلا\nخزانه: {u['bank']:,} طلا*"
            send_message(chat_id, reply, parse_mode="Markdown", reply_to_message_id=reply_id)

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
                    remaining_sec = int(STEAL_COOLDOWN - (now - u['last_steal']))
                    send_message(chat_id, f"⏳ *هنوز زمان دزدی نرسیده!*\n\nحدود {remaining_sec} ثانیه دیگه باید صبر کنی.\nاخطار {warnings} از {STEAL_WARNINGS_LIMIT}.", parse_mode="Markdown", reply_to_message_id=reply_id)
                release_conn(conn); return

            target = get_user(target_id, conn)
            if target['gold'] <= 0:
                send_message(chat_id, "این کاربر طلا در کیسه ندارد!", reply_to_message_id=reply_id); release_conn(conn); return

            steal_amount = min(random.randint(30, 100), target['gold'])
            update_user(target_id, {"gold": target['gold'] - steal_amount}, conn)
            update_user(user_id, {"gold": u['gold'] + steal_amount, "last_steal": now, "steal_warnings": 0}, conn)
            
            reply = (
                "*🥷 دزدی با موفقیت انجام شد 🥷                    \n \n"
                f"💰طلا دزدی شده : {steal_amount:,} طلا *\n\n"
                "••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••"
            )
            send_message(chat_id, reply, parse_mode="Markdown", reply_to_message_id=reply_id)

        elif stripped.startswith("انتقال "):
            amount = extract_amount(text, "انتقال")
            reply_to = msg.get("reply_to_message")
            if amount is None or amount <= 0 or not reply_to:
                send_message(chat_id, "برای انتقال طلا، روی پیام شخص ریپلای کنید و بنویسید انتقال [مبلغ].", reply_to_message_id=reply_id); release_conn(conn); return
            target_id = reply_to.get("from", {}).get("id")
            if target_id == user_id:
                send_message(chat_id, "نمی‌توانید به خودتان طلا انتقال دهید!", reply_to_message_id=reply_id); release_conn(conn); return
            if u['gold'] < amount:
                send_message(chat_id, "❌ موجودی کیسه طلای شما کافی نیست.", reply_to_message_id=reply_id); release_conn(conn); return
            target = get_user(target_id, conn)
            update_user(user_id, {"gold": u['gold'] - amount}, conn)
            update_user(target_id, {"gold": target['gold'] + amount}, conn)
            send_message(chat_id, f"✅ مبلغ {amount:,} طلا به {target['name']} منتقل شد.", reply_to_message_id=reply_id)

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
            send_message(chat_id, f"🏦 مبلغ {amount} طلا به خزانه منتقل شد.\n\nکیسه طلا: {u['gold']:,}\nخزانه: {u['bank']:,}", reply_to_message_id=reply_id)

        elif stripped.startswith("برداشت "):
            amount = extract_amount(text, "برداشت")
            if amount is None or amount <= 0 or u['bank'] < amount:
                send_message(chat_id, "❌ مبلغ نامعتبر یا خزانه کافی نیست.", reply_to_message_id=reply_id); release_conn(conn); return
            u['bank'] -= amount
            u['gold'] += amount
            update_user(user_id, {"gold": u['gold'], "bank": u['bank']}, conn)
            send_message(chat_id, f"💸 مبلغ {amount} طلا از خزانه برداشت شد.\n\nکیسه طلا: {u['gold']:,}\nخزانه: {u['bank']:,}", reply_to_message_id=reply_id)

        # --- بازی ها ---
        elif stripped.startswith("دوز "):
            amount = extract_amount(text, "دوز")
            if amount and amount > 0 and u['gold'] >= amount:
                update_user(user_id, {"gold": u['gold'] - amount}, conn)
                text_msg = (
                    "❌⭕ بازی دوز (XO) شروع شد ⭕❌\n\n"
                    f"👤 میزبان: {u['name']} (X)\n\n"
                    "👤 حریف: منتظر...\n\n"
                    f"💰 مبلغ شرط: {amount:,} طلا\n"
                    f"🎁 جایزه برد: {amount * 2:,} طلا (پس از کسر ۵٪ مالیات)\n\n"
                    "اگر کسی برای شرکت پیدا نشود، بعد 7 دقیقه بازی لغو می‌شود ✅"
                )
                create_duel_game(conn, "dooz", chat_id, user_id, u['name'], amount, text_msg)

        elif stripped.startswith("کازینو "):
            amount = extract_amount(text, "کازینو")
            if amount and amount > 0 and u['gold'] >= amount:
                update_user(user_id, {"gold": u['gold'] - amount}, conn)
                text_msg = (
                    "(*کازینو جدید*)🎰\n\n"
                    f"👤 میزبان: {u['name']}\n\n"
                    f"💵 مبلغ شرط: {amount:,} طلا\n\n"
                    "*•••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••*\n"
                    "(تا 5 دقیقه دیگر شرکت کننده‌ای نباشد کازینو باطل می‌شود)"
                )
                create_duel_game(conn, "casino", chat_id, user_id, u['name'], amount, text_msg)

        elif stripped.startswith("سنگ کاغذ قیچی "):
            amount = extract_amount(text, "سنگ کاغذ قیچی")
            if amount and amount > 0 and u['gold'] >= amount:
                update_user(user_id, {"gold": u['gold'] - amount}, conn)
                text_msg = (
                    "✊✋✌️ چالش سنگ‌کاغذقیچی شروع شد\n\n"
                    f"👤 میزبان: {u['name']}\n\n"
                    f"💰 مبلغ شرط: {amount:,} طلا\n"
                    f"🎁 جایزه برد: {amount * 2:,} طلا (پس از کسر ۵٪ مالیات)\n\n"
                    "اگر کسی برای شرکت پیدا نشود، بعد 5 دقیقه بازی لغو می‌شود ✅"
                )
                create_duel_game(conn, "rps", chat_id, user_id, u['name'], amount, text_msg)

        elif stripped.startswith("گل یا پوچ "):
            amount = extract_amount(text, "گل یا پوچ")
            if amount and amount > 0 and u['gold'] >= amount:
                update_user(user_id, {"gold": u['gold'] - amount}, conn)
                text_msg = (
                    "🌸 چالش گل یا پوچ شروع شد 🌸\n\n"
                    f"👤 میزبان: {u['name']}\n\n"
                    f"💰 مبلغ شرط: {amount:,} طلا\n"
                    f"🎁 جایزه برد: {amount * 2:,} طلا (پس از کسر ۵٪ مالیات)\n\n"
                    "اگر کسی برای شرکت پیدا نشود، بعد 5 دقیقه بازی لغو می‌شود ✅"
                )
                create_duel_game(conn, "guess", chat_id, user_id, u['name'], amount, text_msg)

        release_conn(conn)
    except Exception as e:
        print("🔴 ERROR in process_message:", e)

    finally:
        if conn: release_conn(conn)

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

        if data.startswith(("dooz_", "casino_", "rps_", "guess_")):
            handle_game_callback(cb, conn, u)
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

    finally:
        if conn: release_conn(conn)
