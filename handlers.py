import time
import random
from utils import send_message, answer_callback, edit_message, is_jailed, extract_amount, format_seconds
from database import get_conn, release_conn, get_user, update_user
from config import (CLAIM_COOLDOWN, DAILY_COOLDOWN_SECONDS, STEAL_COOLDOWN, STEAL_WARNINGS_LIMIT, 
                    JAIL_SECONDS, JAIL_RANSOM, ITEMS, OWNER_ID, OWNER_RESET_USER_CMD, ADMIN_IDS, 
                    BOT_USERNAME, REFERRAL_BONUS, ARREST_BASE_CHANCE, MASK_ARREST_DISCOUNT)
from admin import handle_admin_commands, handle_admin_callback
from games import create_duel_game, handle_game_callback

START_TEXT = """🤖 به ربات اقتصاد-بازی خوش آمدید!

با این ربات می‌توانید طلا جمع کنید، اقلام بخرید، از دیگران دزدی کنید، در مسابقه شرکت کنید و خیلی کارهای دیگر.

📌 برای شروع سریع از دستورات زیر استفاده کنید.

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

👥 زیرمجموعه‌گیری
🔸 زیر مجموعه — دریافت لینک دعوت اختصاصی

🏆 رتبه‌بندی
🔸 رتبه — ۱۰ نفر برتر گروه و ۱۰ نفر برتر کل ربات (بر اساس خزانه)

🎮 بازی‌های شرط‌بندی (با کیسه طلا)
🔸 دوز [مبلغ] — بازی دوز (XO) دو نفره ⭕❌
🔸 کازینو [مبلغ] — چالش شانسی ۵۰-۵۰ 🎰
🔸 سنگ کاغذ قیچی [مبلغ] — بازی کلاسیک دو نفره ✂️
🔸 گل یا پوچ [مبلغ] — قایم‌کردن و حدس‌زدن دست 🌸

⏱ توی همه بازی‌های دو نفره هر نوبت فقط ۳۰ ثانیه فرصت دارید؛ دیر بجنبید، طلا میره برای حریف!

برای شروع، از /start استفاده کنید 🚀"""

def send_jail_block(chat_id, user_id, u, reply_id=None, custom_text=""):
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
    text_msg = custom_text + f"\n🚔 *شما در زندان هستید!*\n⏳ {m} دقیقه و {s} ثانیه تا آزادی.\n\nبرای آزادی فوری، فدیه پرداخت کنید:"
    send_message(chat_id, text_msg, reply_markup=keyboard, parse_mode="Markdown", reply_to_message_id=reply_id)

def process_message(msg):
    conn = get_conn()
    try:
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")
        user = msg.get("from", {})
        user_id = user.get("id")
        chat_type = msg.get("chat", {}).get("type", "private")
        reply_id = msg["message_id"] if chat_type in ("group", "supergroup") else None

        if not text or user_id is None: return
        
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
            return

        if handle_admin_commands(msg, u, conn, reply_id):
            return

        stripped = text.strip()
        
        if is_jailed(u) and not (stripped.startswith("واریز ") or stripped.startswith("برداشت ") or stripped in ["/start", "کیف", "/help", "کمک"]):
            send_jail_block(chat_id, user_id, u, reply_id)
            return

        if stripped == "/start":
            send_message(chat_id, START_TEXT, reply_to_message_id=reply_id)

        elif stripped == "/help" or stripped == "کمک":
            send_message(chat_id, HELP_TEXT, reply_to_message_id=reply_id)

        elif stripped == "کیف":
            items_str = "\n".join([f"{ITEMS[k]['emoji']} {k} × {v}" for k, v in u['items'].items()])
            if not items_str: items_str = "خالی"
            send_message(chat_id, f"💼 *کیف پول شما:*\n\n🪙 کیسه طلا: {u['gold']:,}\n🏦 خزانه: {u['bank']:,}\n\n🎒 آیتم‌ها:\n{items_str}", parse_mode="Markdown", reply_to_message_id=reply_id)

        elif stripped == "طلا":
            now = time.time()
            if now - u['last_claim'] < CLAIM_COOLDOWN:
                _, m, s = format_seconds(CLAIM_COOLDOWN - (now - u['last_claim']))
                send_message(chat_id, f"*🔴 شما قبلاً طلا دریافت کردید 🪙\n\n🛠 لطفا {m} دقیقه و {s} ثانیه دیگر امتحان کنید.⚒*", parse_mode="Markdown", reply_to_message_id=reply_id); return
            
            # سیستم آهنربا
            if u['items'].get("آهنربا", 0) > 0:
                amount = random.randint(200, 500)
                u['items']["آهنربا"] -= 1
                if u['items']["آهنربا"] <= 0: del u['items']["آهنربا"]
                update_user(user_id, {"gold": u['gold'] + amount, "last_claim": now, "items": u['items']}, conn)
                send_message(chat_id, f"🧲 *آهنربای شما فعال شد!*\n💰 شما {amount} طلا دریافت کردید! 💰\n\nموجودی کیف طلا شما: {u['gold']+amount:,} طلا", parse_mode="Markdown", reply_to_message_id=reply_id)
            else:
                amount = random.randint(80, 250)
                update_user(user_id, {"gold": u['gold'] + amount, "last_claim": now}, conn)
                send_message(chat_id, f"💰 *تبریک شما {amount} طلا دریافت کردید! 💰*\n\nموجودی کیف طلا شما: {u['gold']+amount:,} طلا", parse_mode="Markdown", reply_to_message_id=reply_id)

        elif stripped == "روزانه":
            now = time.time()
            elapsed = now - u.get('last_daily', 0)
            if elapsed < DAILY_COOLDOWN_SECONDS:
                remaining = DAILY_COOLDOWN_SECONDS - elapsed
                h, m, s = format_seconds(remaining)
                send_message(chat_id, f"⏳ *شما قبلاً جایزه روزانه را گرفته‌اید.*\n\nلطفا {h} ساعت و {m} دقیقه و {s} ثانیه دیگر تلاش کنید.", parse_mode="Markdown", reply_to_message_id=reply_id); return

            amount = random.randint(300, 800)
            update_user(user_id, {"gold": u['gold'] + amount, "last_daily": now}, conn)
            send_message(chat_id, f"🎁 *جایزه روزانه شما: {amount:,} طلا!*\n\nکیسه طلا: {u['gold'] + amount:,} طلا\nخزانه: {u['bank']:,} طلا", parse_mode="Markdown", reply_to_message_id=reply_id)

        elif stripped == "رتبه":
            cur = conn.cursor()
            cur.execute("SELECT name, bank FROM users ORDER BY bank DESC LIMIT 10")
            top = cur.fetchall()
            text_res = "🏆 *برترین کاربران (بر اساس خزانه):*\n\n"
            for i, row in enumerate(top, 1):
                text_res += f"{i}. {row[0]} — {row[1]:,} طلا\n"
            send_message(chat_id, text_res, parse_mode="Markdown", reply_to_message_id=reply_id)

        elif stripped == "زیر مجموعه":
            link = f"https://ble.ir/{BOT_USERNAME}?start=ref-{user_id}"
            reply = f"با پخش لینک زیر و دعوت هر نفر {REFERRAL_BONUS:,} طلا دریافت کن😍😱\n{link}\n\n💰 هر دعوت: {REFERRAL_BONUS:,} طلا"
            send_message(chat_id, reply, reply_to_message_id=reply_id)

        elif stripped == "دزدی":
            reply_to = msg.get("reply_to_message")
            if not reply_to:
                send_message(chat_id, "برای دزدی، روی پیام فردی که می‌خواهید از او بدزدید ریپلای کنید و بنویسید «دزدی».", reply_to_message_id=reply_id); return
            
            target_id = reply_to.get("from", {}).get("id")
            if target_id == user_id:
                send_message(chat_id, "نمی‌توانید از خودتان بدزدید!", reply_to_message_id=reply_id); return
                
            now = time.time()
            if now - u['last_steal'] < STEAL_COOLDOWN:
                warnings = u['steal_warnings'] + 1
                if warnings >= STEAL_WARNINGS_LIMIT:
                    update_user(user_id, {"jail_until": now + JAIL_SECONDS, "steal_warnings": 0}, conn)
                    send_jail_block(chat_id, user_id, u, reply_id, "🚔 *پافشاری کردی! زندان ۱۰ دقیقه.*")
                else:
                    update_user(user_id, {"steal_warnings": warnings}, conn)
                    remaining_sec = int(STEAL_COOLDOWN - (now - u['last_steal']))
                    send_message(chat_id, f"⏳ *هنوز زمان دزدی نرسیده!*\n\nحدود {remaining_sec} ثانیه دیگه باید صبر کنی.\nاخطار {warnings} از {STEAL_WARNINGS_LIMIT}.", parse_mode="Markdown", reply_to_message_id=reply_id)
                return

            target = get_user(target_id, conn)
            if target['gold'] <= 0:
                send_message(chat_id, "این کاربر طلایی در کیسه طلا خود ندارد!", reply_to_message_id=reply_id); return

            thief_items = u['items']
            target_items = target['items']
            thief_updated = False
            target_updated = False

            # ۱. چک کردن سپر طرف مقابل
            if target_items.get("سپر", 0) > 0:
                target_items["سپر"] -= 1
                if target_items["سپر"] <= 0: del target_items["سپر"]
                target_updated = True
                
                msg_parts = [f"🛡 *سپر {target['name']} شکست!* دزدی ناموفق بود!"]
                
                if thief_items.get("چاقو", 0) > 0:
                    thief_items["چاقو"] -= 1
                    if thief_items["چاقو"] <= 0: del thief_items["چاقو"]
                    msg_parts.append("🔪 چاقوی تو هم در درگیری شکست!")
                    thief_updated = True
                    
                # اگه ماسک نداشت، میره زندان
                if thief_items.get("ماسک", 0) > 0:
                    thief_items["ماسک"] -= 1
                    if thief_items["ماسک"] <= 0: del thief_items["ماسک"]
                    msg_parts.append("🎭 ماسکت تو رو از دست پلیس پنهان کرد و فرار کردی!")
                    update_user(user_id, {"items": thief_items, "last_steal": now, "steal_warnings": 0}, conn)
                    send_message(chat_id, "\n".join(msg_parts), parse_mode="Markdown", reply_to_message_id=reply_id)
                else:
                    update_user(user_id, {"items": thief_items, "jail_until": now + JAIL_SECONDS, "last_steal": now, "steal_warnings": 0}, conn)
                    u['jail_until'] = now + JAIL_SECONDS
                    send_jail_block(chat_id, user_id, u, reply_id, "\n".join(msg_parts) + "\n🚔 پلیس تو دستگیر کرد!")
                
                if target_updated: update_user(target_id, {"items": target_items}, conn)
                return

            # ۲. چک کردن شانس دستگیری پلیس (اگه سپر نداشت)
            arrest_chance = ARREST_BASE_CHANCE
            if thief_items.get("ماسک", 0) > 0:
                arrest_chance -= MASK_ARREST_DISCOUNT
                
            if random.random() < arrest_chance:
                # دستگیر شده!
                if thief_items.get("ماسک", 0) > 0:
                    thief_items["ماسک"] -= 1
                    if thief_items["ماسک"] <= 0: del thief_items["ماسک"]
                    update_user(user_id, {"items": thief_items, "last_steal": now, "steal_warnings": 0}, conn)
                    send_message(chat_id, "🚔 *پلیس متوجه دزدی شد!*\n🎭 اما ماسکت تو رو سرپنه کرد و از دست پلیس فرار کردی (ماسک شکست)!", parse_mode="Markdown", reply_to_message_id=reply_id)
                else:
                    update_user(user_id, {"jail_until": now + JAIL_SECONDS, "last_steal": now, "steal_warnings": 0}, conn)
                    u['jail_until'] = now + JAIL_SECONDS
                    send_jail_block(chat_id, user_id, u, reply_id, "🚔 *پلیس تو حین دزدی دستگیرت کرد!*")
                return

            # ۳. دزدی با موفقیت انجام شد!
            if thief_items.get("چاقو", 0) > 0:
                steal_amount = min(random.randint(80, 200), target['gold'])
                thief_items["چاقو"] -= 1
                if thief_items["چاقو"] <= 0: del thief_items["چاقو"]
                update_user(target_id, {"gold": target['gold'] - steal_amount}, conn)
                update_user(user_id, {"gold": u['gold'] + steal_amount, "items": thief_items, "last_steal": now, "steal_warnings": 0}, conn)
                reply = f"*🔪 با چاقو دزدی رو با خشونت انجام دادی!*\n💰طلا دزدی شده : {steal_amount:,} طلا"
            else:
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
                send_message(chat_id, "برای انتقال طلا، روی پیام شخص مورد نظر ریپلای کنید و بنویسید «انتقال [مبلغ]»", reply_to_message_id=reply_id); return
            target_id = reply_to.get("from", {}).get("id")
            if target_id == user_id:
                send_message(chat_id, "نمی‌توانید به خودتان طلا انتقال دهید!", reply_to_message_id=reply_id); return
            if u['gold'] < amount:
                send_message(chat_id, "❌ موجودی کیسه طلای شما برای این انتقال کافی نیست.", reply_to_message_id=reply_id); return
            target = get_user(target_id, conn)
            update_user(user_id, {"gold": u['gold'] - amount}, conn)
            update_user(target_id, {"gold": target['gold'] + amount}, conn)
            send_message(chat_id, f"✅ مبلغ {amount:,} طلا از کیسه طلای شما به {target['name']} منتقل شد.\n\nکیسه طلای شما: {u['gold']:,} طلا", reply_to_message_id=reply_id)

        elif stripped == "فروشگاه":
            send_message(chat_id, """🛒 فروشگاه ربات:

🛡 سپر — 100 طلا
جلوگیری از دزدی (محافظت کامل)

🔪 چاقو — 100 طلا
دریافت پول ۲ برابری در دزدی

🎭 ماسک — 100 طلا
کاهش شانس دستگیری پلیس

🧲 آهنربا — 100 طلا
دریافت طلا ۳ برابر در دستور طلا

🎫 بلیط آزادی — 47 طلا
آزادی فوری از زندان

برای خرید از دستور "خرید [نام آیتم]" استفاده کنید.""", reply_to_message_id=reply_id)

        elif stripped.startswith("خرید"):
            parts = stripped.split(maxsplit=1)
            item_name = parts[1].strip() if len(parts) > 1 else None

            if not item_name or item_name not in ITEMS:
                send_message(chat_id, "❌ همچین آیتمی در فروشگاه وجود ندارد.", reply_to_message_id=reply_id); return

            price = ITEMS[item_name]["price"]
            emoji = ITEMS[item_name]["emoji"]

            if u['gold'] < price:
                send_message(chat_id, "❌ موجودی کیسه طلا برای خرید این آیتم کافی نیست.", reply_to_message_id=reply_id); return

            u['gold'] -= price
            u['items'][item_name] = u['items'].get(item_name, 0) + 1
            update_user(user_id, {"gold": u['gold'], "items": u['items']}, conn)
            send_message(chat_id, f"✅ شما {emoji} {item_name} را خریدید.\n\nکیسه طلا: {u['gold']:,} طلا\nخزانه: {u['bank']:,} طلا", reply_to_message_id=reply_id)

        elif stripped.startswith("واریز "):
            amount = extract_amount(text, "واریز")
            if amount is None or amount <= 0:
                send_message(chat_id, "❌ مبلغ نامعتبر است.", reply_to_message_id=reply_id); return
            if u['gold'] < amount:
                send_message(chat_id, "❌ موجودی کیسه طلای شما کافی نیست.", reply_to_message_id=reply_id); return
            
            u['gold'] -= amount
            u['bank'] += amount
            update_user(user_id, {"gold": u['gold'], "bank": u['bank']}, conn)
            reply = f"🏦 مبلغ {amount:,} طلا به خزانه منتقل شد.\n\nکیسه طلا: {u['gold']:,} طلا\nخزانه: {u['bank']:,} طلا"
            send_message(chat_id, reply, reply_to_message_id=reply_id)

        elif stripped.startswith("برداشت "):
            amount = extract_amount(text, "برداشت")
            if amount is None or amount <= 0:
                send_message(chat_id, "❌ مبلغ نامعتبر است.", reply_to_message_id=reply_id); return
            if u['bank'] < amount:
                send_message(chat_id, "❌ موجودی خزانه شما کافی نیست.", reply_to_message_id=reply_id); return
                
            u['bank'] -= amount
            u['gold'] += amount
            update_user(user_id, {"gold": u['gold'], "bank": u['bank']}, conn)
            reply = f"💸 مبلغ {amount:,} طلا از خزانه برداشت شد.\n\nکیسه طلا: {u['gold']:,} طلا\nخزانه: {u['bank']:,} طلا"
            send_message(chat_id, reply, reply_to_message_id=reply_id)

        # --- بازی ها ---
        elif stripped.startswith("دوز "):
            amount = extract_amount(text, "دوز")
            if amount and amount > 0 and u['gold'] >= amount:
                update_user(user_id, {"gold": u['gold'] - amount}, conn)
                text_msg = (
                    "❌⭕ بازی دوز (XO) شروع شد ⭕❌\n\n"
                    "👥 شرکت‌کنندگان:\n"
                    f"👤 میزبان: {u['name']} (X)\n\n"
                    "👤 حریف: منتظر...\n\n"
                    f"💰 مبلغ شرط: {amount:,} طلا\n"
                    f"🎁 جایزه برد: {amount * 2:,} طلا (پس از کسر ۱۰٪ مالیات)\n\n"
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
                    f"🎁 جایزه برد: {amount * 2:,} طلا (پس از کسر ۱۰٪ مالیات)\n\n"
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
                    f"🎁 جایزه برد: {amount * 2:,} طلا (پس از کسر ۱۰٪ مالیات)\n\n"
                    "اگر کسی برای شرکت پیدا نشود، بعد 5 دقیقه بازی لغو می‌شود ✅"
                )
                create_duel_game(conn, "guess", chat_id, user_id, u['name'], amount, text_msg)

    except Exception as e:
        print("🔴 ERROR in process_message:", e)
    finally:
        if conn: release_conn(conn)

def process_callback(cb):
    conn = get_conn()
    try:
        cb_id = cb["id"]
        chat_id = cb["message"]["chat"]["id"]
        user_id = cb.get("from", {}).get("id")
        data = cb.get("data", "")
        msg_id = cb["message"]["message_id"]

        u = get_user(user_id, conn)

        if data.startswith("admin_") and user_id in ADMIN_IDS:
            handle_admin_callback(cb, conn, u)
            return

        if data.startswith(("dooz_", "casino_", "rps_", "guess_")):
            handle_game_callback(cb, conn, u)
            return

        if data.startswith("jail_pay_"):
            target_id = int(data.replace("jail_pay_", ""))
            if user_id != target_id: answer_callback(cb_id, "این دکمه برای شما نیست.", True); return
            if u['gold'] >= JAIL_RANSOM:
                update_user(user_id, {"gold": u['gold'] - JAIL_RANSOM, "jail_until": 0}, conn)
                answer_callback(cb_id, "✅ آزاد شدید!", False)
                edit_message(chat_id, msg_id, f"✅ شما با پرداخت {JAIL_RANSOM} طلا آزاد شدید!", reply_markup={"inline_keyboard": []})
            else:
                answer_callback(cb_id, "موجودی کیسه طلای شما برای پرداخت فدیه کافی نیست.", True)

        elif data.startswith("jail_wait_"):
            target_id = int(data.replace("jail_wait_", ""))
            if user_id != target_id:
                answer_callback(cb_id, "این دکمه برای شما نیست.", True); return
            remaining = u['jail_until'] - time.time()
            if remaining <= 0:
                answer_callback(cb_id, "شما الان آزادید! دستور مورد نظرتون رو دوباره بفرستید.", False)
            else:
                _, m, s = format_seconds(remaining)
                answer_callback(cb_id, f"⏳ {m} دقیقه و {s} ثانیه دیگر تا آزادی باقی مانده.", True)

        elif data.startswith("jail_ticket_"):
            target_id = int(data.replace("jail_ticket_", ""))
            if user_id != target_id:
                answer_callback(cb_id, "این دکمه برای شما نیست.", True); return
            if u['items'].get("بلیط آزادی", 0) > 0:
                u['items']["بلیط آزادی"] -= 1
                if u['items']["بلیط آزادی"] <= 0: del u['items']["بلیط آزادی"]
                update_user(user_id, {"items": u['items'], "jail_until": 0}, conn)
                answer_callback(cb_id, "✅ آزاد شدید!", False)
                edit_message(chat_id, msg_id, "✅ شما با استفاده از بلیط آزادی آزاد شدید!", reply_markup={"inline_keyboard": []})
            else:
                answer_callback(cb_id, "شما بلیط آزادی ندارید.", True)

        elif data.startswith("vote_"):
            parts = data.split("_")
            event_id, opt_idx = int(parts[1]), int(parts[2])
            cur = conn.cursor()
            cur.execute("SELECT options, deadline, status FROM events WHERE event_id=%s", (event_id,))
            row = cur.fetchone()
            if not row: answer_callback(cb_id, "مسابقه پیدا نشد.", True); return
            options, deadline, status = row
            
            if status != 'active' or time.time() > deadline:
                answer_callback(cb_id, "⏰ زمان مسابقه به پایان رسیده!", True)
                if status == 'active':
                    edit_message(chat_id, msg_id, "⏰ زمان مسابقه به پایان رسید!\nانتخاب‌ها قفل شدند.", reply_markup={"inline_keyboard": []})
                return
            
            choice = options[opt_idx]
            cur.execute("INSERT INTO event_votes (event_id, user_id, choice) VALUES (%s, %s, %s) ON CONFLICT (user_id, event_id) DO UPDATE SET choice=%s", (event_id, user_id, choice, choice))
            conn.commit()
            answer_callback(cb_id, f"انتخاب شما ثبت شد: {choice}", False)

    except Exception as e:
        print("🔴 ERROR in process_callback:", e)
    finally:
        if conn: release_conn(conn)
