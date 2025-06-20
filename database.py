# database.py

import sqlite3

def init_db():
    conn = sqlite3.connect('requests.db')
    c = conn.cursor()

    # Таблица запросов
    c.execute('''CREATE TABLE IF NOT EXISTS requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  user_name TEXT,
                  ok_choice TEXT,
                  radio_choice TEXT,
                  chat_type TEXT,
                  comment TEXT,
                  response_text TEXT,
                  responder_name TEXT)''')

    # Таблица авторизованных пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS authorized_users
                 (user_id INTEGER PRIMARY KEY)''')

    conn.commit()
    conn.close()


def add_authorized_user(user_id):
    conn = sqlite3.connect('requests.db')
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO authorized_users (user_id) VALUES (?)", (user_id,))
        conn.commit()
    finally:
        conn.close()


def remove_authorized_user(user_id):
    conn = sqlite3.connect('requests.db')
    c = conn.cursor()
    c.execute("DELETE FROM authorized_users WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def get_all_authorized_users():
    conn = sqlite3.connect('requests.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM authorized_users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users


def is_user_authorized(user_id):
    return user_id in get_all_authorized_users() or user_id in config.USER_ADMINS


def add_request(user_id, user_name, ok_choice, radio_choice, chat_type, comment):
    conn = sqlite3.connect('requests.db')
    c = conn.cursor()
    c.execute("""INSERT INTO requests 
                (user_id, user_name, ok_choice, radio_choice, chat_type, comment) 
                VALUES (?, ?, ?, ?, ?, ?)""",
              (user_id, user_name, ok_choice, radio_choice, chat_type, comment))
    req_id = c.lastrowid
    conn.commit()
    conn.close()
    return req_id


def update_response(req_id, response_text, responder_name):
    conn = sqlite3.connect('requests.db')
    c = conn.cursor()
    c.execute("UPDATE requests SET response_text=?, responder_name=? WHERE id=?", 
              (response_text, responder_name, req_id))
    conn.commit()
    conn.close()


def get_request_by_id(req_id):
    conn = sqlite3.connect('requests.db')
    c = conn.cursor()
    c.execute("SELECT * FROM requests WHERE id=?", (req_id,))
    req = c.fetchone()
    conn.close()
    return req