"""
db.py
=====
SQLite layer for reviewer decisions. Store ONLY decisions (the posts and
AI analysis are recomputed/loaded at runtime) so the database stays small and
auditable.
"""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "decisions.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(seed=True):
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS decisions (
            post_id        TEXT PRIMARY KEY,
            status         TEXT NOT NULL,         -- approved | rejected | unsafe | edited
            final_comment  TEXT,                  -- the comment as approved/edited
            reviewer_note  TEXT,
            decided_at     TEXT NOT NULL
        )
        """
    )
    conn.commit()

    # Seed a few example reviewer decisions so the demo isn't empty on first run.
    if seed:
        existing = conn.execute("SELECT COUNT(*) c FROM decisions").fetchone()["c"]
        if existing == 0:
            seeds = [
                ("p19", "approved",
                 "Booking that first session is genuinely the hardest part — that took "
                 "courage. Mostly it's just a conversation to see if it's a fit. Hope it goes well!",
                 "Warm and specific, no claims. Good to post."),
                ("p01", "edited",
                 "The cost and waitlist barriers are so real. Hope you find support that's "
                 "actually reachable — you deserve that.",
                 "Trimmed for length; kept it human."),
                ("p09", "unsafe",
                 None,
                 "Draft diagnosed bipolar and claimed a cure — hard reject, flagged to AI workflow."),
            ]
            for pid, status, comment, note in seeds:
                conn.execute(
                    "INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?)",
                    (pid, status, comment, note, datetime.utcnow().isoformat(timespec="seconds")),
                )
            conn.commit()
    conn.close()


def save_decision(post_id, status, final_comment=None, reviewer_note=None):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?)",
        (post_id, status, final_comment, reviewer_note,
         datetime.utcnow().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def get_decisions():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM decisions").fetchall()
    conn.close()
    return {r["post_id"]: dict(r) for r in rows}


def export_decisions_json():
    return json.dumps(list(get_decisions().values()), indent=2)
