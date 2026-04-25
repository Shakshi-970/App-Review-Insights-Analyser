import sqlite3
import json
from datetime import datetime
from typing import Optional, List
from .models import RunRecord

class RunLog:
    def __init__(self, db_path: str = "run_log.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    product TEXT,
                    iso_week TEXT,
                    status TEXT,
                    doc_id TEXT,
                    heading_id TEXT,
                    email_message_id TEXT,
                    review_count INTEGER DEFAULT 0,
                    token_usage INTEGER DEFAULT 0,
                    started_at TEXT,
                    completed_at TEXT
                )
            """)
            conn.commit()

    def create_run(self, run: RunRecord):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO runs (run_id, product, iso_week, status, review_count, token_usage, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (run.run_id, run.product, run.iso_week, run.status, run.review_count, run.token_usage, run.started_at.isoformat()))
            conn.commit()

    def update_run(self, run: RunRecord):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE runs SET 
                    status = ?, 
                    doc_id = ?, 
                    heading_id = ?, 
                    email_message_id = ?, 
                    review_count = ?, 
                    token_usage = ?, 
                    completed_at = ?
                WHERE run_id = ?
            """, (
                run.status, 
                run.doc_id, 
                run.heading_id, 
                run.email_message_id, 
                run.review_count, 
                run.token_usage, 
                run.completed_at.isoformat() if run.completed_at else None,
                run.run_id
            ))
            conn.commit()

    def get_run(self, product: str, iso_week: str) -> Optional[RunRecord]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM runs WHERE product = ? AND iso_week = ?", (product, iso_week))
            row = cur.fetchone()
            if row:
                return RunRecord(
                    run_id=row['run_id'],
                    product=row['product'],
                    iso_week=row['iso_week'],
                    status=row['status'],
                    doc_id=row['doc_id'],
                    heading_id=row['heading_id'],
                    email_message_id=row['email_message_id'],
                    review_count=row['review_count'] if row['review_count'] is not None else 0,
                    token_usage=row['token_usage'] if row['token_usage'] is not None else 0,
                    started_at=datetime.fromisoformat(row['started_at']),
                    completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None
                )
        return None

    def exists(self, product: str, iso_week: str) -> bool:
        run = self.get_run(product, iso_week)
        return run is not None and run.status == "success"
