"""
SQLite database para contactos y log de emails enviados.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path("contacts.db")


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                email      TEXT NOT NULL UNIQUE,
                company    TEXT DEFAULT '',
                active     INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_email TEXT NOT NULL,
                subject       TEXT NOT NULL,
                status        TEXT NOT NULL,
                error_msg     TEXT DEFAULT '',
                sent_at       TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.commit()


# ── Contacts ──────────────────────────────────────────────────────────────────

def add_contact(name: str, email: str, company: str = "") -> bool:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO contacts (name, email, company) VALUES (?, ?, ?)",
                (name.strip(), email.strip().lower(), company.strip()),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # email duplicado


def get_contacts(active_only: bool = True) -> list[tuple]:
    with sqlite3.connect(DB_PATH) as conn:
        q = "SELECT id, name, email, company, active, created_at FROM contacts"
        if active_only:
            q += " WHERE active = 1"
        q += " ORDER BY name"
        return conn.execute(q).fetchall()


def delete_contact(contact_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        conn.commit()


def toggle_contact(contact_id: int, active: bool):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE contacts SET active = ? WHERE id = ?",
            (1 if active else 0, contact_id),
        )
        conn.commit()


# ── Email log ─────────────────────────────────────────────────────────────────

def log_email(contact_email: str, subject: str, status: str, error_msg: str = ""):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO email_log (contact_email, subject, status, error_msg) VALUES (?, ?, ?, ?)",
            (contact_email, subject, status, error_msg),
        )
        conn.commit()


def get_email_log(limit: int = 100) -> list[tuple]:
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            """SELECT contact_email, subject, status, sent_at, error_msg
               FROM email_log ORDER BY sent_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
