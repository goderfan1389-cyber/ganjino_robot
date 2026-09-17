import time
import random
import requests
import datetime
import json
import os
from utils import send_message, answer_callback, delete_message, copy_message, admin_panel_keyboard
from database import get_conn, get_user, update_user
from config import BASE_URL, ADMIN_IDS, MAIN_GROUP_USERNAME, BACKUP_PASSWORD

def is_admin(user_id): return user_id in ADMIN_IDS

admin_states = {}

def handle_admin_callback(cb, conn, u):
    cb_id = cb["id"]
    chat_id = cb["message"]["chat"]["id"]
    user_id = cb.get("from", {}).get("id")
    data = cb.get("data", "")
    
    if not is_admin(user_id):
        answer_callback(cb_id, "⛔ دسترسی ندارید.", True)
        return

    if data == "admin_stats":
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        cur.execute("SELECT SUM(gold), SUM(bank) FROM users")
        sums = cur.fetchone()
        send_message(chat_id, f"📊 آمار ربات:\n\n👥 تعداد کاربران: {total_users}\n🪙 مجموع کیسه طلا: {sums[0] or 0:,}\n🏦 مجموع خزانه: {sums[1] or 0:,}")

    elif data == "admin_top_users":
        cur = conn.cursor()
        cur.execute("SELECT name, bank FROM users ORDER BY bank DESC LIMIT 10")
        top = cur.fetchall()
        text = "🏆 برترین کاربران (بر اساس خزانه):\n\n"
        for i, row in enumerate(top, 1):
            text += f"{i}. {row[0]} — {row[1]:,} طلا\n"
        send_message(chat_id, text)

    elif data == "admin_backup":
        admin_states[user_id] = {'step': 'backup_password'}
        send_message(chat_id, "🔐 رمز عبور رو برای دریافت فایل بکاپ بفرست.")

    elif data == "admin_bc_group":
        admin_states[user_id] = {'step': 'bc_wait_msg', 'data': {}}
        send_message(chat_id, "📤 پیام خود را بفرستید. (عکس، متن، ویدیو و...)\nبرای لغو: انصراف")

    elif data == "admin_bc_confirm":
        if user_id in admin_states and admin_states[user_id].get('step') == 'bc_confirm':
            msg_id = admin_states[user_id]['data']['msg_id']
            copy_message(f"@{MAIN_GROUP_USERNAME}", chat_id, msg_id)
            send_message(chat_id, "✅ پیام با موفقیت در گروه ارسال شد.")
            del admin_states[user_id]

    elif data == "admin_bc_cancel":
        if user_id in admin_states: del admin_states[user_id]
        send_message(chat_id, "❌ ارسال لغو شد.")

    elif data == "admin_event":
        admin_states[user_id] = {'step': 'ev_wait_msg', 'data': {}}
        send_message(chat_id, "📸 عکس/فیلم/متن مسابقه را بفرستید (عکس همراه با کپشن هم قابل قبوله):")

    elif data == "admin_ev_confirm":
        if user_id in admin_states and admin_states[user_id].get('step') == 'ev_confirm':
            admin_states[user_id]['step'] = 'num_opts'
            send_message(chat_id, "تعداد گزینه‌ها را وارد کنید (مثلا 3):")

    elif data == "admin_ev_cancel":
        if user_id in admin_states: del admin_states[user_id]
        send_message(chat_id, "❌ ساخت مسابقه لغو شد.")

    elif data == "admin_end_event":
        cur = conn.cursor()
        cur.execute("SELECT event_id, options FROM events WHERE status='active'")
        events = cur.fetchall()
        if not events:
            answer_callback(cb_id, "مسابقه فعالی وجود ندارد.", True)
            return
        txt = "مسابقات فعال:\n" + "\n".join([f"آیدی {e[0]}: {e[1]}" for e in events])
        send_message(chat_id, txt + "\nآیدی مسابقه مورد نظر را بفرستید:")
        admin_states[user_id] = {'step': 'end_select', 'data': {}}

    else:
        prompts = {
            "admin_add_balance": ("add_balance", "آیدی عددی کاربر و مقدار طلا رو با فاصله بفرست.\nمثال: 324157864 500"),
            "admin_remove_balance": ("remove_balance", "آیدی عددی کاربر و مقدار طلا رو با فاصله بفرست.\nمثال: 324157864 500"),
            "admin_add_bank": ("add_bank", "آیدی عددی کاربر و مقدار طلا برای خزانه رو بفرست.\nمثال: 324157864 500"),
            "admin_remove_bank": ("remove_bank", "آیدی عددی کاربر و مقدار طلا برای کسر از خزانه رو بفرست.\nمثال: 324157864 500"),
            "admin_user_info": ("user_info", "آیدی عددی کاربر رو بفرست تا اطلاعاتش رو ببینی.\nمثال: 324157864"),
            "admin_free_jail": ("free_jail", "آیدی عددی کاربری که می‌خوای از زندان آزادش کنی رو بفرست.\nمثال: 324157864")
        }
        if data in prompts:
            action, prompt_text = prompts[data]
            admin_states[user_id] = {'step': action}
            send_message(chat_id, prompt_text + "\n\n(برای لغو: انصراف)")


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

        if state['step'] == 'backup_password':
            if text != BACKUP_PASSWORD:
                send_message(chat_id, "❌ رمز عبور اشتباهه.", reply_id)
                del admin_states[user_id]
                return True
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
            del admin_states[user_id]
            return True

        # --- پیام همگانی ---
        if state['step'] == 'bc_wait_msg':
            state['data']['msg_id'] = msg['message_id']
            state['step'] = 'bc_confirm'
            kb = {"inline_keyboard": [[{"text": "✅ تایید و ارسال", "callback_data": "admin_bc_confirm"}], [{"text": "❌ لغو", "callback_data": "admin_bc_cancel"}]]}
            send_message(chat_id, "آیا از ارسال این پیام مطمئن هستید؟", reply_markup=kb)
            return True

        # --- مراحل قرعه کشی مسابقه ---
        if state['step'] == 'ev_wait_msg':
            state['data']['msg_id'] = msg['message_id']
            state['step'] = 'ev_confirm'
            kb = {"inline_keyboard": [[{"text": "✅ تایید و ادامه", "callback_data": "admin_ev_confirm"}], [{"text": "❌ لغو", "callback_data": "admin_ev_cancel"}]]}
            send_message(chat_id, "پیام ثبت شد. ادامه میدهیم؟", reply_markup=kb)
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
                # تنظیم زمان بر اساس ساعت ایران (UTC+3:30)
                now = datetime.datetime.utcnow() + datetime.timedelta(minutes=210)
                deadline = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if deadline < now: deadline += datetime.timedelta(days=1)
                
                cur = conn.cursor()
                # کپی پیام به گروه و گرفتن آیدی پیام گروه
                resp = copy_message(f"@{MAIN_GROUP_USERNAME}", chat_id, state['data']['msg_id'])
                group_msg_id = resp.json().get("result", {}).get("message_id")
                
                cur.execute("INSERT INTO events (admin_chat_id, admin_msg_id, group_msg_id, options, deadline, status) VALUES (%s, %s, %s, %s, %s, 'active') RETURNING event_id", 
                            (chat_id, state['data']['msg_id'], group_msg_id, state['data']['options'], deadline.timestamp()))
                event_id = cur.fetchone()[0]
                conn.commit()
                
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
            cur.execute("SELECT options, group_msg_id FROM events WHERE event_id=%s", (event_id,))
            row = cur.fetchone()
            options = row[0]
            group_msg_id = row[1]
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
            
            # پاک کردن پیام مسابقه از گروه
            if group_msg_id:
                delete_message(f"@{MAIN_GROUP_USERNAME}", group_msg_id)
            
            send_message(f"@{MAIN_GROUP_USERNAME}", f"🏁 مسابقه تمام شد!\nگزینه برنده: {win_option}\nجوایز به برندگان داده شد (نام‌ها فاش نمیشه).")
            del admin_states[user_id]
            send_message(chat_id, "✅ جوایز با موفقیت توزیع شد و پیام مسابقه پاک شد.")
            return True

        # --- مراحل پنل ادمین ---
        if state['step'] in ["add_balance", "remove_balance", "add_bank", "remove_bank"]:
            parts = text.split()
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                send_message(chat_id, "❌ فرمت اشتباه است. مثال: 324157864 500", reply_id)
                return True
            target_id, amount = int(parts[0]), int(parts[1])
            target = get_user(target_id, conn)
            if state['step'] == "add_balance":
                target['gold'] += amount; msg = f"✅ مبلغ {amount} طلا به کیسه {target['name']} اضافه شد."
            elif state['step'] == "remove_balance":
                target['gold'] = max(0, target['gold'] - amount); msg = f"✅ مبلغ {amount} طلا از کیسه {target['name']} کم شد."
            elif state['step'] == "add_bank":
                target['bank'] += amount; msg = f"✅ مبلغ {amount} طلا به خزانه {target['name']} اضافه شد."
            elif state['step'] == "remove_bank":
                target['bank'] = max(0, target['bank'] - amount); msg = f"✅ مبلغ {amount} طلا از خزانه {target['name']} کم شد."
            update_user(target_id, {"gold": target['gold'], "bank": target['bank']}, conn)
            send_message(chat_id, msg, reply_id)
            del admin_states[user_id]
            return True

        if state['step'] == "user_info":
            if not text.isdigit(): send_message(chat_id, "❌ لطفا فقط آیدی عددی بفرست.", reply_id); return True
            target_id = int(text)
            target = get_user(target_id, conn)
            send_message(chat_id, f"🔍 اطلاعات کاربر:\n\n👤 نام: {target['name']}\n🆔 آیدی: {target_id}\n🪙 کیسه: {target['gold']:,}\n🏦 خزانه: {target['bank']:,}\n🚔 وضعیت: {'🔒 زندان' if target['jail_until'] > time.time() else '🔓 آزاد'}", reply_id)
            del admin_states[user_id]
            return True

        if state['step'] == "free_jail":
            if not text.isdigit(): send_message(chat_id, "❌ لطفا فقط آیدی عددی بفرست.", reply_id); return True
            target_id = int(text)
            update_user(target_id, {"jail_until": 0}, conn)
            send_message(chat_id, f"✅ کاربر {target_id} از زندان آزاد شد.", reply_id)
            del admin_states[user_id]
            return True

    if text == "/admin" or text == "پنل":
        send_message(chat_id, "🛠 پنل مدیریت ربات طلا\nیکی از گزینه‌ها رو انتخاب کن:", reply_markup=admin_panel_keyboard())
        return True

    return False
