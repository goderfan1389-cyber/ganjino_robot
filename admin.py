import time
import random
import requests
import datetime
import json
from utils import send_message, admin_panel_keyboard
from database import get_conn, get_user, update_user
from config import BASE_URL, ADMIN_IDS, MAIN_GROUP_USERNAME

def is_admin(user_id): return user_id in ADMIN_IDS

admin_states = {}

def handle_admin_commands(msg, u, conn, reply_id=None):
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()
    user_id = u['user_id']

    if not is_admin(user_id): return False

    state = admin_states.get(user_id)
    if state:
        if text == "انصراف":
            del admin_states[user_id]
            send_message(chat_id, "❌ عملیات لغو شد.", reply_id)
            return True

        if state['step'] == 'msg':
            state['data']['msg_id'] = msg['message_id']
            state['step'] = 'num_opts'
            send_message(chat_id, "تعداد گزینه‌ها را وارد کنید (مثلا 3):")
            return True

        if state['step'] == 'num_opts':
            if not text.isdigit(): send_message(chat_id, "عدد وارد کنید."); return True
            state['data']['num_opts'] = int(text)
            state['data']['options'] = []
            state['step'] = 'opt'
            send_message(chat_id, "گزینه 1 را وارد کنید:")
            return True

        if state['step'] == 'opt':
            state['data']['options'].append(text)
            if len(state['data']['options']) < state['data']['num_opts']:
                send_message(chat_id, f"گزینه {len(state['data']['options'])+1} را وارد کنید:")
            else:
                state['step'] = 'time'
                send_message(chat_id, "تا چه ساعتی مهلت دارند؟ (فرمت 24 ساعته مثال: 19:30)")
            return True

        if state['step'] == 'time':
            try:
                h, m = map(int, text.split(':'))
                now = datetime.datetime.now()
                deadline = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if deadline < now: deadline += datetime.timedelta(days=1)
                
                cur = conn.cursor()
                cur.execute("INSERT INTO events (admin_chat_id, admin_msg_id, options, deadline, status) VALUES (%s, %s, %s, %s, 'active') RETURNING event_id", 
                            (chat_id, state['data']['msg_id'], state['data']['options'], deadline.timestamp()))
                event_id = cur.fetchone()[0]
                conn.commit()
                
                requests.post(f"{BASE_URL}/forwardMessage", data={"chat_id": f"@{MAIN_GROUP_USERNAME}", "from_chat_id": chat_id, "message_id": state['data']['msg_id']})
                
                keyboard = {"inline_keyboard": [[{"text": opt, "callback_data": f"vote_{event_id}_{i}"}] for i, opt in enumerate(state['data']['options'])]}
                send_message(f"@{MAIN_GROUP_USERNAME}", "⚽ مسابقه پیش‌بینی! انتخاب کنید:", reply_markup=keyboard)
                
                del admin_states[user_id]
                send_message(chat_id, "✅ مسابقه در گروه ایجاد شد.")
            except:
                send_message(chat_id, "فرمت ساعت اشتباه است. مثال درست: 19:30")
            return True

        if state['step'] == 'end_select':
            if not text.isdigit(): return True
            event_id = int(text)
            cur = conn.cursor()
            cur.execute("SELECT options FROM events WHERE event_id=%s AND status='active'", (event_id,))
            row = cur.fetchone()
            if not row:
                send_message(chat_id, "مسابقه پیدا نشد."); return True
            options = row[0]
            state['data']['event_id'] = event_id
            text_opt = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
            state['step'] = 'end_opt'
            send_message(chat_id, f"کدام گزینه برنده است؟\n{text_opt}\nشماره را بفرستید:")
            return True

        if state['step'] == 'end_opt':
            if not text.isdigit(): return True
            win_idx = int(text) - 1
            state['data']['win_idx'] = win_idx
            items_list = ["1. طلا کیسه", "2. طلا خزانه", "3. سپر", "4. چاقو", "5. ماسک", "6. آهنربا", "7. بلیط آزادی"]
            state['step'] = 'end_prize'
            send_message(chat_id, f"جوایز را با این فرمت بفرستید (مثال: 1=500 2=2000 3=2):\n" + "\n".join(items_list))
            return True

        if state['step'] == 'end_prize':
            prizes = {}
            try:
