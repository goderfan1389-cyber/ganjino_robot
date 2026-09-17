import psycopg2
from psycopg2 import pool, extras
import json
from config import DATABASE_URL

try:
    db_pool = pool.SimpleConnectionPool(1, 20, DATABASE_URL)
    print("PostgreSQL connected successfully!")
except Exception as e:
    print("Error connecting to PostgreSQL:", e)
    db_pool = None

def get_conn():
    return db_pool.getconn() if db_pool else None

def release_conn(conn):
    if db_pool and conn:
        db_pool.putconn(conn)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            name TEXT,
            gold INT DEFAULT 0,
            bank INT DEFAULT 0,
            xp INT DEFAULT 0,
            last_claim FLOAT DEFAULT 0,
            last_daily FLOAT DEFAULT 0,
            jail_until FLOAT DEFAULT 0,
            last_steal FLOAT DEFAULT 0,
            steal_warnings INT DEFAULT 0,
            items JSONB DEFAULT '{}',
            seen_start BOOLEAN DEFAULT FALSE
        )
    ''')
    # اضافه کردن ستون last_daily اگه جدول قدیمی هست
    try:
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_daily FLOAT DEFAULT 0")
    except:
        pass

    cur.execute('''
        CREATE TABLE IF NOT EXISTS events (
            event_id SERIAL PRIMARY KEY,
            admin_chat_id BIGINT,
            admin_msg_id BIGINT,
            group_msg_id BIGINT,
            options TEXT[],
            deadline FLOAT,
            prize TEXT,
            winning_option TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS event_votes (
            vote_id SERIAL PRIMARY KEY,
            event_id INT,
            user_id BIGINT,
            choice TEXT,
            UNIQUE(user_id, event_id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS games (
            game_id SERIAL PRIMARY KEY,
            game_type TEXT,
            chat_id BIGINT,
            message_id BIGINT,
            host_id BIGINT,
            host_name TEXT,
            opponent_id BIGINT,
            opponent_name TEXT,
            bet INT,
            status TEXT DEFAULT 'waiting',
            data JSONB DEFAULT '{}',
            created_at FLOAT,
            deadline FLOAT
        )
    ''')
    conn.commit()
    release_conn(conn)

def get_user(user_id, conn=None):
    local = conn is None
    if local: conn = get_conn()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    u = cur.fetchone()
    if not u:
        cur.execute("INSERT INTO users (user_id, name) VALUES (%s, %s) RETURNING *", (user_id, "کاربر"))
        conn.commit()
        u = cur.fetchone()
    if not isinstance(u['items'], dict):
        u['items'] = json.loads(u['items']) if u['items'] else {}
    if local: release_conn(conn)
    return u

def update_user(user_id, fields, conn=None):
    local = conn is None
    if local: conn = get_conn()
    cur = conn.cursor()
    set_clauses = []
    values = []
    for k, v in fields.items():
        if isinstance(v, (dict, list)):
            v = extras.Json(v)
        set_clauses.append(f"{k} = %s")
        values.append(v)
    values.append(user_id)
    cur.execute(f"UPDATE users SET {', '.join(set_clauses)} WHERE user_id = %s", tuple(values))
    conn.commit()
    if local: release_conn(conn)
