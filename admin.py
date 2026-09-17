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
                for p in text.split():
                    k, v = p.split('=')
                    prizes[k] = int(v)
            except:
                send_message(chat_id, "فرمت اشتباه. مثال: 1=500 2=2000 3=2")
                return True
                
            event_id = state['data']['event_id']
            win_idx = state['data']['win_idx']
            
            cur = conn.cursor()
            cur.execute("SELECT options FROM events WHERE event_id=%s", (event_id,))
            options = cur.fetchone()[0]
            win_option = options[win_idx]
            
            cur.execute("SELECT user_id FROM event_votes WHERE event_id=%s AND choice=%s", (event_id, win_option))
            winners = cur.fetchall()
            
            for (wid,) in winners:
                w_user = get_user(wid, conn)
                items = w_user['items']
                if '1' in prizes: w_user['gold'] += prizes['1']
                if '2' in prizes: w_user['bank'] += prizes['2']
                if '3' in prizes: items['سپر'] = items.get('سپر', 0) + prizes['3']
                if '4' in prizes: items['چاقو'] = items.get('چاقو', 0) + prizes['4']
                if '5' in prizes: items['ماسک'] = items.get('ماسک', 0) + prizes['5']
                if '6' in prizes: items['آهنربا'] = items.get('آهنربا', 0) + prizes['6']
                if '7' in prizes: items['بلیط آزادی'] = items.get('بلیط آزادی', 0) + prizes['7']
                update_user(wid, {"gold": w_user['gold'], "bank": w_user['bank'], "items": items}, conn)
                
            cur.execute("UPDATE events SET status='finished', winning_option=%s WHERE event_id=%s", (win_option, event_id))
            conn.commit()
            
            send_message(f"@{MAIN_GROUP_USERNAME}", f"🏁 مسابقه تمام شد!\nگزینه برنده: {win_option}\nجوایز به برندگان داده شد (نام‌ها فاش نمیشه).")
            del admin_states[user_id]
            send_message(chat_id, "✅ جوایز با موفقیت توزیع شد.")
            return True

    # --- دستورات عادی ادمین ---
    if text == "/admin" or text == "پنل":
        send_message(chat_id, "🛠 پنل مدیریت ربات طلا\nیکی از گزینه‌ها رو انتخاب کن:", reply_markup=admin_panel_keyboard())
        return True

    if text.startswith("خزانه "):
        try:
            parts = text.split()
            target_id, amount = int(parts[1]), int(parts[2])
            update_user(target_id, {"bank": get_user(target_id, conn)['bank'] + amount}, conn)
            send_message(chat_id, f"✅ {amount} طلا به خزانه کاربر {target_id} اضافه شد.")
        except:
            send_message(chat_id, "فرمت: خزانه [آیدی] [مقدار]")
        return True

    if text == "بکاپ":
        import os
        cur = conn.cursor()
        cur.execute("SELECT * FROM users")
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        sql_lines = ["-- Bot PostgreSQL Backup", "TRUNCATE TABLE users RESTART IDENTITY CASCADE;"]
        for row in rows:
            values = []
            for val in row:
                if isinstance(val, dict): val = json.dumps(val)
                if val is None: values.append("NULL")
                elif isinstance(val, (int, float)): values.append(str(val))
                else: values.append(f"'{str(val).replace(chr(39), chr(39)+chr(39))}'")
            sql_lines.append(f"INSERT INTO users ({', '.join(colnames)}) VALUES ({', '.join(values)});")
        with open("backup.sql", "w", encoding="utf-8") as f:
            f.write("\n".join(sql_lines))
        from utils import send_document
        send_document(chat_id, "backup.sql", "📥 فایل بکاپ دیتابیس (SQL)")
        if os.path.exists("backup.sql"): os.remove("backup.sql")
        return True

    return False
