import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN = os.environ.get("BOT_TOKEN", "1178057070:HPKhPZfmr8oVwDqSXIpbDFfqBroohnuHWd8")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "GANJINO_BOT")
MAIN_GROUP_USERNAME = os.environ.get("MAIN_GROUP_USERNAME", "GANJINO_GAP")
JOIN_CHANNEL_USERNAME = os.environ.get("JOIN_CHANNEL_USERNAME", "computer_program")
BACKUP_PASSWORD = os.environ.get("BACKUP_PASSWORD", "GANJINO_TEAM_IR")

ADMIN_IDS = [324157864, 890352247]
OWNER_ID = 324157864

DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=postgres user=postgres password=postgres host=localhost port=5432")
BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"

CLAIM_COOLDOWN = 4 * 60
JAIL_SECONDS = 10 * 60
JAIL_RANSOM = 150

STEAL_COOLDOWN = 30
STEAL_WARNINGS_LIMIT = 3

ITEMS = {
    "سپر": {"emoji": "🛡", "price": 100},
    "چاقو": {"emoji": "🔪", "price": 100},
    "ماسک": {"emoji": "🎭", "price": 100},
    "آهنربا": {"emoji": "🧲", "price": 100},
    "بلیط آزادی": {"emoji": "🎫", "price": 47},
}
