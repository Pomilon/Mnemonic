import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

class SessionManager:
    def __init__(self, db_path: str = "data/sessions.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP,
                    last_updated TIMESTAMP,
                    metadata TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS turns (
                    turn_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT, -- 'user' or 'assistant'
                    content TEXT,
                    context_json TEXT,
                    timestamp TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                )
            ''')
            conn.commit()

    def create_session(self, metadata: Dict[str, Any] = {}) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, created_at, last_updated, metadata) VALUES (?, ?, ?, ?)",
                (session_id, now, now, json.dumps(metadata))
            )
            conn.commit()
        return session_id

    def add_turn(self, session_id: str, role: str, content: str, context: Optional[Dict[str, Any]] = None):
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO turns (session_id, role, content, context_json, timestamp) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, json.dumps(context) if context else None, now)
            )
            conn.execute(
                "UPDATE sessions SET last_updated = ? WHERE session_id = ?",
                (now, session_id)
            )
            conn.commit()

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT role, content, context_json, timestamp FROM turns WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,)
            )
            rows = cursor.fetchall()
            return [
                {
                    "role": row["role"],
                    "content": row["content"],
                    "context": json.loads(row["context_json"]) if row["context_json"] else None,
                    "timestamp": row["timestamp"]
                }
                for row in rows
            ]

    def delete_session(self, session_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
            conn.commit()
