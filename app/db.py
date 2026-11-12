"""SQLite question log + editable system prompt (swap for Postgres in production)."""
import json
import sqlite3
import time
from contextlib import closing

from .config import settings, DEFAULT_SYSTEM_PROMPT


def _conn():
    c = sqlite3.connect(settings.db_path)
    c.row_factory = sqlite3.Row
    return c


def init():
    with closing(_conn()) as c, c:
        c.execute("""CREATE TABLE IF NOT EXISTS qa_log(
            id INTEGER PRIMARY KEY, ts REAL, customer_id TEXT, user_id TEXT, question TEXT, answer TEXT,
            sources TEXT, refused INTEGER, grounded INTEGER, prompt_tokens INTEGER, completion_tokens INTEGER,
            cost_usd REAL, first_token_ms INTEGER, total_ms INTEGER)""")
        c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")


def get_system_prompt() -> str:
    with closing(_conn()) as c:
        row = c.execute("SELECT value FROM settings WHERE key='system_prompt'").fetchone()
    return row["value"] if row else DEFAULT_SYSTEM_PROMPT


def set_system_prompt(text: str):
    with closing(_conn()) as c, c:
        c.execute("INSERT INTO settings VALUES('system_prompt', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (text,))


def log(**row):
    row["ts"] = time.time()
    row["sources"] = json.dumps(row.get("sources", []))
    cols = ",".join(row)
    with closing(_conn()) as c, c:
        c.execute(f"INSERT INTO qa_log({cols}) VALUES({','.join('?' * len(row))})", list(row.values()))


def recent(limit=100):
    with closing(_conn()) as c:
        rows = c.execute("SELECT * FROM qa_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = [dict(r) for r in rows]
    for r in out:
        r["sources"] = json.loads(r["sources"])
    return out
