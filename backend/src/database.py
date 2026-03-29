"""Database operations for the OCR job queue."""

import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "jobs.db"))


class JobStatus:
    """Job status constants."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize the database schema."""
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                raw_text TEXT,
                corrected_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status
            ON jobs(status, created_at)
        """)
    logger.info("Database initialized successfully")


def add_job(filename: str) -> str:
    """Add a new job to the queue."""
    job_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        conn.execute(
            """INSERT INTO jobs (id, filename, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (job_id, filename, JobStatus.PENDING, datetime.now(), datetime.now())
        )
    logger.info(f"Job {job_id} added for file: {filename}")
    return job_id


def get_next_job() -> Optional[tuple[str, str]]:
    """Get the next pending job from the queue."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """SELECT id, filename FROM jobs
               WHERE status = ?
               ORDER BY created_at ASC
               LIMIT 1""",
            (JobStatus.PENDING,)
        )
        row = cursor.fetchone()
        return (row["id"], row["filename"]) if row else None


def update_job(
    job_id: str,
    status: str,
    raw_text: Optional[str] = None,
    corrected_text: Optional[str] = None
) -> None:
    """Update job status and results."""
    with get_db_connection() as conn:
        conn.execute(
            """UPDATE jobs
               SET status = ?, raw_text = ?, corrected_text = ?, updated_at = ?
               WHERE id = ?""",
            (status, raw_text, corrected_text, datetime.now(), job_id)
        )
    logger.info(f"Job {job_id} updated to status: {status}")


def get_all_jobs() -> list[tuple]:
    """Get all jobs ordered by creation date (newest first)."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """SELECT id, filename, status, raw_text, corrected_text, created_at
               FROM jobs
               ORDER BY created_at DESC"""
        )
        return cursor.fetchall()


def get_job_stats() -> dict[str, int]:
    """Get job statistics by status."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """SELECT status, COUNT(*) as count
               FROM jobs
               GROUP BY status"""
        )
        return {row["status"]: row["count"] for row in cursor.fetchall()}


def clear_db() -> None:
    """Delete all jobs from the database."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM jobs")
    logger.info("Database cleared")
