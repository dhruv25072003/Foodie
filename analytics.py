# analytics.py
import sqlite3, json, os
from datetime import datetime
ANALYTICS_DB = os.getenv('ANALYTICS_DB','analytics.db')
def _connect():
    conn = sqlite3.connect(ANALYTICS_DB, check_same_thread=False); conn.row_factory = sqlite3.Row; return conn
def init_db():
    conn=_connect(); cur=conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, turn INTEGER, user_message TEXT, bot_reply TEXT, intent_json TEXT, interest_score INTEGER, recommended_products TEXT, chosen_product TEXT, created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS query_log (id INTEGER PRIMARY KEY AUTOINCREMENT, query_text TEXT, params TEXT, duration_ms REAL, created_at TEXT)''')
    conn.commit(); conn.close()
def log_turn(session_id, turn, user_message, bot_reply, score, intents, recommended=None, chosen=None):
    conn=_connect(); cur=conn.cursor(); cur.execute('INSERT INTO conversations (session_id,turn,user_message,bot_reply,intent_json,interest_score,recommended_products,chosen_product,created_at) VALUES (?,?,?,?,?,?,?,?,?)',(session_id,turn,user_message,bot_reply,json.dumps(intents),score,json.dumps(recommended or []),chosen,datetime.utcnow().isoformat())); conn.commit(); conn.close()
def log_query(query_text, params, duration_ms):
    conn=_connect(); cur=conn.cursor(); cur.execute('INSERT INTO query_log (query_text,params,duration_ms,created_at) VALUES (?,?,?,?)',(query_text,json.dumps(params),duration_ms,datetime.utcnow().isoformat())); conn.commit(); conn.close()
def fetch_recent_queries(limit=50):
    conn=_connect(); cur=conn.cursor(); cur.execute('SELECT query_text,params,duration_ms,created_at FROM query_log ORDER BY id DESC LIMIT ?', (limit,)); rows=[dict(r) for r in cur.fetchall()]; conn.close(); return rows
def fetch_conversations(limit=50):
    conn=_connect(); cur=conn.cursor(); cur.execute('SELECT * FROM conversations ORDER BY id DESC LIMIT ?', (limit,)); rows=[dict(r) for r in cur.fetchall()]; conn.close(); return rows
