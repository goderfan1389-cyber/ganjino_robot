import time
import json
import random
import psycopg2
import psycopg2.extras
from utils import send_message, edit_message, answer_callback, delete_message
from database import get_conn, release_conn, get_user, update_user
from config import (GAME_TAX_PERCENT, CASINO_TAX_PERCENT, TURN_TIMEOUT, 
                    DOOZ_WAIT_TIMEOUT, CASINO_WAIT_TIMEOUT, RPS_WAIT_TIMEOUT, GUESS_WAIT_TIMEOUT,
                    EMPTY_CELL, X_MARK, O_MARK, RPS_NAMES, RPS_BEATS)

def create_duel_game(conn, game_type, chat_id, user_id, user_name, bet, text_msg, extra_data={}):
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO games (game_type, chat_id, host_id, host_name, bet, status, data, created_at)
        VALUES (%s, %s, %s, %s, %s, 'waiting', %s, %s) RETURNING game_id
    ''', (game_type, chat_id, user_id, user_name, bet, json.dumps(extra_data), time.time()))
    game_id = cur.fetchone()[0]
    conn.commit()

    keyboard = {
        "inline_keyboard": [
            [{"text": "✅️ قبول", "callback_data": f"{game_type}_join_{game_id}"}],
            [{"text": "❌️ لغو", "callback_data": f"{game_type}_cancel_{game_id}"}],
        ]
    }
    resp = send_message(chat_id, text_msg, reply_markup=keyboard)
    msg_id = resp.json().get("result", {}).get("message_id") if resp else None
    
    cur.execute("UPDATE games SET message_id = %s WHERE game_id = %s", (msg_id, game_id))
    conn.commit()

def handle_game_callback(cb, conn, u):
    cb_id = cb["id"]
    chat_id = cb["message"]["chat"]["id"]
    user_id = cb.get("from", {}).get("id")
    data = cb.get("data", "")
    msg_id = cb["message"]["message_id"]

    parts = data.split("_")
    game_type = parts[0]
    action = parts[1]
    game_id = int(parts[2])

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM games WHERE game_id = %s", (game_id,))
    game = cur.fetchone()
    if not game:
        answer_callback(cb_id, "بازی پیدا نشد.", True); return

    if action == "join":
        if user_id == game['host_id']:
            answer_callback(cb_id, "نمی‌تونی چون خودت این بازی رو ساختی!", True); return
        if game['status'] != 'waiting':
            answer_callback(cb_id, "این بازی شروع شده یا لغو شده.", True); return

        if u['gold'] < game['bet']:
            answer_callback(cb_id, "موجودی طلای شما کافی نیست.", True); return

        update_user(user_id, {"gold": u['gold'] - game['bet']}, conn)
        
        if game_type == "dooz":
            _start_dooz(conn, cb, game, u)
        elif game_type == "casino":
            _resolve_casino(conn, cb, game, u)
        elif game_type == "rps":
            _start_rps(conn, cb, game, u)
        elif game_type == "guess":
            _start_guess(conn, cb, game, u)

    elif action == "cancel":
        if user_id != game['host_id']:
            answer_callback(cb_id, "فقط سازنده می‌تونه لغو کنه.", True); return
        host = get_user(game['host_id'], conn)
        update_user(game['host_id'], {"gold": host['gold'] + game['bet']}, conn)
        cur.execute("UPDATE games SET status = 'cancelled' WHERE game_id = %s", (game_id,))
        conn.commit()
        delete_message(chat_id, msg_id)
        answer_callback(cb_id, "بازی لغو شد و طلای شما برگشت.")

    elif action == "move":
        _handle_dooz_move(cb, conn, game, u, int(parts[3]))
    elif action == "choice":
        _handle_rps_choice(cb, conn, game, u, parts[3])
    elif action == "hide":
        _handle_guess_hide(cb, conn, game, u, parts[3])
    elif action == "pick":
        _handle_guess_pick(cb, conn, game, u, parts[3])

def _start_dooz(conn, cb, game, u):
    cb_id = cb["id"]; chat_id = cb["message"]["chat"]["id"]; msg_id = cb["message"]["message_id"]
    symbols = {str(game['host_id']): X_MARK, str(u['user_id']): O_MARK} if random.choice([True, False]) else {str(game['host_id']): O_MARK, str(u['user_id']): X_MARK}
    game_data = {"board": [EMPTY_CELL]*9, "symbols": symbols, "turn": X_MARK}
    cur = conn.cursor()
    cur.execute("UPDATE games SET status = 'active', opponent_id = %s, opponent_name = %s, data = %s, deadline = %s WHERE game_id = %s", 
                (u['user_id'], u['name'], json.dumps(game_data), time.time() + TURN_TIMEOUT, game['game_id']))
    conn.commit()
    
    starter_name = game['host_name'] if symbols[str(game['host_id'])] == X_MARK else u['name']
    text = f"❌⭕ بازی دوز شروع شد ⭕❌\n👤 {game['host_name']} ({symbols[str(game['host_id'])]})\n👤 {u['name']} ({symbols[str(u['user_id'])]})\n💰 مبلغ شرط: {game['bet']:,} طلا\n\nنوبت {starter_name} ({X_MARK}) هست"
    
    keyboard = {"inline_keyboard": [[{"text": EMPTY_CELL, "callback_data": f"dooz_move_{game['game_id']}_{row*3+col}"} for col in range(3)] for row in range(3)]}
    edit_message(chat_id, msg_id, text, reply_markup=keyboard)
    answer_callback(cb_id, "بازی شروع شد!")

def _handle_dooz_move(cb, conn, game, u, idx):
    cb_id = cb["id"]; chat_id = cb["message"]["chat"]["id"]; msg_id = cb["message"]["message_id"]
    game_data = game['data']
    if game_data['symbols'][str(u['user_id'])] != game_data['turn']:
        answer_callback(cb_id, "نوبت شما نیست!", True); return
    if game_data['board'][idx] != EMPTY_CELL:
        answer_callback(cb_id, "این خانه پر شده!", True); return

    game_data['board'][idx] = game_data['turn']
    
    win_lines = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    winner = None
    for a,b,c in win_lines:
        if game_data['board'][a] != EMPTY_CELL and game_data['board'][a] == game_data['board'][b] == game_data['board'][c]:
            winner = game_data['board'][a]; break
    if not winner and all(c != EMPTY_CELL for c in game_data['board']):
        winner = "draw"

    if winner:
        cur = conn.cursor()
        if winner == "draw":
            host = get_user(game['host_id'], conn); opp = get_user(game['opponent_id'], conn)
            update_user(game['host_id'], {"gold": host['gold'] + game['bet']}, conn)
            update_user(game['opponent_id'], {"gold": opp['gold'] + game['bet']}, conn)
            text = "🤝 بازی مساوی شد! مبلغ شرط برگشت داده شد."
        else:
            win_id = game['host_id'] if game_data['symbols'][str(game['host_id'])] == winner else game['opponent_id']
            # اصلاح محاسبات مالیات
            pot = game['bet'] * 2
            tax = round(pot * GAME_TAX_PERCENT)
            prize = pot - tax
            win_user = get_user(win_id, conn)
            update_user(win_id, {"gold": win_user['gold'] + prize}, conn)
            text = f"🏆 {win_user['name']} برنده شد!\n💰 جایزه: {prize:,} طلا (کسر مالیات ۱۰٪)"
        cur.execute("UPDATE games SET status = 'finished' WHERE game_id = %s", (game['game_id'],))
        conn.commit()
        edit_message(chat_id, msg_id, text, reply_markup={"inline_keyboard": []})
        answer_callback(cb_id, "بازی تمام شد.")
    else:
        game_data['turn'] = O_MARK if game_data['turn'] == X_MARK else X_MARK
        next_id = game['host_id'] if game_data['symbols'][str(game['host_id'])] == game_data['turn'] else game['opponent_id']
        next_name = game['host_name'] if next_id == game['host_id'] else game['opponent_name']
        
        cur = conn.cursor()
        cur.execute("UPDATE games SET data = %s, deadline = %s WHERE game_id = %s", (json.dumps(game_data), time.time() + TURN_TIMEOUT, game['game_id']))
        conn.commit()
        
        text = f"❌⭕ بازی دوز ⭕❌\n👤 {game['host_name']} ({game_data['symbols'][str(game['host_id'])]})\n👤 {game['opponent_name']} ({game_data['symbols'][str(game['opponent_id')]})\n\nنوبت {next_name} ({game_data['turn']}) هست"
        keyboard = {"inline_keyboard": [[{"text": game_data['board'][row*3+col], "callback_data": f"dooz_move_{game['game_id']}_{row*3+col}"} for col in range(3)] for row in range(3)]}
        edit_message(chat_id, msg_id, text, reply_markup=keyboard)
        answer_callback(cb_id)

def _resolve_casino(conn, cb, game, u):
    cb_id = cb["id"]; chat_id = cb["message"]["chat"]["id"]; msg_id = cb["message"]["message_id"]
    winner_is_host = random.choice([True, False])
    winner_id = game['host_id'] if winner_is_host else u['user_id']
    winner_name = game['host_name'] if winner_is_host else u['name']
    
    # اصلاح محاسبات مالیات
    pot = game['bet'] * 2
    tax = round(pot * CASINO_TAX_PERCENT)
    prize = pot - tax
    win_user = get_user(winner_id, conn)
    update_user(winner_id, {"gold": win_user['gold'] + prize}, conn)
    
    cur = conn.cursor()
    cur.execute("UPDATE games SET status = 'finished', opponent_id = %s, opponent_name = %s WHERE game_id = %s", (u['user_id'], u['name'], game['game_id']))
    conn.commit()
    
    text = f"🎰 کازینو تموم شد!\n👤 {game['host_name']}\n👤 {u['name']}\n\nبرنده: 🎖 {winner_name}\n🎁 جایزه: {prize:,} طلا (کسر مالیات ۱۰٪)"
    edit_message(chat_id, msg_id, text, reply_markup={"inline_keyboard": []})
    answer_callback(cb_id, "نتیجه مشخص شد!")

def _start_rps(conn, cb, game, u):
    cb_id = cb["id"]; chat_id = cb["message"]["chat"]["id"]; msg_id = cb["message"]["message_id"]
    game_data = {"choices": {}}
    cur = conn.cursor()
    cur.execute("UPDATE games SET status = 'active', opponent_id = %s, opponent_name = %s, data = %s, deadline = %s WHERE game_id = %s", 
                (u['user_id'], u['name'], json.dumps(game_data), time.time() + TURN_TIMEOUT, game['game_id']))
    conn.commit()
    text = f"✊ بازی سنگ‌کاغذقیچی شروع شد ✂️\n👤 {game['host_name']}\n👤 {u['name']}\n\nانتخاب کنید:"
    keyboard = {"inline_keyboard": [[
        {"text": "🪨 سنگ", "callback_data": f"rps_choice_{game['game_id']}_rock"},
        {"text": "📄 کاغذ", "callback_data": f"rps_choice_{game['game_id']}_paper"},
        {"text": "✂️ قیچی", "callback_data": f"rps_choice_{game['game_id']}_scissors"},
    ]]}
    edit_message(chat_id, msg_id, text, reply_markup=keyboard)
    answer_callback(cb_id, "بازی شروع شد!")

def _handle_rps_choice(cb, conn, game, u, choice):
    cb_id = cb["id"]; chat_id = cb["message"]["chat"]["id"]; msg_id = cb["message"]["message_id"]
    game_data = game['data']
    if str(u['user_id']) in game_data['choices']:
        answer_callback(cb_id, "قبلا انتخاب کردی!", True); return
    game_data['choices'][str(u['user_id'])] = choice
    answer_callback(cb_id, f"انتخاب ثبت شد: {RPS_NAMES[choice]}", False)

    if len(game_data['choices']) == 2:
        host_ch = game_data['choices'][str(game['host_id'])]
        opp_ch = game_data['choices'][str(game['opponent_id'])]
        if host_ch == opp_ch:
            host = get_user(game['host_id'], conn); opp = get_user(game['opponent_id'], conn)
            update_user(game['host_id'], {"gold": host['gold'] + game['bet']}, conn)
            update_user(game['opponent_id'], {"gold": opp['gold'] + game['bet']}, conn)
            text = f"🤝 مساوی شد!\n{game['host_name']}: {RPS_NAMES[host_ch]}\n{game['opponent_name']}: {RPS_NAMES[opp_ch]}"
        else:
            host_wins = RPS_BEATS[host_ch] == opp_ch
            win_id = game['host_id'] if host_wins else game['opponent_id']
            win_user = get_user(win_id, conn)
            # اصلاح محاسبات مالیات
            pot = game['bet'] * 2
            tax = round(pot * GAME_TAX_PERCENT)
            prize = pot - tax
            update_user(win_id, {"gold": win_user['gold'] + prize}, conn)
            text = f"🏆 {win_user['name']} برنده شد!\n{game['host_name']}: {RPS_NAMES[host_ch]}\n{game['opponent_name']}: {RPS_NAMES[opp_ch]}\n💰 جایزه: {prize:,} طلا (کسر مالیات ۱۰٪)"
        cur = conn.cursor()
        cur.execute("UPDATE games SET status = 'finished' WHERE game_id = %s", (game['game_id'],))
        conn.commit()
        edit_message(chat_id, msg_id, text, reply_markup={"inline_keyboard": []})
    else:
        cur = conn.cursor()
        cur.execute("UPDATE games SET data = %s WHERE game_id = %s", (json.dumps(game_data), game['game_id']))
        conn.commit()

def _start_guess(conn, cb, game, u):
    cb_id = cb["id"]; chat_id = cb["message"]["chat"]["id"]; msg_id = cb["message"]["message_id"]
    game_data = {"flower_hand": None}
    cur = conn.cursor()
    cur.execute("UPDATE games SET status = 'hiding', opponent_id = %s, opponent_name = %s, data = %s, deadline = %s WHERE game_id = %s", 
                (u['user_id'], u['name'], json.dumps(game_data), time.time() + TURN_TIMEOUT, game['game_id']))
    conn.commit()
    text = f"🌸 حریف پیدا شد!\n👤 میزبان: {game['host_name']}\n👤 حریف: {u['name']}\n\n🤲 {game['host_name']} گل رو قایم کن:"
    keyboard = {"inline_keyboard": [[
        {"text": "🤚 قایم راست", "callback_data": f"guess_hide_{game['game_id']}_right"},
        {"text": "🤚 قایم چپ", "callback_data": f"guess_hide_{game['game_id']}_left"},
    ]]}
    edit_message(chat_id, msg_id, text, reply_markup=keyboard)
    answer_callback(cb_id, "بازی شروع شد!")

def _handle_guess_hide(cb, conn, game, u, side):
    cb_id = cb["id"]; chat_id = cb["message"]["chat"]["id"]; msg_id = cb["message"]["message_id"]
    if u['user_id'] != game['host_id']:
        answer_callback(cb_id, "نوبت شما نیست!", True); return
    game_data = game['data']
    game_data['flower_hand'] = side
    cur = conn.cursor()
    cur.execute("UPDATE games SET status = 'guessing', data = %s, deadline = %s WHERE game_id = %s", (json.dumps(game_data), time.time() + TURN_TIMEOUT, game['game_id']))
    conn.commit()
    text = f"🌸 گل قایم شد! نوبت حدس زدنه.\n✋ {game['opponent_name']} حدس بزن:"
    keyboard = {"inline_keyboard": [[
        {"text": "✋ دست چپ", "callback_data": f"guess_pick_{game['game_id']}_left"},
        {"text": "✋ دست راست", "callback_data": f"guess_pick_{game['game_id']}_right"},
    ]]}
    edit_message(chat_id, msg_id, text, reply_markup=keyboard)
    answer_callback(cb_id, "قایم شد!")

def _handle_guess_pick(cb, conn, game, u, side):
    cb_id = cb["id"]; chat_id = cb["message"]["chat"]["id"]; msg_id = cb["message"]["message_id"]
    if u['user_id'] != game['opponent_id']:
        answer_callback(cb_id, "نوبت شما نیست!", True); return
    game_data = game['data']
    correct = side == game_data['flower_hand']
    win_id = game['opponent_id'] if correct else game['host_id']
    win_user = get_user(win_id, conn)
    # اصلاح محاسبات مالیات
    pot = game['bet'] * 2
    tax = round(pot * GAME_TAX_PERCENT)
    prize = pot - tax
    update_user(win_id, {"gold": win_user['gold'] + prize}, conn)
    
    cur = conn.cursor()
    cur.execute("UPDATE games SET status = 'finished' WHERE game_id = %s", (game['game_id'],))
    conn.commit()
    
    host_hand = "چپ" if game_data['flower_hand']=='left' else "راست"
    opp_hand = "چپ" if side=='left' else "راست"
    text = f"🌸 {game['host_name']} گل رو در دست {host_hand} قایم کرد!\n{game['opponent_name']} دست {opp_hand} رو انتخاب کرد.\n\n🏆 {win_user['name']} برنده شد!\n💰 جایزه: {prize:,} طلا (کسر مالیات ۱۰٪)"
    edit_message(chat_id, msg_id, text, reply_markup={"inline_keyboard": []})
    answer_callback(cb_id, "بازی تمام شد.")

def check_expired_games():
    conn = get_conn()
    if not conn: return
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        now = time.time()
        
        cur.execute("SELECT * FROM games WHERE status = 'waiting' AND created_at < %s", (now - DOOZ_WAIT_TIMEOUT,))
        for game in cur.fetchall():
            host = get_user(game['host_id'], conn)
            update_user(game['host_id'], {"gold": host['gold'] + game['bet']}, conn)
            cur2 = conn.cursor()
            cur2.execute("UPDATE games SET status = 'cancelled' WHERE game_id = %s", (game['game_id'],))
            delete_message(game['chat_id'], game['message_id'])
        conn.commit()

        cur.execute("SELECT * FROM games WHERE status IN ('active', 'hiding', 'guessing') AND deadline < %s", (now,))
        for game in cur.fetchall():
            win_id = game['opponent_id'] if game['status'] == 'active' else game['host_id']
            if win_id:
                win_user = get_user(win_id, conn)
                # اصلاح محاسبات مالیات برای تایم‌اوت
                pot = game['bet'] * 2
                tax = round(pot * GAME_TAX_PERCENT)
                prize = pot - tax
                update_user(win_id, {"gold": win_user['gold'] + prize}, conn)
                edit_message(game['chat_id'], game['message_id'], f"⏰ زمان تمام شد!\n🏆 {win_user['name']} برنده شد!\n💰 جایزه: {prize:,} طلا")
            cur2 = conn.cursor()
            cur2.execute("UPDATE games SET status = 'finished' WHERE game_id = %s", (game['game_id'],))
        conn.commit()
    except Exception as e:
        print("Game Timeout Error:", e)
    finally:
        release_conn(conn)
