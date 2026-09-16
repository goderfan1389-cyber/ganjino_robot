import requests
import json
import os
import re
import random
import time
import threading

# تلاش برای بارگذاری فایل .env در حالت اجرای محلی
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ===== تنظیمات حساس =====
BOT_TOKEN = os.environ.get("BOT_TOKEN", "1178057070:HPKhPZfmr8oVwDqSXIpbDFfqBroohnuHWd8")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "GANJINO_BOT")
MAIN_GROUP_USERNAME = os.environ.get("MAIN_GROUP_USERNAME", "GANJINO_GAP")
JOIN_CHANNEL_USERNAME = os.environ.get("JOIN_CHANNEL_USERNAME", "computer_program")
BACKUP_PASSWORD = os.environ.get("BACKUP_PASSWORD", "GANJINO_TEAM_IR")

def _parse_id_set(env_name, default_csv):
    raw = os.environ.get(env_name, default_csv)
    return {int(x.strip()) for x in raw.split(",") if x.strip()}

ADMIN_IDS = _parse_id_set("ADMIN_IDS", "324157864,890352247")
OWNER_ID = int(os.environ.get("OWNER_ID", "324157864"))
OWNER_RESET_USER_CMD = os.environ.get("OWNER_RESET_USER_CMD", "/resetuser_9fK7xQ2pLmZ8vR3")

BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"
DATA_FILE = "bot_data.json"

# ===== بهینه‌سازی سرعت =====
session = requests.Session()
data_lock = threading.Lock()
last_game_check = 0.0

CLAIM_COOLDOWN_SECONDS = 4 * 60
DAILY_COOLDOWN_SECONDS = 24 * 60 * 60

DOOZ_WAIT_TIMEOUT_SECONDS = 7 * 60
CASINO_WAIT_TIMEOUT_SECONDS = 5 * 60
RPS_WAIT_TIMEOUT_SECONDS = 5 * 60
GUESS_WAIT_TIMEOUT_SECONDS = 5 * 60
TURN_TIMEOUT_SECONDS = 30

GAME_TAX_PERCENT = 0.05
CASINO_TAX_PERCENT = 0.10

REFERRAL_BONUS_DEFAULT = 7500

JAIL_SECONDS = 10 * 60
JAIL_RANSOM = 50
ARREST_BASE_CHANCE = 0.30
KNIFE_ARREST_DISCOUNT = 0.10
MASK_ARREST_DISCOUNT = 0.15
MIN_ARREST_CHANCE = 0.05

MAGNET_GOLD_RANGE = (60, 300)
DEFAULT_GOLD_RANGE = (80, 250)

ITEMS = {
    "سپر": {"emoji": "🛡", "price": 100},
    "چاقو": {"emoji": "🔪", "price": 100},
    "ماسک": {"emoji": "🎭", "price": 100},
    "آهنربا": {"emoji": "🧲", "price": 100},
    "بلیط آزادی": {"emoji": "🎫", "price": 47},
}

SHOP_TEXT = """🛒 فروشگاه ربات:

🛡 سپر — 100 طلا
جلوگیری از دزدی

🔪 چاقو — 100 طلا
افزایش شانس دزدی

🎭 ماسک — 100 طلا
کاهش احتمال زندان

🧲 آهنربا — 100 طلا
پول بیشتر از دستور پول

🎫 بلیط آزادی — 47 طلا
استفاده برای آزادی فوری از زندان بدون نیاز به پرداخت طلا.

برای خرید از دستور "خرید [نام آیتم]" استفاده کنید."""

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
🔸 دکمه «زیرمجموعه‌های من» — دیدن لیست دعوت‌شده‌ها

🏆 رتبه‌بندی
🔸 رتبه — ۱۰ نفر برتر گروه و ۱۰ نفر برتر کل ربات (بر اساس خزانه)

🎮 بازی‌های شرط‌بندی (با کیسه طلا)
🔸 دوز [مبلغ] — بازی دوز (XO) دو نفره ⭕❌
🔸 کازینو [مبلغ] — چالش شانسی ۵۰-۵۰ 🎰
🔸 سنگ کاغذ قیچی [مبلغ] — بازی کلاسیک دو نفره ✂️
🔸 گل یا پوچ [مبلغ] — قایم‌کردن و حدس‌زدن دست 🌸

⏱ توی همه بازی‌های دو نفره هر نوبت فقط ۳۰ ثانیه فرصت دارید؛ دیر بجنبید، طلا میره برای حریف!

برای شروع، از /start استفاده کنید 🚀"""

RANK_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

EMPTY_CELL = "⬜️"
X_MARK = "❌"
O_MARK = "⭕"

WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]

RPS_NAMES = {"rock": "🪨 سنگ", "paper": "📄 کاغذ", "scissors": "✂️ قیچی"}
RPS_BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}

GAME_STORE_KEYS = ("_dooz_games", "_casino_games", "_rps_games", "_guess_games")
NON_USER_KEYS = ("_groups", "_game_counter", "_referral_bonus", "_admin_pending") + GAME_STORE_KEYS

# ===== ذخیره‌سازی داده =====
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(data, user_id):
    uid = str(user_id)
    if uid not in data or not isinstance(data[uid], dict):
        data[uid] = {
            "gold": 0,
            "bank": 0,
            "xp": 0,
            "last_claim": 0,
            "last_daily": 0,
            "jail_until": 0,
            "referred_by": None,
            "referrals": [],
            "items": {},
            "name": "کاربر",
        }
    u = data[uid]
    u.setdefault("items", {})
    u.setdefault("last_daily", 0)
    u.setdefault("jail_until", 0)
    return u

def update_name(u, user):
    name = (user.get("first_name") or "").strip()
    if user.get("last_name"):
        name = f"{name} {user.get('last_name')}".strip()
    if not name:
        name = user.get("username") or "کاربر"
    u["name"] = name

def record_group_membership(data, chat_id, chat_type, user_id):
    if chat_type in ("group", "supergroup"):
        groups = data.setdefault("_groups", {})
        members = groups.setdefault(str(chat_id), [])
        if user_id not in members:
            members.append(user_id)

def all_real_users(data):
    return [(uid, u) for uid, u in data.items() if uid not in NON_USER_KEYS and isinstance(u, dict)]

def next_game_id(data):
    counter = data.get("_game_counter", 0) + 1
    data["_game_counter"] = counter
    return str(counter)

def get_referral_bonus(data):
    return data.get("_referral_bonus", REFERRAL_BONUS_DEFAULT)

# ===== زندان =====
def is_jailed(u):
    return u.get("jail_until", 0) > time.time()

def jail_remaining(u):
    return u.get("jail_until", 0) - time.time()

def jail_block_message(u):
    remaining = jail_remaining(u)
    _, m, s = format_seconds(remaining)
    return (
        "🚔 شما در زندان هستید!\n\n"
        f"⏳ {m} دقیقه و {s} ثانیه تا آزادی باقی مانده.\n"
        "می‌توانید از دکمه‌های زیر برای آزادی زودتر استفاده کنید."
    )

def jail_block_keyboard(u, user_id):
    rows = [
        [{"text": f"💰 پرداخت فدیه ({JAIL_RANSOM} طلا)", "callback_data": f"jail_pay_{user_id}"}],
    ]
    ticket_count = u.get("items", {}).get("بلیط آزادی", 0)
    if ticket_count > 0:
        rows.append([{"text": f"🎫 استفاده از بلیط آزادی (موجودی: {ticket_count})", "callback_data": f"jail_ticket_{user_id}"}])
    return {"inline_keyboard": rows}

def send_jail_block_message(chat_id, user_id, u, reply_to_message_id=None):
    send_message(chat_id, jail_block_message(u), reply_markup=jail_block_keyboard(u, user_id), reply_to_message_id=reply_to_message_id)

def compute_arrest_chance(u):
    chance = ARREST_BASE_CHANCE
    items = u.get("items", {})
    if items.get("چاقو", 0) > 0:
        chance -= KNIFE_ARREST_DISCOUNT
    if items.get("ماسک", 0) > 0:
        chance -= MASK_ARREST_DISCOUNT
    return max(chance, MIN_ARREST_CHANCE)

def arrest_user(data, user_id, chat_id, extra_text=None, reply_to_message_id=None):
    u = get_user(data, user_id)
    u["jail_until"] = time.time() + JAIL_SECONDS
    text = "🚔 *شما دستگیر شدید* 🚔\n\n*⛓‍💥 برای آزاد شدن 10 دقیقه باید صبر کنید\nیا جریمه پرداخت کنید 💵*"
    if extra_text:
        text = f"{extra_text}\n\n{text}"
    rows = [
        [{"text": f"💰 پرداخت فدیه ({JAIL_RANSOM} طلا)", "callback_data": f"jail_pay_{user_id}"}],
        [{"text": "⏳️تحمل می کنم (خروج خودکار)", "callback_data": f"jail_wait_{user_id}"}],
    ]
    ticket_count = u.get("items", {}).get("بلیط آزادی", 0)
    if ticket_count > 0:
        rows.append([{"text": f"🎫 استفاده از بلیط آزادی (موجودی: {ticket_count})", "callback_data": f"jail_ticket_{user_id}"}])
    send_message(chat_id, text, reply_markup={"inline_keyboard": rows}, parse_mode="Markdown", reply_to_message_id=reply_to_message_id)

# ===== تبدیل اعداد فارسی =====
FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
def fa_to_en(s):
    return s.translate(str.maketrans(FA_DIGITS, "0123456789"))

def extract_amount(text, keyword):
    text = fa_to_en(text.strip())
    if not text.startswith(keyword):
        return None
    remainder = text[len(keyword):]
    if remainder and not remainder[0].isspace():
        return None
    remainder = remainder.strip()
    if not remainder:
        return None
    num_str = re.sub(r"[^\d]", "", remainder.split()[0])
    if num_str:
        return int(num_str)
    return None

def format_seconds(total_seconds):
    total_seconds = max(0, int(total_seconds))
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return h, m, s

def items_text_for(u):
    items = u.get("items", {})
    if not items:
        return "هیچ آیتمی ندارید."
    lines = []
    for name, count in items.items():
        emoji = ITEMS.get(name, {}).get("emoji", "🎒")
        lines.append(f"{emoji} {name} × {count}")
    return "\n".join(lines)

def referral_message_text(user_id, bonus):
    link = f"https://ble.ir/{BOT_USERNAME}?start=ref-{user_id}"
    return (
        f"با پخش لینک زیر و دعوت هر نفر {bonus:,} طلا دریافت کن😍😱\n"
        f"{link}\n\n"
        f"💰 هر دعوت: {bonus:,} طلا"
    )

def notify_referrer(ref_id, invitee_name, bonus):
    text = (
        f"🎉 {invitee_name} با لینک دعوت شما به ربات پیوست!\n\n"
        f"💰 شما {bonus:,} طلا دریافت کردید."
    )
    send_message(ref_id, text)

# ===== توابع ارتباط با API بله =====
def send_message(chat_id, text, reply_markup=None, parse_mode=None, reply_to_message_id=None):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup)
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    try:
        return session.post(url, data=payload, timeout=10)
    except Exception as e:
        print("send_message error:", e)
        return None

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

def edit_message(chat_id, message_id, text, reply_markup=None, parse_mode=None):
    if message_id is None:
        return
    url = f"{BASE_URL}/editMessageText"
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup)
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        session.post(url, data=payload, timeout=10)
    except Exception as e:
        print("edit_message error:", e)

def answer_callback(callback_id, text="", show_alert=True):
    url = f"{BASE_URL}/answerCallbackQuery"
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert
    try:
        session.post(url, data=payload, timeout=10)
    except Exception as e:
        print("answer_callback error:", e)

def get_sent_message_id(resp):
    if resp is None:
        return None
    try:
        return resp.json().get("result", {}).get("message_id")
    except Exception:
        return None

def check_joined_channel(user_id):
    try:
        resp = session.get(f"{BASE_URL}/getChatMember", params={
            "chat_id": f"@{JOIN_CHANNEL_USERNAME}",
            "user_id": user_id,
        }, timeout=10)
        result = resp.json().get("result", {})
        status = result.get("status", "")
        return status in ("member", "administrator", "creator", "owner")
    except Exception as e:
        print("check_joined_channel error:", e)
        return True

def join_required_reply(chat_id, reply_to_message_id=None):
    keyboard = {
        "inline_keyboard": [
            [{"text": "📚 آموزش برنامه‌نویسی آرکا", "url": f"https://ble.ir/{JOIN_CHANNEL_USERNAME}"}],
        ]
    }
    send_message(
        chat_id,
        "🚫 برای استفاده از ربات، ابتدا باید عضو کانال زیر بشید:\n\n"
        "بعد از عضویت، دوباره دستور خودتون رو بفرستید. ✅",
        reply_markup=keyboard,
        reply_to_message_id=reply_to_message_id,
    )

# ===== متن‌های ثابت =====
START_TEXT = """🤖 به ربات اقتصاد-بازی خوش آمدید!

با این ربات می‌توانید طلا جمع کنید، اقلام بخرید، از دیگران دزدی کنید، در مسابقه شرکت کنید و خیلی کارهای دیگر.

📌 برای شروع سریع از دکمه‌های زیر استفاده کنید.

برای دیدن دستورات، /help را بزنید."""

START_KEYBOARD = {
    "inline_keyboard": [
        [{"text": "📢 گروه اصلی ربات", "url": f"https://ble.ir/{MAIN_GROUP_USERNAME}"}],
        [{"text": "👥️ زیرمجموعه گیری", "callback_data": "referral"}],
        [{"text": "🏠 حساب من", "callback_data": "my_account"}],
        [{"text": "📜 زیرمجموعه های من", "callback_data": "my_referrals"}],
    ]
}

# ================= بازی دوز (XO) =================
def build_board_keyboard(game_id, board):
    keyboard = []
    for row in range(3):
        row_buttons = []
        for col in range(3):
            idx = row * 3 + col
            row_buttons.append({"text": board[idx], "callback_data": f"dooz_move_{game_id}_{idx}"})
        keyboard.append(row_buttons)
    return {"inline_keyboard": keyboard}

def check_winner(board):
    for a, b, c in WIN_LINES:
        if board[a] != EMPTY_CELL and board[a] == board[b] == board[c]:
            return board[a]
    if all(cell != EMPTY_CELL for cell in board):
        return "draw"
    return None

def dooz_waiting_text(game):
    return (
        "❌⭕ بازی دوز (XO) شروع شد ⭕❌\n\n"
        "👥 شرکت‌کنندگان:\n"
        f"👤 میزبان: {game['host_name']} (X)\n\n"
        "👤 حریف: منتظر...\n\n"
        f"💰 مبلغ شرط: {game['bet']:,} طلا\n"
        f"🎁 جایزه برد: {game['bet'] * 2:,} طلا (پس از کسر ۵٪ مالیات)\n\n"
        "اگر کسی برای شرکت پیدا نشود، بعد 7 دقیقه بازی لغو می‌شود ✅"
    )

def dooz_active_text(game, turn_name):
    return (
        "❌⭕ بازی دوز (XO) ⭕❌\n\n"
        f"👤 {game['host_name']} ({game['symbols'][str(game['host_id'])]})\n"
        f"👤 {game['opponent_name']} ({game['symbols'][str(game['opponent_id'])]})\n\n"
        f"💰 مبلغ شرط: {game['bet']:,} طلا\n\n"
        f"نوبت {turn_name} ({game['turn']}) هست"
    )

def dooz_payout(data, winner_id, game):
    winner = get_user(data, winner_id)
    pot = game["bet"] * 2
    tax = round(pot * GAME_TAX_PERCENT)
    prize = pot - tax
    winner["gold"] += prize
    return prize

def handle_dooz_join(data, cb, game_id):
    cb_id = cb["id"]
    game = data.get("_dooz_games", {}).get(game_id)
    if not game or game.get("status") != "waiting":
        answer_callback(cb_id, "این بازی دیگر در دسترس نیست.")
        return

    user = cb.get("from", {})
    user_id = user.get("id")

    if user_id == game["host_id"]:
        answer_callback(cb_id, "نمی‌تونی چون خودت این بازی رو ساختی!")
        return

    u = get_user(data, user_id)
    update_name(u, user)

    if u["gold"] < game["bet"]:
        answer_callback(cb_id, "موجودی کیسه طلای شما برای این بازی کافی نیست.")
        return

    u["gold"] -= game["bet"]
    game["opponent_id"] = user_id
    game["opponent_name"] = u["name"]
    game["status"] = "active"
    game["board"] = [EMPTY_CELL] * 9

    if random.choice([True, False]):
        game["symbols"] = {str(game["host_id"]): X_MARK, str(user_id): O_MARK}
    else:
        game["symbols"] = {str(game["host_id"]): O_MARK, str(user_id): X_MARK}

    game["turn"] = X_MARK
    game["turn_deadline"] = time.time() + TURN_TIMEOUT_SECONDS
    starter_id = game["host_id"] if game["symbols"][str(game["host_id"])] == X_MARK else user_id
    starter_name = game["host_name"] if starter_id == game["host_id"] else game["opponent_name"]

    text = dooz_active_text(game, starter_name)
    keyboard = build_board_keyboard(game_id, game["board"])
    edit_message(game["chat_id"], game["message_id"], text, reply_markup=keyboard)
    answer_callback(cb_id, "بازی شروع شد!")

def handle_dooz_cancel(data, cb, game_id):
    cb_id = cb["id"]
    game = data.get("_dooz_games", {}).get(game_id)
    if not game or game.get("status") != "waiting":
        answer_callback(cb_id, "این بازی دیگر قابل لغو نیست.")
        return

    user_id = cb.get("from", {}).get("id")
    if user_id != game["host_id"]:
        answer_callback(cb_id, "فقط سازنده بازی می‌تواند آن را لغو کند.")
        return

    host = get_user(data, game["host_id"])
    host["gold"] += game["bet"]
    game["status"] = "cancelled"

    edit_message(
        game["chat_id"], game["message_id"],
        "❌ بازی دوز توسط سازنده لغو شد و مبلغ شرط به کیسه طلا بازگشت داده شد.",
        reply_markup={"inline_keyboard": []},
    )
    answer_callback(cb_id, "بازی لغو شد و طلای شما بازگشت.")

def handle_dooz_move(data, cb, game_id, idx):
    cb_id = cb["id"]
    game = data.get("_dooz_games", {}).get(game_id)
    if not game or game.get("status") != "active":
        answer_callback(cb_id, "این بازی فعال نیست.")
        return

    user_id = cb.get("from", {}).get("id")
    if user_id not in (game["host_id"], game["opponent_id"]):
        answer_callback(cb_id, "شما در این بازی شرکت نکرده‌اید.")
        return

    my_symbol = game["symbols"].get(str(user_id))
    if my_symbol != game["turn"]:
        answer_callback(cb_id, "نوبت شما نیست.")
        return

    if game["board"][idx] != EMPTY_CELL:
        answer_callback(cb_id, "این خانه قبلا پر شده.")
        return

    game["board"][idx] = my_symbol
    result = check_winner(game["board"])
    keyboard = build_board_keyboard(game_id, game["board"])

    if result == "draw":
        host = get_user(data, game["host_id"])
        opp = get_user(data, game["opponent_id"])
        host["gold"] += game["bet"]
        opp["gold"] += game["bet"]
        game["status"] = "finished"
        text = "🤝 بازی مساوی شد! مبلغ شرط به کیسه طلای هر دو نفر بازگشت داده شد."
        edit_message(game["chat_id"], game["message_id"], text, reply_markup=keyboard)
        answer_callback(cb_id, "مساوی شد.")
        return

    if result in (X_MARK, O_MARK):
        winner_id = user_id
        prize = dooz_payout(data, winner_id, game)
        winner_name = game["host_name"] if winner_id == game["host_id"] else game["opponent_name"]
        game["status"] = "finished"
        text = (
            f"🏆 {winner_name} برنده بازی دوز شد! 🏆\n\n"
            f"💰 جایزه دریافتی: {prize:,} طلا (پس از کسر ۵٪ مالیات)"
        )
        edit_message(game["chat_id"], game["message_id"], text, reply_markup=keyboard)
        answer_callback(cb_id, "بردی! تبریک 🎉")
        return

    game["turn"] = O_MARK if game["turn"] == X_MARK else X_MARK
    game["turn_deadline"] = time.time() + TURN_TIMEOUT_SECONDS
    next_id = game["host_id"] if game["symbols"][str(game["host_id"])] == game["turn"] else game["opponent_id"]
    next_name = game["host_name"] if next_id == game["host_id"] else game["opponent_name"]
    text = dooz_active_text(game, next_name)
    edit_message(game["chat_id"], game["message_id"], text, reply_markup=keyboard)
    answer_callback(cb_id)

# ================= کازینو =================
def handle_casino_join(data, cb, game_id):
    cb_id = cb["id"]
    game = data.get("_casino_games", {}).get(game_id)
    if not game or game.get("status") != "waiting":
        answer_callback(cb_id, "این چالش دیگر در دسترس نیست.")
        return

    user = cb.get("from", {})
    user_id = user.get("id")

    if user_id == game["host_id"]:
        answer_callback(cb_id, "نمی‌تونی چون خودت این چالش رو ساختی!")
        return

    u = get_user(data, user_id)
    update_name(u, user)

    if u["gold"] < game["bet"]:
        answer_callback(cb_id, "موجودی کیسه طلای شما برای این چالش کافی نیست.")
        return

    u["gold"] -= game["bet"]
    game["opponent_id"] = user_id
    game["opponent_name"] = u["name"]
    game["status"] = "finished"

    winner_is_host = random.choice([True, False])
    winner_id = game["host_id"] if winner_is_host else user_id
    winner_name = game["host_name"] if winner_is_host else game["opponent_name"]
    winner = get_user(data, winner_id)

    pot = game["bet"] * 2
    tax = round(pot * CASINO_TAX_PERCENT)
    prize = pot - tax
    winner["gold"] += prize

    text = (
        "🎰 *کازینو  تمام شد و نتیجه اعلام شد* 🎲\n\n"
        "👥شرکت‌کنندگان:\n"
        f"👤 : {game['host_name']}\n\n"
        f"👤 : {game['opponent_name']}\n"
        "*••••••••••••••••••نتیجه••••••••••••••••••*\n"
        f"💰 مبلغ شرط:  {game['bet']:,} طلا\n\n"
        f"برنده: 🎖 {winner_name}\n"
        f"🎁 جایزه (کسر مالیات 10%): {prize:,} طلا\n"
        f"💸 مالیات کسر شده: {tax:,} طلا"
    )
    edit_message(game["chat_id"], game["message_id"], text, reply_markup={"inline_keyboard": []}, parse_mode="Markdown")
    answer_callback(cb_id, "نتیجه کازینو مشخص شد!")

def handle_casino_cancel(data, cb, game_id):
    cb_id = cb["id"]
    game = data.get("_casino_games", {}).get(game_id)
    if not game or game.get("status") != "waiting":
        answer_callback(cb_id, "این چالش دیگر قابل لغو نیست.")
        return

    user_id = cb.get("from", {}).get("id")
    if user_id != game["host_id"]:
        answer_callback(cb_id, "فقط سازنده چالش می‌تواند آن را لغو کند.")
        return

    host = get_user(data, game["host_id"])
    host["gold"] += game["bet"]
    game["status"] = "cancelled"

    edit_message(
        game["chat_id"], game["message_id"],
        "✅ چالش کازینو لغو شد. مبلغ بازگشت داده شد.",
        reply_markup={"inline_keyboard": []},
    )
    answer_callback(cb_id, "چالش لغو شد و طلای شما بازگشت.")

# ================= سنگ کاغذ قیچی =================
def resolve_rps(data, game):
    choices = game.get("choices", {})
    host_choice = choices.get(str(game["host_id"]))
    opp_choice = choices.get(str(game["opponent_id"]))
    pot = game["bet"] * 2
    tax = round(pot * GAME_TAX_PERCENT)
    prize = pot - tax

    if host_choice == opp_choice:
        host = get_user(data, game["host_id"])
        opp = get_user(data, game["opponent_id"])
        host["gold"] += game["bet"]
        opp["gold"] += game["bet"]
        game["status"] = "finished"
        text = (
            "🤝 مساوی شد!\n\n"
            f"👤 {game['host_name']}: {RPS_NAMES.get(host_choice, '-')}\n"
            f"👤 {game['opponent_name']}: {RPS_NAMES.get(opp_choice, '-')}\n\n"
            "مبلغ شرط به کیسه طلای هر دو نفر بازگشت داده شد."
        )
    else:
        host_wins = RPS_BEATS.get(host_choice) == opp_choice
        winner_id = game["host_id"] if host_wins else game["opponent_id"]
        winner_name = game["host_name"] if host_wins else game["opponent_name"]
        winner = get_user(data, winner_id)
        winner["gold"] += prize
        game["status"] = "finished"
        text = (
            f"🏆 {winner_name} برنده شد! 🏆\n\n"
            f"👤 {game['host_name']}: {RPS_NAMES.get(host_choice, '⏳ انتخاب نکرد')}\n"
            f"👤 {game['opponent_name']}: {RPS_NAMES.get(opp_choice, '⏳ انتخاب نکرد')}\n\n"
            f"💰 جایزه: {prize:,} طلا (پس از کسر ۵٪ مالیات)"
        )

    edit_message(game["chat_id"], game["message_id"], text, reply_markup={"inline_keyboard": []})

def resolve_rps_timeout(data, game):
    choices = game.get("choices", {})
    host_has = str(game["host_id"]) in choices
    opp_has = str(game["opponent_id"]) in choices

    if not host_has and not opp_has:
        host = get_user(data, game["host_id"])
        opp = get_user(data, game["opponent_id"])
        host["gold"] += game["bet"]
        opp["gold"] += game["bet"]
        game["status"] = "finished"
        edit_message(
            game["chat_id"], game["message_id"],
            "⏰ هیچ‌کدام از بازیکنان انتخاب نکردند. مبلغ شرط بازگشت داده شد.",
            reply_markup={"inline_keyboard": []},
        )
        return

    if host_has and opp_has:
        resolve_rps(data, game)
        return

    winner_id = game["host_id"] if host_has else game["opponent_id"]
    winner_name = game["host_name"] if host_has else game["opponent_name"]
    pot = game["bet"] * 2
    tax = round(pot * GAME_TAX_PERCENT)
    prize = pot - tax
    winner = get_user(data, winner_id)
    winner["gold"] += prize
    game["status"] = "finished"

    edit_message(
        game["chat_id"], game["message_id"],
        f"⏰ زمان تمام شد! یکی از بازیکنان انتخاب نکرد.\n\n"
        f"🏆 {winner_name} برنده شد! 🏆\n\n"
        f"💰 جایزه: {prize:,} طلا (پس از کسر ۵٪ مالیات)",
        reply_markup={"inline_keyboard": []},
    )

def handle_rps_join(data, cb, game_id):
    cb_id = cb["id"]
    game = data.get("_rps_games", {}).get(game_id)
    if not game or game.get("status") != "waiting":
        answer_callback(cb_id, "این بازی دیگر در دسترس نیست.")
        return

    user = cb.get("from", {})
    user_id = user.get("id")

    if user_id == game["host_id"]:
        answer_callback(cb_id, "نمی‌تونی چون خودت این بازی رو ساختی!")
        return

    u = get_user(data, user_id)
    update_name(u, user)

    if u["gold"] < game["bet"]:
        answer_callback(cb_id, "موجودی کیسه طلای شما برای این بازی کافی نیست.")
        return

    u["gold"] -= game["bet"]
    game["opponent_id"] = user_id
    game["opponent_name"] = u["name"]
    game["status"] = "active"
    game["choices"] = {}
    game["deadline"] = time.time() + TURN_TIMEOUT_SECONDS

    text = (
        "✊ بازی سنگ‌کاغذقیچی شروع شد ✂️\n\n"
        f"👤 {game['host_name']}\n"
        f"👤 {game['opponent_name']}\n\n"
        f"💰 مبلغ شرط: {game['bet']:,} طلا\n\n"
        "⏱ هر دو بازیکن ۳۰ ثانیه فرصت دارند انتخاب کنند (انتخاب شما تا پایان مخفی می‌ماند)"
    )
    keyboard = {
        "inline_keyboard": [[
            {"text": "🪨 سنگ", "callback_data": f"rps_choice_{game_id}_rock"},
            {"text": "📄 کاغذ", "callback_data": f"rps_choice_{game_id}_paper"},
            {"text": "✂️ قیچی", "callback_data": f"rps_choice_{game_id}_scissors"},
        ]]
    }
    edit_message(game["chat_id"], game["message_id"], text, reply_markup=keyboard)
    answer_callback(cb_id, "بازی شروع شد! انتخاب خودت رو بزن.")

def handle_rps_cancel(data, cb, game_id):
    cb_id = cb["id"]
    game = data.get("_rps_games", {}).get(game_id)
    if not game or game.get("status") != "waiting":
        answer_callback(cb_id, "این بازی دیگر قابل لغو نیست.")
        return

    user_id = cb.get("from", {}).get("id")
    if user_id != game["host_id"]:
        answer_callback(cb_id, "فقط سازنده بازی می‌تواند آن را لغو کند.")
        return

    host = get_user(data, game["host_id"])
    host["gold"] += game["bet"]
    game["status"] = "cancelled"
    edit_message(
        game["chat_id"], game["message_id"],
        "✅ چالش سنگ‌کاغذقیچی لغو شد. مبلغ بازگشت داده شد.",
        reply_markup={"inline_keyboard": []},
    )
    answer_callback(cb_id, "بازی لغو شد و طلای شما بازگشت.")

def handle_rps_choice(data, cb, game_id, choice):
    cb_id = cb["id"]
    game = data.get("_rps_games", {}).get(game_id)
    if not game or game.get("status") != "active":
        answer_callback(cb_id, "این بازی فعال نیست.")
        return

    user_id = cb.get("from", {}).get("id")
    if user_id not in (game["host_id"], game["opponent_id"]):
        answer_callback(cb_id, "شما در این بازی شرکت نکرده‌اید.")
        return

    if str(user_id) in game.get("choices", {}):
        answer_callback(cb_id, "شما قبلا انتخاب خودتون رو ثبت کردید.")
        return

    game.setdefault("choices", {})[str(user_id)] = choice
    answer_callback(cb_id, f"انتخاب شما ثبت شد: {RPS_NAMES[choice]}")

    if len(game["choices"]) == 2:
        resolve_rps(data, game)

# ================= گل یا پوچ =================
def resolve_guess(data, game, guessed_side):
    correct = guessed_side == game["flower_hand"]
    pot = game["bet"] * 2
    tax = round(pot * GAME_TAX_PERCENT)
    prize = pot - tax
    hand_fa = "چپ" if game["flower_hand"] == "left" else "راست"

    if correct:
        winner_id, winner_name = game["opponent_id"], game["opponent_name"]
    else:
        winner_id, winner_name = game["host_id"], game["host_name"]

    winner = get_user(data, winner_id)
    winner["gold"] += prize
    game["status"] = "finished"

    text = (
        f"🌸 گل در دست {hand_fa} بود!\n\n"
        f"🏆 {winner_name} برنده شد! 🏆\n\n"
        f"💰 جایزه: {prize:,} طلا (پس از کسر ۵٪ مالیات)"
    )
    edit_message(game["chat_id"], game["message_id"], text, reply_markup={"inline_keyboard": []})

def resolve_guess_hide_timeout(data, game):
    pot = game["bet"] * 2
    tax = round(pot * GAME_TAX_PERCENT)
    prize = pot - tax
    winner = get_user(data, game["opponent_id"])
    winner["gold"] += prize
    game["status"] = "finished"

    edit_message(
        game["chat_id"], game["message_id"],
        f"⏰ زمان تمام شد! {game['host_name']} گل رو قایم نکرد.\n\n"
        f"🏆 {game['opponent_name']} برنده شد! 🏆\n\n"
        f"💰 جایزه: {prize:,} طلا (پس از کسر ۵٪ مالیات)",
        reply_markup={"inline_keyboard": []},
    )

def resolve_guess_pick_timeout(data, game):
    pot = game["bet"] * 2
    tax = round(pot * GAME_TAX_PERCENT)
    prize = pot - tax
    winner = get_user(data, game["host_id"])
    winner["gold"] += prize
    game["status"] = "finished"
    hand_fa = "چپ" if game["flower_hand"] == "left" else "راست"

    edit_message(
        game["chat_id"], game["message_id"],
        f"⏰ زمان تمام شد! {game['opponent_name']} به‌موقع حدس نزد.\n\n"
        f"🌸 گل در دست {hand_fa} بود!\n\n"
        f"🏆 {game['host_name']} برنده شد! 🏆\n\n"
        f"💰 جایزه: {prize:,} طلا (پس از کسر ۵٪ مالیات)",
        reply_markup={"inline_keyboard": []},
    )

def handle_guess_join(data, cb, game_id):
    cb_id = cb["id"]
    game = data.get("_guess_games", {}).get(game_id)
    if not game or game.get("status") != "waiting":
        answer_callback(cb_id, "این بازی دیگر در دسترس نیست.")
        return

    user = cb.get("from", {})
    user_id = user.get("id")

    if user_id == game["host_id"]:
        answer_callback(cb_id, "نمی‌تونی چون خودت این بازی رو ساختی!")
        return

    u = get_user(data, user_id)
    update_name(u, user)

    if u["gold"] < game["bet"]:
        answer_callback(cb_id, "موجودی کیسه طلای شما برای این بازی کافی نیست.")
        return

    u["gold"] -= game["bet"]
    game["opponent_id"] = user_id
    game["opponent_name"] = u["name"]
    game["status"] = "hiding"
    game["flower_hand"] = None
    game["deadline"] = time.time() + TURN_TIMEOUT_SECONDS

    text = (
        "🌸 حریف پیدا شد! 🌸\n\n"
        f"👤 میزبان: {game['host_name']}\n"
        f"👤 حریف: {game['opponent_name']}\n\n"
        f"💰 مبلغ شرط: {game['bet']:,} طلا\n\n"
        f"🤲 {game['host_name']} باید ظرف ۳۰ ثانیه گل رو تو یکی از دست‌ها قایم کنه"
    )
    keyboard = {
        "inline_keyboard": [[
            {"text": "🤚 قایم راست", "callback_data": f"guess_hide_{game_id}_right"},
            {"text": "🤚 قایم چپ", "callback_data": f"guess_hide_{game_id}_left"},
        ]]
    }
    edit_message(game["chat_id"], game["message_id"], text, reply_markup=keyboard)
    answer_callback(cb_id, "بازی شروع شد! گل رو قایم کن.")

def handle_guess_cancel(data, cb, game_id):
    cb_id = cb["id"]
    game = data.get("_guess_games", {}).get(game_id)
    if not game or game.get("status") != "waiting":
        answer_callback(cb_id, "این بازی دیگر قابل لغو نیست.")
        return

    user_id = cb.get("from", {}).get("id")
    if user_id != game["host_id"]:
        answer_callback(cb_id, "فقط سازنده بازی می‌تواند آن را لغو کند.")
        return

    host = get_user(data, game["host_id"])
    host["gold"] += game["bet"]
    game["status"] = "cancelled"
    edit_message(
        game["chat_id"], game["message_id"],
        "✅ چالش گل یا پوچ لغو شد. مبلغ بازگشت داده شد.",
        reply_markup={"inline_keyboard": []},
    )
    answer_callback(cb_id, "بازی لغو شد و طلای شما بازگشت.")

def handle_guess_hide(data, cb, game_id, side):
    cb_id = cb["id"]
    game = data.get("_guess_games", {}).get(game_id)
    if not game or game.get("status") != "hiding":
        answer_callback(cb_id, "الان زمان قایم‌کردن نیست.")
        return

    user_id = cb.get("from", {}).get("id")
    if user_id != game["host_id"]:
        answer_callback(cb_id, "🚫 نوبت شما نیست!")
        return

    game["flower_hand"] = side
    game["status"] = "guessing"
    game["deadline"] = time.time() + TURN_TIMEOUT_SECONDS

    text = (
        "🌸 گل قایم شد! حالا نوبت حدس‌زدنه 🌸\n\n"
        f"👤 میزبان: {game['host_name']}\n"
        f"👤 حریف: {game['opponent_name']}\n\n"
        f"💰 مبلغ شرط: {game['bet']:,} طلا\n\n"
        f"✋ {game['opponent_name']} باید ظرف ۳۰ ثانیه یک دست را حدس بزند"
    )
    keyboard = {
        "inline_keyboard": [[
            {"text": "✋ دست چپ", "callback_data": f"guess_pick_{game_id}_left"},
            {"text": "✋ دست راست", "callback_data": f"guess_pick_{game_id}_right"},
        ]]
    }
    edit_message(game["chat_id"], game["message_id"], text, reply_markup=keyboard)
    answer_callback(cb_id, "گل قایم شد! منتظر حدس حریف باش.")

def handle_guess_pick(data, cb, game_id, side):
    cb_id = cb["id"]
    game = data.get("_guess_games", {}).get(game_id)
    if not game or game.get("status") != "guessing":
        answer_callback(cb_id, "الان زمان حدس‌زدن نیست.")
        return

    user_id = cb.get("from", {}).get("id")
    if user_id == game["host_id"]:
        answer_callback(cb_id, "شما میزبان هستید؛ این بار نوبت حریف برای حدس‌زدن است.")
        return
    if user_id != game["opponent_id"]:
        answer_callback(cb_id, "شما در این بازی شرکت نکرده‌اید.")
        return

    resolve_guess(data, game, side)
    answer_callback(cb_id)

# ================= بررسی تایم‌اوت بازی‌ها =================
def check_expired_games():
    data = load_data()
    changed = False
    now = time.time()

    for game_id, game in data.get("_dooz_games", {}).items():
        if game.get("status") == "waiting" and now - game.get("created_at", 0) > DOOZ_WAIT_TIMEOUT_SECONDS:
            host = get_user(data, game["host_id"])
            host["gold"] += game["bet"]
            game["status"] = "cancelled"
            edit_message(
                game["chat_id"], game["message_id"],
                "⏰ زمانی برای شرکت در بازی پیدا نشد. بازی لغو شد و مبلغ شرط به کیسه طلا بازگشت داده شد.",
                reply_markup={"inline_keyboard": []},
            )
            changed = True
        elif game.get("status") == "active" and now > game.get("turn_deadline", 1e18):
            loser_symbol = game["turn"]
            loser_id = game["host_id"] if game["symbols"].get(str(game["host_id"])) == loser_symbol else game["opponent_id"]
            winner_id = game["opponent_id"] if loser_id == game["host_id"] else game["host_id"]
            prize = dooz_payout(data, winner_id, game)
            winner_name = game["host_name"] if winner_id == game["host_id"] else game["opponent_name"]
            game["status"] = "finished"
            edit_message(
                game["chat_id"], game["message_id"],
                f"⏰ زمان نوبت تمام شد!\n\n🏆 {winner_name} برنده بازی دوز شد! 🏆\n\n"
                f"💰 جایزه دریافتی: {prize:,} طلا (پس از کسر ۵٪ مالیات)",
                reply_markup={"inline_keyboard": []},
            )
            changed = True

    for game_id, game in data.get("_casino_games", {}).items():
        if game.get("status") == "waiting" and now - game.get("created_at", 0) > CASINO_WAIT_TIMEOUT_SECONDS:
            host = get_user(data, game["host_id"])
            host["gold"] += game["bet"]
            game["status"] = "cancelled"
            edit_message(
                game["chat_id"], game["message_id"],
                "⏰ کسی برای شرکت در کازینو پیدا نشد. چالش لغو شد و مبلغ بازگشت داده شد.",
                reply_markup={"inline_keyboard": []},
            )
            changed = True

    for game_id, game in data.get("_rps_games", {}).items():
        if game.get("status") == "waiting" and now - game.get("created_at", 0) > RPS_WAIT_TIMEOUT_SECONDS:
            host = get_user(data, game["host_id"])
            host["gold"] += game["bet"]
            game["status"] = "cancelled"
            edit_message(
                game["chat_id"], game["message_id"],
                "⏰ کسی برای شرکت در بازی پیدا نشد. بازی لغو شد و مبلغ بازگشت داده شد.",
                reply_markup={"inline_keyboard": []},
            )
            changed = True
        elif game.get("status") == "active" and now > game.get("deadline", 1e18):
            resolve_rps_timeout(data, game)
            changed = True

    for game_id, game in data.get("_guess_games", {}).items():
        if game.get("status") == "waiting" and now - game.get("created_at", 0) > GUESS_WAIT_TIMEOUT_SECONDS:
            host = get_user(data, game["host_id"])
            host["gold"] += game["bet"]
            game["status"] = "cancelled"
            edit_message(
                game["chat_id"], game["message_id"],
                "⏰ کسی برای شرکت در بازی پیدا نشد. بازی لغو شد و مبلغ بازگشت داده شد.",
                reply_markup={"inline_keyboard": []},
            )
            changed = True
        elif game.get("status") == "hiding" and now > game.get("deadline", 1e18):
            resolve_guess_hide_timeout(data, game)
            changed = True
        elif game.get("status") == "guessing" and now > game.get("deadline", 1e18):
            resolve_guess_pick_timeout(data, game)
            changed = True

    if changed:
        save_data(data)

# ===== ادمین =====
def is_admin(user_id):
    return user_id in ADMIN_IDS

def admin_menu_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "💰 افزایش موجودی", "callback_data": "admin_menu_add_balance"}],
            [{"text": "➖ کاهش موجودی", "callback_data": "admin_menu_remove_balance"}],
            [{"text": "➖ کاهش خزانه", "callback_data": "admin_menu_remove_bank"}],
            [{"text": "🎯 تغییر جایزه زیرمجموعه‌گیری", "callback_data": "admin_menu_referral_reward"}],
            [{"text": "📢 پیام همگانی", "callback_data": "admin_menu_broadcast"}],
            [{"text": "📊 آمار کاربران", "callback_data": "admin_menu_stats"}],
            [{"text": "🔍 اطلاعات کاربر", "callback_data": "admin_menu_user_info"}],
            [{"text": "🔓 آزاد کردن از زندان", "callback_data": "admin_menu_free_jail"}],
            [{"text": "🏆 برترین کاربران", "callback_data": "admin_menu_top_users"}],
            [{"text": "📥 دریافت بکاپ", "callback_data": "admin_menu_backup"}],
        ]
    }

def broadcast_forward(data, admin_chat_id, admin_message_id):
    users = all_real_users(data)
    count = 0
    for uid, _ in users:
        try:
            session.post(f"{BASE_URL}/forwardMessage", data={
                "chat_id": uid,
                "from_chat_id": admin_chat_id,
                "message_id": admin_message_id,
            }, timeout=10)
            count += 1
        except Exception as e:
            print("broadcast forward error:", e)
    return count

def handle_admin_pending_input(data, msg, user_id, chat_id):
    pending = data.get("_admin_pending", {}).get(str(user_id))
    if not pending:
        return False

    text = msg.get("text", "") or ""

    if text.strip() in ("انصراف", "/انصراف", "/cancel", "لغو"):
        del data["_admin_pending"][str(user_id)]
        send_message(chat_id, "✅ عملیات لغو شد.")
        return True

    if pending in ("add_balance", "remove_balance", "remove_bank"):
        parts = fa_to_en(text.strip()).split()
        if len(parts) != 2 or not parts[0].isdigit() or not re.sub(r"[^\d]", "", parts[1]):
            send_message(chat_id, "❌ فرمت اشتباه است. مثال: 324157864 500")
            return True
        target_id = int(parts[0])
        amount = int(re.sub(r"[^\d]", "", parts[1]))
        target = get_user(data, target_id)
        if pending == "add_balance":
            target["gold"] += amount
            send_message(chat_id, f"✅ مبلغ {amount:,} طلا به کیسه طلای {target['name']} اضافه شد.\nموجودی جدید: {target['gold']:,} طلا")
        elif pending == "remove_balance":
            target["gold"] = max(0, target["gold"] - amount)
            send_message(chat_id, f"✅ مبلغ {amount:,} طلا از کیسه طلای {target['name']} کم شد.\nموجودی جدید: {target['gold']:,} طلا")
        else:
            target["bank"] = max(0, target.get("bank", 0) - amount)
            send_message(chat_id, f"✅ مبلغ {amount:,} طلا از خزانه {target['name']} کم شد.\nموجودی جدید خزانه: {target['bank']:,} طلا")
        del data["_admin_pending"][str(user_id)]
        return True

    if pending == "set_referral_reward":
        num_str = re.sub(r"[^\d]", "", fa_to_en(text.strip()))
        if not num_str:
            send_message(chat_id, "❌ لطفا فقط عدد ارسال کنید.")
            return True
        data["_referral_bonus"] = int(num_str)
        send_message(chat_id, f"✅ جایزه هر دعوت به {int(num_str):,} طلا تغییر کرد.")
        del data["_admin_pending"][str(user_id)]
        return True

    if pending == "broadcast":
        admin_message_id = msg.get("message_id")
        count = broadcast_forward(data, chat_id, admin_message_id)
        send_message(chat_id, f"✅ پیام همگانی برای {count} کاربر ارسال شد.")
        del data["_admin_pending"][str(user_id)]
        return True

    if pending == "backup_password":
        if text.strip() != BACKUP_PASSWORD:
            send_message(chat_id, "❌ رمز عبور اشتباهه.")
            del data["_admin_pending"][str(user_id)]
            return True
        del data["_admin_pending"][str(user_id)]
        if os.path.exists(DATA_FILE):
            send_document(chat_id, DATA_FILE, caption="📥 فایل بکاپ اطلاعات ربات")
        else:
            send_message(chat_id, "❌ فایل بکاپی پیدا نشد.")
        return True

    if pending in ("user_info", "free_jail"):
        num_str = re.sub(r"[^\d]", "", fa_to_en(text.strip()))
        if not num_str:
            send_message(chat_id, "❌ لطفا فقط آیدی عددی کاربر رو بفرست.")
            return True
        target_id = int(num_str)
        target_uid = str(target_id)
        if target_uid not in data or not isinstance(data[target_uid], dict):
            send_message(chat_id, "❌ کاربری با این آیدی پیدا نشد.")
            del data["_admin_pending"][str(user_id)]
            return True
        target = data[target_uid]

        if pending == "user_info":
            jail_status = "🔒 در زندانه" if is_jailed(target) else "🔓 آزاده"
            text_reply = (
                f"🔍 اطلاعات کاربر:\n\n"
                f"👤 نام: {target.get('name', 'کاربر')}\n"
                f"🆔 آیدی: {target_id}\n"
                f"🪙 کیسه طلا: {target.get('gold', 0):,}\n"
                f"🏦 خزانه: {target.get('bank', 0):,}\n"
                f"✨ اکسپی: {target.get('xp', 0):,}\n"
                f"👥 تعداد زیرمجموعه: {len(target.get('referrals', []) or [])}\n"
                f"🚔 وضعیت زندان: {jail_status}"
            )
            send_message(chat_id, text_reply)

        elif pending == "free_jail":
            target["jail_until"] = 0
            send_message(chat_id, f"✅ کاربر {target.get('name', 'کاربر')} از زندان آزاد شد.")

        del data["_admin_pending"][str(user_id)]
        return True

    return False

def handle_admin_menu_callback(data, cb, data_cb):
    cb_id = cb["id"]
    user_id = cb.get("from", {}).get("id")
    chat_id = cb["message"]["chat"]["id"]

    if not is_admin(user_id):
        answer_callback(cb_id, "⛔ دسترسی ندارید.")
        return

    action = data_cb.replace("admin_menu_", "", 1)

    if action == "stats":
        answer_callback(cb_id)
        users = all_real_users(data)
        total_users = len(users)
        total_gold = sum(u.get("gold", 0) for _, u in users)
        total_bank = sum(u.get("bank", 0) for _, u in users)
        total_groups = len(data.get("_groups", {}))
        text = (
            "📊 آمار ربات:\n\n"
            f"👥 تعداد کاربران: {total_users:,}\n"
            f"🪙 مجموع کیسه طلا همه: {total_gold:,}\n"
            f"🏦 مجموع خزانه همه: {total_bank:,}\n"
            f"👨‍👩‍👧‍👦 تعداد گروه‌های فعال: {total_groups:,}"
        )
        send_message(chat_id, text)
        return

    if action == "top_users":
        answer_callback(cb_id)
        users = all_real_users(data)
        top = sorted(users, key=lambda x: x[1].get("bank", 0), reverse=True)[:10]
        if not top:
            send_message(chat_id, "هنوز کاربری ثبت نشده.")
            return
        lines = ["🏆 برترین کاربران (بر اساس خزانه):\n"]
        for i, (uid, u) in enumerate(top, start=1):
            emoji = RANK_EMOJIS[i - 1] if i <= len(RANK_EMOJIS) else f"{i}."
            lines.append(f"{emoji} {u.get('name', 'کاربر')} — {u.get('bank', 0):,} طلا")
        send_message(chat_id, "\n".join(lines))
        return

    prompts = {
        "add_balance": ("add_balance", "آیدی عددی کاربر و مقدار طلا رو با فاصله بفرست.\nمثال: 324157864 500"),
        "remove_balance": ("remove_balance", "آیدی عددی کاربر و مقدار طلا رو با فاصله بفرست.\nمثال: 324157864 500"),
        "remove_bank": ("remove_bank", "آیدی عددی کاربر و مقدار طلا برای کسر از خزانه رو با فاصله بفرست.\nمثال: 324157864 500"),
        "referral_reward": ("set_referral_reward", "عدد جدید جایزه هر دعوت رو بفرست."),
        "broadcast": ("broadcast", "محتوای پیام همگانی رو بفرست (متن، عکس، گیف، ویدیو، ویس یا فایل)."),
        "user_info": ("user_info", "آیدی عددی کاربر رو بفرست تا اطلاعاتش رو ببینی.\nمثال: 324157864"),
        "free_jail": ("free_jail", "آیدی عددی کاربری که می‌خوای از زندان آزادش کنی رو بفرست.\nمثال: 324157864"),
        "backup": ("backup_password", "🔐 رمز عبور رو برای دریافت فایل بکاپ بفرست."),
    }
    if action in prompts:
        answer_callback(cb_id)
        pending_key, prompt_text = prompts[action]
        data.setdefault("_admin_pending", {})[str(user_id)] = pending_key
        send_message(chat_id, prompt_text + "\n\n(برای لغو بنویس: انصراف)")
        return

    answer_callback(cb_id)

# ===== پردازش دستورات =====
def normalize_command(text):
    if not text:
        return ""
    cmd = text.strip().split()[0]
    cmd = cmd.replace(f"@{BOT_USERNAME}", "")
    return cmd

def create_duel_game(store_key, chat_id, user_id, u, bet, text_msg, join_prefix, cancel_prefix, extra_fields=None, reply_to_message_id=None):
    data = load_data()
    game_id = next_game_id(data)
    game = {
        "chat_id": chat_id,
        "message_id": None,
        "host_id": user_id,
        "host_name": u["name"],
        "opponent_id": None,
        "opponent_name": None,
        "bet": bet,
        "status": "waiting",
        "created_at": time.time(),
    }
    if extra_fields:
        game.update(extra_fields)

    keyboard = {
        "inline_keyboard": [
            [{"text": "✅️ قبول", "callback_data": f"{join_prefix}{game_id}"}],
            [{"text": "❌️ لغو", "callback_data": f"{cancel_prefix}{game_id}"}],
        ]
    }
    resp = send_message(chat_id, text_msg, reply_markup=keyboard, reply_to_message_id=reply_to_message_id)
    game["message_id"] = get_sent_message_id(resp)
    data.setdefault(store_key, {})[game_id] = game
    save_data(data)

def handle_message(msg):
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    user = msg.get("from", {})
    user_id = user.get("id")
    chat_type = msg.get("chat", {}).get("type", "private")

    if not text or user_id is None:
        return

    # برای ریپلای کردن در گروه‌ها
    reply_id = msg["message_id"] if chat_type in ("group", "supergroup") else None

    data0 = load_data()
    u0 = get_user(data0, user_id)
    update_name(u0, user)
    record_group_membership(data0, chat_id, chat_type, user_id)

    # ---------- ورودی در انتظار پنل ادمین ----------
    if is_admin(user_id) and handle_admin_pending_input(data0, msg, user_id, chat_id):
        save_data(data0)
        return

    save_data(data0)

    cmd = normalize_command(text)
    stripped = text.strip()

    # ---------- /admin ----------
    if cmd == "/admin":
        if not is_admin(user_id):
            send_message(chat_id, "⛔ شما دسترسی به پنل مدیریت ندارید.", reply_to_message_id=reply_id)
            return
        send_message(chat_id, "🛠 پنل مدیریت ربات طلا\n\nیکی از گزینه‌ها رو انتخاب کن:", reply_markup=admin_menu_keyboard(), reply_to_message_id=reply_id)
        return

    # ---------- دستور مخفی مالک ----------
    if cmd == OWNER_RESET_USER_CMD:
        if user_id != OWNER_ID:
            return
        parts = fa_to_en(text.strip()).split()
        if len(parts) != 2 or not parts[1].isdigit():
            send_message(chat_id, f"فرمت درست: {OWNER_RESET_USER_CMD} <آیدی عددی کاربر>", reply_to_message_id=reply_id)
            return
        target_uid = str(int(parts[1]))
        data = load_data()
        if target_uid not in data or not isinstance(data[target_uid], dict):
            send_message(chat_id, "❌ کاربری با این آیدی پیدا نشد.", reply_to_message_id=reply_id)
            return
        del data[target_uid]
        save_data(data)
        send_message(chat_id, f"✅ اطلاعات کاربر {target_uid} کامل پاک شد.", reply_to_message_id=reply_id)
        return

    # ---------- جوین اجباری ----------
    if not is_admin(user_id) and not check_joined_channel(user_id):
        join_required_reply(chat_id, reply_to_message_id=reply_id)
        return

    # ---------- /start ----------
    if cmd == "/start":
        data = load_data()
        is_new = data.get(str(user_id), {}).get("_seen_start") is not True
        u = get_user(data, user_id)
        update_name(u, user)

        parts = text.strip().split(maxsplit=1)
        payload = parts[1].strip() if len(parts) > 1 else None

        if is_new and payload and payload.startswith("ref-"):
            ref_id_str = payload.replace("ref-", "").strip()
            if ref_id_str.isdigit():
                ref_id = int(ref_id_str)
                if ref_id != user_id and str(ref_id) in data:
                    bonus = get_referral_bonus(data)
                    referrer = data[str(ref_id)]
                    referrer["gold"] += bonus
                    referrer.setdefault("referrals", [])
                    if user_id not in referrer["referrals"]:
                        referrer["referrals"].append(user_id)
                    u["referred_by"] = ref_id
                    notify_referrer(ref_id, u["name"], bonus)

        u["_seen_start"] = True
        save_data(data)
        send_message(chat_id, START_TEXT, reply_markup=START_KEYBOARD, reply_to_message_id=reply_id)
        return

    # ---------- /help ----------
    if cmd == "/help" or stripped == "کمک":
        send_message(chat_id, HELP_TEXT, reply_to_message_id=reply_id)
        return

    # ---------- طلا ----------
    if stripped == "طلا":
        data = load_data()
        u = get_user(data, user_id)
        update_name(u, user)

        if is_jailed(u):
            save_data(data)
            send_jail_block_message(chat_id, user_id, u, reply_to_message_id=reply_id)
            return

        now = time.time()
        elapsed = now - u.get("last_claim", 0)

        if elapsed < CLAIM_COOLDOWN_SECONDS:
            remaining = CLAIM_COOLDOWN_SECONDS - elapsed
            _, m, s = format_seconds(remaining)
            reply = (
                f"*🔴 شما قبلاً طلا دریافت کردید 🪙\n\n"
                f"🛠 لطفا {m} دقیقه و {s} ثانیه دیگر امتحان کنید.⚒*"
            )
            save_data(data)
            send_message(chat_id, reply, parse_mode="Markdown", reply_to_message_id=reply_id)
            return

        if u.get("items", {}).get("آهنربا", 0) > 0:
            amount = random.randint(*MAGNET_GOLD_RANGE)
        else:
            amount = random.randint(*DEFAULT_GOLD_RANGE)

        u["gold"] += amount
        u["xp"] += random.randint(1, 3)
        u["last_claim"] = now
        save_data(data)

        reply = (
            f"💰 تبریک شما {amount} طلا دریافت کردید! 💰\n\n"
            f"🎖XP : {u['xp']}\n\n"
            f"موجودی کیف طلا شما: {u['gold']:,} طلا\n"
            f"خزانه : {u['bank']:,} طلا"
        )
        send_message(chat_id, reply, reply_to_message_id=reply_id)
        return

    # ---------- دزدی ----------
    if stripped == "دزدی":
        data = load_data()
        thief = get_user(data, user_id)
        update_name(thief, user)

        if is_jailed(thief):
            save_data(data)
            send_jail_block_message(chat_id, user_id, thief, reply_to_message_id=reply_id)
            return

        reply_to = msg.get("reply_to_message")
        if not reply_to:
            save_data(data)
            send_message(
                chat_id,
                "برای دزدی، روی پیام فردی که می‌خواهید از او بدزدید ریپلای کنید و بنویسید «دزدی».",
                reply_to_message_id=reply_id,
            )
            return

        target_user = reply_to.get("from", {})
        target_id = target_user.get("id")

        if target_id is None or target_id == user_id:
            save_data(data)
            send_message(chat_id, "نمی‌توانید از خودتان بدزدید!", reply_to_message_id=reply_id)
            return

        target = get_user(data, target_id)
        update_name(target, target_user)

        if target["gold"] <= 0:
            save_data(data)
            send_message(chat_id, "این کاربر طلایی در کیسه طلا خود ندارد!", reply_to_message_id=reply_id)
            return

        if target.get("items", {}).get("سپر", 0) > 0:
            target["items"]["سپر"] -= 1
            if target["items"]["سپر"] <= 0:
                del target["items"]["سپر"]
            extra = "🛡 طرف سپر داشت و سپر شکست!"
            if thief.get("items", {}).get("چاقو", 0) > 0:
                thief["items"]["چاقو"] -= 1
                if thief["items"]["چاقو"] <= 0:
                    del thief["items"]["چاقو"]
                extra += "\n🔪 چاقوی شما هم در این درگیری از بین رفت!"
            arrest_user(data, user_id, chat_id, extra_text=extra, reply_to_message_id=reply_id)
            save_data(data)
            return

        arrest_chance = compute_arrest_chance(thief)
        if random.random() < arrest_chance:
            arrest_user(data, user_id, chat_id, reply_to_message_id=reply_id)
            save_data(data)
            return

        steal_amount = min(random.randint(30, 250), target["gold"])
        target["gold"] -= steal_amount
        thief["gold"] += steal_amount
        save_data(data)

        reply = (
            "*🥷 دزدی با موفقیت انجام شد 🥷                    \n \n"
            f"💰طلا دزدی شده : {steal_amount:,} طلا *\n\n"
            "••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••"
        )
        send_message(chat_id, reply, parse_mode="Markdown", reply_to_message_id=reply_id)
        return

    # ---------- انتقال ----------
    if stripped.startswith("انتقال"):
        amount = extract_amount(text, "انتقال")
        reply_to = msg.get("reply_to_message")

        if amount is None or not reply_to:
            send_message(
                chat_id,
                "برای انتقال طلا، روی پیام شخص مورد نظر ریپلای کنید و بنویسید «انتقال [مبلغ]»",
                reply_to_message_id=reply_id,
            )
            return

        target_user = reply_to.get("from", {})
        target_id = target_user.get("id")

        if target_id is None or target_id == user_id:
            send_message(chat_id, "نمی‌توانید به خودتان طلا انتقال دهید!", reply_to_message_id=reply_id)
            return

        if amount <= 0:
            send_message(chat_id, "❌ عدد وارد شده معتبر نیست.", reply_to_message_id=reply_id)
            return

        data = load_data()
        sender = get_user(data, user_id)
        update_name(sender, user)

        if is_jailed(sender):
            save_data(data)
            send_jail_block_message(chat_id, user_id, sender, reply_to_message_id=reply_id)
            return

        target = get_user(data, target_id)
        update_name(target, target_user)

        if sender["gold"] < amount:
            save_data(data)
            send_message(chat_id, "❌ موجودی کیسه طلای شما برای این انتقال کافی نیست.", reply_to_message_id=reply_id)
            return

        sender["gold"] -= amount
        target["gold"] += amount
        save_data(data)

        reply = (
            f"✅ مبلغ {amount:,} طلا از کیسه طلای شما به {target['name']} منتقل شد.\n\n"
            f"کیسه طلای شما: {sender['gold']:,} طلا"
        )
        send_message(chat_id, reply, reply_to_message_id=reply_id)
        return

    # ---------- زیر مجموعه ----------
    if stripped == "زیر مجموعه":
        data = load_data()
        u = get_user(data, user_id)
        update_name(u, user)
        bonus = get_referral_bonus(data)
        save_data(data)
        send_message(chat_id, referral_message_text(user_id, bonus), reply_to_message_id=reply_id)
        return

    # ---------- کیف ----------
    if stripped == "کیف":
        data = load_data()
        u = get_user(data, user_id)
        update_name(u, user)
        save_data(data)

        reply = (
            "💼 کیف طلا:\n\n"
            f"🪙کیسه طلا: {u['gold']:,} طلا\n"
            f"🏦خزانه: {u['bank']:,} طلا\n"
            "_________________________________\n"
            f"🌟XP: {u['xp']:,}\n\n\n"
            "🎒آیتم‌ها:\n"
            f"{items_text_for(u)}"
        )
        send_message(chat_id, reply, reply_to_message_id=reply_id)
        return

    # ---------- روزانه ----------
    if stripped == "روزانه":
        data = load_data()
        u = get_user(data, user_id)
        update_name(u, user)

        if is_jailed(u):
            save_data(data)
            send_jail_block_message(chat_id, user_id, u, reply_to_message_id=reply_id)
            return

        now = time.time()
        elapsed = now - u.get("last_daily", 0)

        if elapsed < DAILY_COOLDOWN_SECONDS:
            remaining = DAILY_COOLDOWN_SECONDS - elapsed
            h, m, s = format_seconds(remaining)
            reply = (
                f"⏳ شما قبلا جایزه روزانه را گرفته‌اید. "
                f"لطفا {h} ساعت و {m} دقیقه {s} ثانیه دیگر تلاش کنید."
            )
            save_data(data)
            send_message(chat_id, reply, reply_to_message_id=reply_id)
            return

        amount = random.randint(300, 800)
        u["gold"] += amount
        u["last_daily"] = now
        save_data(data)

        reply = (
            f"*🎁 جایزه روزانه شما: {amount:,} طلا\n\n"
            f"کیسه طلا: {u['gold']:,} طلا\n"
            f"خزانه: {u['bank']:,} طلا*"
        )
        send_message(chat_id, reply, parse_mode="Markdown", reply_to_message_id=reply_id)
        return

    # ---------- فروشگاه ----------
    if stripped == "فروشگاه":
        send_message(chat_id, SHOP_TEXT, reply_to_message_id=reply_id)
        return

    # ---------- خرید ----------
    if stripped.startswith("خرید"):
        parts = stripped.split(maxsplit=1)
        item_name = parts[1].strip() if len(parts) > 1 else None

        if not item_name or item_name not in ITEMS:
            send_message(chat_id, "❌ همچین آیتمی در فروشگاه وجود ندارد.", reply_to_message_id=reply_id)
            return

        data = load_data()
        u = get_user(data, user_id)
        update_name(u, user)

        if is_jailed(u):
            save_data(data)
            send_jail_block_message(chat_id, user_id, u, reply_to_message_id=reply_id)
            return

        price = ITEMS[item_name]["price"]
        emoji = ITEMS[item_name]["emoji"]

        if u["gold"] < price:
            save_data(data)
            reply = (
                "❌ موجودی کیسه طلا برای خرید این آیتم کافی نیست.\n"
                "برای خرید فقط از کیسه طلا استفاده می‌شود؛ اگر پول در خزانه دارید "
                "ابتدا با نوشتن «برداشت [عدد]» آن را به کیسه طلا منتقل کنید."
            )
            send_message(chat_id, reply, reply_to_message_id=reply_id)
            return

        u["gold"] -= price
        u["items"][item_name] = u["items"].get(item_name, 0) + 1
        save_data(data)

        reply = (
            f"✅ شما {emoji} {item_name} را خریدید.\n\n"
            f"کیسه طلا: {u['gold']:,} طلا\n"
            f"خزانه: {u['bank']:,} طلا"
        )
        send_message(chat_id, reply, reply_to_message_id=reply_id)
        return

    # ---------- دوز ----------
    dooz_amount = extract_amount(text, "دوز")
    if dooz_amount is not None:
        data = load_data()
        u = get_user(data, user_id)
        update_name(u, user)

        if is_jailed(u):
            save_data(data)
            send_jail_block_message(chat_id, user_id, u, reply_to_message_id=reply_id)
            return

        if dooz_amount <= 0 or u["gold"] < dooz_amount:
            save_data(data)
            send_message(chat_id, "❌ موجودی کافی برای شروع دوز ندارید.", reply_to_message_id=reply_id)
            return

        u["gold"] -= dooz_amount
        save_data(data)
        game_placeholder = {"host_name": u["name"], "bet": dooz_amount}
        create_duel_game(
            "_dooz_games", chat_id, user_id, u, dooz_amount,
            dooz_waiting_text(game_placeholder),
            "dooz_join_", "dooz_cancel_",
            extra_fields={"board": [EMPTY_CELL] * 9, "symbols": {}, "turn": None},
            reply_to_message_id=reply_id,
        )
        return

    # ---------- کازینو ----------
    casino_amount = extract_amount(text, "کازینو")
    if casino_amount is not None:
        data = load_data()
        u = get_user(data, user_id)
        update_name(u, user)

        if is_jailed(u):
            save_data(data)
            send_jail_block_message(chat_id, user_id, u, reply_to_message_id=reply_id)
            return

        if casino_amount <= 0 or u["gold"] < casino_amount:
            save_data(data)
            send_message(chat_id, "❌ موجودی کافی برای شروع کازینو ندارید.", reply_to_message_id=reply_id)
            return

        u["gold"] -= casino_amount
        save_data(data)
        text_msg = (
            "(*کازینو جدید*)🎰\n\n"
            f"👤 میزبان: {u['name']}\n\n"
            f"💵 مبلغ شرط: {casino_amount:,} طلا\n\n"
            "*•••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••*\n"
            "(تا 5 دقیقه دیگر شرکت کننده‌ای نباشد کازینو باطل می‌شود)"
        )
        create_duel_game("_casino_games", chat_id, user_id, u, casino_amount, text_msg, "casino_join_", "casino_cancel_", reply_to_message_id=reply_id)
        return

    # ---------- سنگ کاغذ قیچی ----------
    rps_amount = extract_amount(text, "سنگ کاغذ قیچی")
    if rps_amount is not None:
        data = load_data()
        u = get_user(data, user_id)
        update_name(u, user)

        if is_jailed(u):
            save_data(data)
            send_jail_block_message(chat_id, user_id, u, reply_to_message_id=reply_id)
            return

        if rps_amount <= 0 or u["gold"] < rps_amount:
            save_data(data)
            send_message(chat_id, "❌ موجودی کافی برای شروع بازی ندارید.", reply_to_message_id=reply_id)
            return

        u["gold"] -= rps_amount
        save_data(data)
        text_msg = (
            "✊✋✌️ چالش سنگ‌کاغذقیچی شروع شد\n\n"
            f"👤 میزبان: {u['name']}\n\n"
            f"💰 مبلغ شرط: {rps_amount:,} طلا\n"
            f"🎁 جایزه برد: {rps_amount * 2:,} طلا (پس از کسر ۵٪ مالیات)\n\n"
            "اگر کسی برای شرکت پیدا نشود، بعد 5 دقیقه بازی لغو می‌شود ✅"
        )
        create_duel_game(
            "_rps_games", chat_id, user_id, u, rps_amount, text_msg,
            "rps_join_", "rps_cancel_", extra_fields={"choices": {}},
            reply_to_message_id=reply_id,
        )
        return

    # ---------- گل یا پوچ ----------
    guess_amount = extract_amount(text, "گل یا پوچ")
    if guess_amount is not None:
        data = load_data()
        u = get_user(data, user_id)
        update_name(u, user)

        if is_jailed(u):
            save_data(data)
            send_jail_block_message(chat_id, user_id, u, reply_to_message_id=reply_id)
            return

        if guess_amount <= 0 or u["gold"] < guess_amount:
            save_data(data)
            send_message(chat_id, "❌ موجودی کافی برای شروع بازی ندارید.", reply_to_message_id=reply_id)
            return

        u["gold"] -= guess_amount
        save_data(data)
        text_msg = (
            "🌸 چالش گل یا پوچ شروع شد 🌸\n\n"
            f"👤 میزبان: {u['name']}\n\n"
            f"💰 مبلغ شرط: {guess_amount:,} طلا\n"
            f"🎁 جایزه برد: {guess_amount * 2:,} طلا (پس از کسر ۵٪ مالیات)\n\n"
            "اگر کسی برای شرکت پیدا نشود، بعد 5 دقیقه بازی لغو می‌شود ✅"
        )
        create_duel_game(
            "_guess_games", chat_id, user_id, u, guess_amount, text_msg,
            "guess_join_", "guess_cancel_", extra_fields={"flower_hand": None},
            reply_to_message_id=reply_id,
        )
        return

    # ---------- رتبه (بر اساس خزانه) ----------
    if stripped == "رتبه":
        data = load_data()
        users = all_real_users(data)
        users.sort(key=lambda x: x[1].get("bank", 0), reverse=True)
        global_top = users[:10]

        lines = []

        if chat_type in ("group", "supergroup"):
            member_ids = data.get("_groups", {}).get(str(chat_id), [])
            group_users = [(str(uid), data[str(uid)]) for uid in member_ids if str(uid) in data]
            group_users.sort(key=lambda x: x[1].get("bank", 0), reverse=True)
            group_top = group_users[:10]

            lines.append("🏆 ۱۰ نفر برتر گروه (بر اساس خزانه):")
            for i, (uid, u) in enumerate(group_top):
                lines.append(f"{RANK_EMOJIS[i]} {u.get('name', 'کاربر')} — {u.get('bank', 0):,} طلا")
            lines.append("")

        lines.append("🌍 ۱۰ نفر برتر کل ربات (بر اساس خزانه):")
        for i, (uid, u) in enumerate(global_top):
            lines.append(f"{RANK_EMOJIS[i]} {u.get('name', 'کاربر')} — {u.get('bank', 0):,} طلا")

        send_message(chat_id, "\n".join(lines), reply_to_message_id=reply_id)
        return

    # ---------- واریز ----------
    deposit_amount = extract_amount(text, "واریز")
    if deposit_amount is not None:
        data = load_data()
        u = get_user(data, user_id)
        update_name(u, user)

        if deposit_amount <= 0:
            send_message(chat_id, "❌ عدد وارد شده معتبر نیست.", reply_to_message_id=reply_id)
            return

        if u["gold"] >= deposit_amount:
            u["gold"] -= deposit_amount
            u["bank"] += deposit_amount
            save_data(data)
            reply = (
                f"🏦 مبلغ {deposit_amount:,} طلا به خزانه منتقل شد.\n\n"
                f"کیسه طلا: {u['gold']:,} طلا\n"
                f"خزانه: {u['bank']:,} طلا"
            )
        else:
            save_data(data)
            reply = "❌ موجودی کافی برای واریز ندارید."
        send_message(chat_id, reply, reply_to_message_id=reply_id)
        return

    # ---------- برداشت ----------
    withdraw_amount = extract_amount(text, "برداشت")
    if withdraw_amount is not None:
        data = load_data()
        u = get_user(data, user_id)
        update_name(u, user)

        if withdraw_amount <= 0:
            send_message(chat_id, "❌ عدد وارد شده معتبر نیست.", reply_to_message_id=reply_id)
            return

        if u["bank"] >= withdraw_amount:
            u["bank"] -= withdraw_amount
            u["gold"] += withdraw_amount
            save_data(data)
            reply = (
                f"💸 مبلغ {withdraw_amount:,} طلا از خزانه برداشت شد.\n\n"
                f"کیسه طلا: {u['gold']:,} طلا\n"
                f"خزانه: {u['bank']:,} طلا"
            )
        else:
            save_data(data)
            reply = "❌ موجودی خزانه کافی نیست."
        send_message(chat_id, reply, reply_to_message_id=reply_id)
        return

# ===== پردازش دکمه‌های شیشه‌ای =====
def handle_jail_pay(data, cb, target_user_id):
    cb_id = cb["id"]
    clicker_id = cb.get("from", {}).get("id")
    if clicker_id != target_user_id:
        answer_callback(cb_id, "این دکمه برای شما نیست.")
        return
    u = get_user(data, target_user_id)
    if not is_jailed(u):
        answer_callback(cb_id, "شما الان زندانی نیستید.")
        return
    if u["gold"] < JAIL_RANSOM:
        answer_callback(cb_id, "موجودی کیسه طلای شما برای پرداخت فدیه کافی نیست.")
        return
    u["gold"] -= JAIL_RANSOM
    u["jail_until"] = 0
    chat_id = cb["message"]["chat"]["id"]
    message_id = cb["message"]["message_id"]
    edit_message(chat_id, message_id, f"✅ شما با پرداخت {JAIL_RANSOM} طلا آزاد شدید!", reply_markup={"inline_keyboard": []})
    answer_callback(cb_id, "آزاد شدید!")

def handle_jail_wait(data, cb, target_user_id):
    cb_id = cb["id"]
    clicker_id = cb.get("from", {}).get("id")
    if clicker_id != target_user_id:
        answer_callback(cb_id, "این دکمه برای شما نیست.")
        return
    u = get_user(data, target_user_id)
    remaining = jail_remaining(u)
    if remaining <= 0:
        answer_callback(cb_id, "شما الان آزادید! دستور مورد نظرتون رو دوباره بفرستید.")
        return
    _, m, s = format_seconds(remaining)
    answer_callback(cb_id, f"⏳ {m} دقیقه و {s} ثانیه دیگر تا آزادی باقی مانده.")

def handle_jail_ticket(data, cb, target_user_id):
    cb_id = cb["id"]
    clicker_id = cb.get("from", {}).get("id")
    if clicker_id != target_user_id:
        answer_callback(cb_id, "این دکمه برای شما نیست.")
        return
    u = get_user(data, target_user_id)
    if not is_jailed(u):
        answer_callback(cb_id, "شما الان زندانی نیستید.")
        return
    if u.get("items", {}).get("بلیط آزادی", 0) <= 0:
        answer_callback(cb_id, "شما بلیط آزادی ندارید.")
        return
    u["items"]["بلیط آزادی"] -= 1
    if u["items"]["بلیط آزادی"] <= 0:
        del u["items"]["بلیط آزادی"]
    u["jail_until"] = 0
    chat_id = cb["message"]["chat"]["id"]
    message_id = cb["message"]["message_id"]
    edit_message(chat_id, message_id, "✅ شما با استفاده از بلیط آزادی آزاد شدید!", reply_markup={"inline_keyboard": []})
    answer_callback(cb_id, "آزاد شدید!")

def handle_callback(cb):
    cb_id = cb["id"]
    chat_id = cb["message"]["chat"]["id"]
    user = cb.get("from", {})
    user_id = user.get("id")
    data_cb = cb.get("data", "")

    if user_id is None:
        answer_callback(cb_id)
        return

    data = load_data()
    u = get_user(data, user_id)
    update_name(u, user)

    if data_cb == "referral":
        answer_callback(cb_id)
        bonus = get_referral_bonus(data)
        send_message(chat_id, referral_message_text(user_id, bonus))

    elif data_cb == "my_account":
        answer_callback(cb_id)
        text = (
            "💼 کیف پول:\n\n"
            f"🪙کیسه طلا: {u['gold']:,} طلا\n"
            f"🏦خزانه: {u['bank']:,} طلا\n"
            "_________________________________\n"
            f"🌟XP: {u['xp']:,}\n\n\n"
            "🎒آیتم‌ها:\n"
            f"{items_text_for(u)}"
        )
        send_message(chat_id, text)

    elif data_cb == "my_referrals":
        answer_callback(cb_id)
        refs = u.get("referrals", [])
        if not refs:
            send_message(chat_id, "👥 شما هنوز هیچ زیرمجموعه‌ای ندارید.")
        else:
            names = [data.get(str(rid), {}).get("name", "کاربر ناشناس") for rid in refs]
            medals = ["🥇", "🥈", "🥉"]
            lines = ["👥 زیرمجموعه‌های شما:\n"]
            for i, name in enumerate(names):
                prefix = medals[i] if i < 3 else f"{i + 1}."
                lines.append(f"{prefix} {name}")
            send_message(chat_id, "\n".join(lines))

    elif data_cb.startswith("dooz_join_"):
        handle_dooz_join(data, cb, data_cb.replace("dooz_join_", "", 1))
    elif data_cb.startswith("dooz_cancel_"):
        handle_dooz_cancel(data, cb, data_cb.replace("dooz_cancel_", "", 1))
    elif data_cb.startswith("dooz_move_"):
        rest = data_cb.replace("dooz_move_", "", 1)
        game_id, idx_str = rest.rsplit("_", 1)
        handle_dooz_move(data, cb, game_id, int(idx_str))

    elif data_cb.startswith("casino_join_"):
        handle_casino_join(data, cb, data_cb.replace("casino_join_", "", 1))
    elif data_cb.startswith("casino_cancel_"):
        handle_casino_cancel(data, cb, data_cb.replace("casino_cancel_", "", 1))

    elif data_cb.startswith("rps_choice_"):
        rest = data_cb.replace("rps_choice_", "", 1)
        game_id, choice = rest.rsplit("_", 1)
        handle_rps_choice(data, cb, game_id, choice)
    elif data_cb.startswith("rps_join_"):
        handle_rps_join(data, cb, data_cb.replace("rps_join_", "", 1))
    elif data_cb.startswith("rps_cancel_"):
        handle_rps_cancel(data, cb, data_cb.replace("rps_cancel_", "", 1))

    elif data_cb.startswith("guess_hide_"):
        rest = data_cb.replace("guess_hide_", "", 1)
        game_id, side = rest.rsplit("_", 1)
        handle_guess_hide(data, cb, game_id, side)
    elif data_cb.startswith("guess_pick_"):
        rest = data_cb.replace("guess_pick_", "", 1)
        game_id, side = rest.rsplit("_", 1)
        handle_guess_pick(data, cb, game_id, side)
    elif data_cb.startswith("guess_join_"):
        handle_guess_join(data, cb, data_cb.replace("guess_join_", "", 1))
    elif data_cb.startswith("guess_cancel_"):
        handle_guess_cancel(data, cb, data_cb.replace("guess_cancel_", "", 1))

    elif data_cb.startswith("jail_pay_"):
        handle_jail_pay(data, cb, int(data_cb.replace("jail_pay_", "", 1)))
    elif data_cb.startswith("jail_wait_"):
        handle_jail_wait(data, cb, int(data_cb.replace("jail_wait_", "", 1)))
    elif data_cb.startswith("jail_ticket_"):
        handle_jail_ticket(data, cb, int(data_cb.replace("jail_ticket_", "", 1)))

    elif data_cb.startswith("admin_menu_"):
        handle_admin_menu_callback(data, cb, data_cb)

    else:
        answer_callback(cb_id)

    save_data(data)

# ===== wrapper های thread-safe =====
def process_message(msg):
    with data_lock:
        try:
            handle_message(msg)
        except Exception as e:
            print("handle_message error:", e)

def process_callback(cb):
    with data_lock:
        try:
            handle_callback(cb)
        except Exception as e:
            print("handle_callback error:", e)

def process_expired_games():
    with data_lock:
        try:
            check_expired_games()
        except Exception as e:
            print("check_expired_games error:", e)

# ===== حلقه اصلی (Long Polling) =====
def main():
    global last_game_check
    print("ربات طلا در حال اجراست...")
    offset = None
    while True:
        now = time.time()
        if now - last_game_check > 30:
            threading.Thread(target=process_expired_games, daemon=True).start()
            last_game_check = now

        params = {"timeout": 15}
        if offset:
            params["offset"] = offset
        try:
            resp = session.get(f"{BASE_URL}/getUpdates", params=params, timeout=20)
            updates = resp.json().get("result", [])
        except Exception as e:
            print("getUpdates error:", e)
            time.sleep(2)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            if "message" in update:
                threading.Thread(target=process_message, args=(update["message"],), daemon=True).start()
            elif "callback_query" in update:
                threading.Thread(target=process_callback, args=(update["callback_query"],), daemon=True).start()

if __name__ == "__main__":
    main()
