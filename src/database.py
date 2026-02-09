"""Database operations for the OCR job queue."""

import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "./data/jobs.db")


class JobStatus:
    """Job status constants."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    # Ensure data directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
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


def table_exists(conn, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None


def init_db() -> None:
    """Initialize the database schema."""
    logger.info("Initializing database...")
    
    with get_db_connection() as conn:
        # Create table if it doesn't exist
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
        
        # Create index if it doesn't exist
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status
            ON jobs(status, created_at)
        """)
        
        logger.info("Database schema initialized")
        
        # Verify table exists
        if table_exists(conn, "jobs"):
            logger.info("Jobs table verified")
        else:
            logger.error("Jobs table creation failed!")
            raise RuntimeError("Failed to create jobs table")


def add_job(filename: str) -> str:
    """Add a new job to the queue."""
    init_db()  # Ensure database is initialized
    
    job_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        conn.execute(
            """INSERT INTO jobs (id, filename, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (job_id, filename, JobStatus.PENDING, datetime.now(), datetime.now())
        )
    logger.info(f"Job {job_id} added for file: {filename}")
    return job_id


def get_next_job() -> Optional[Tuple[str, str]]:
    """Get the next pending job from the queue."""
    init_db()  # Ensure database is initialized
    
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
    init_db()  # Ensure database is initialized
    
    with get_db_connection() as conn:
        # Build the update query dynamically based on what's provided
        update_fields = ["status = ?", "updated_at = ?"]
        params = [status, datetime.now()]
        
        if raw_text is not None:
            update_fields.append("raw_text = ?")
            params.append(raw_text)
        
        if corrected_text is not None:
            update_fields.append("corrected_text = ?")
            params.append(corrected_text)
        
        # Add job_id to params
        params.append(job_id)
        
        # Execute the update
        update_query = f"""
            UPDATE jobs
            SET {', '.join(update_fields)}
            WHERE id = ?
        """
        
        conn.execute(update_query, params)
    
    logger.info(f"Job {job_id} updated to status: {status}")


def get_all_jobs() -> List[Tuple]:
    """Get all jobs ordered by creation date (newest first)."""
    init_db()  # Ensure database is initialized
    
    with get_db_connection() as conn:
        cursor = conn.execute(
            """SELECT id, filename, status, raw_text, corrected_text, created_at
               FROM jobs
               ORDER BY created_at DESC"""
        )
        rows = cursor.fetchall()
        # Convert sqlite3.Row to tuple for consistency
        result = []
        for row in rows:
            result.append((
                row["id"],
                row["filename"],
                row["status"],
                row["raw_text"] if row["raw_text"] is not None else "",
                row["corrected_text"] if row["corrected_text"] is not None else "",
                row["created_at"]
            ))
        return result


def get_job_stats() -> Dict[str, int]:
    """Get job statistics by status."""
    init_db()  # Ensure database is initialized
    
    with get_db_connection() as conn:
        cursor = conn.execute(
            """SELECT status, COUNT(*) as count
               FROM jobs
               GROUP BY status"""
        )
        return {row["status"]: row["count"] for row in cursor.fetchall()}
    

def delete_all_jobs() -> None:
    """Delete all jobs from the database."""
    init_db()  # Ensure database is initialized
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM jobs")
        logger.info("All jobs deleted from database")
    except Exception as e:
        logger.error(f"Error deleting all jobs: {e}")
        raise


def delete_job_files() -> None:
    """Delete all uploaded files and generated text files."""
    try:
        # Get upload directory from environment
        upload_dir = os.getenv("UPLOAD_DIR", "./data/uploads")
        upload_path = os.path.abspath(upload_dir)
        
        # Ensure we're in the right directory
        if os.path.exists(upload_path) and os.path.isdir(upload_path):
            # Delete all files in upload directory
            for filename in os.listdir(upload_path):
                file_path = os.path.join(upload_path, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        logger.info(f"Deleted file: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to delete file {file_path}: {e}")
            
            logger.info(f"All files deleted from upload directory: {upload_path}")
        else:
            logger.warning(f"Upload directory does not exist: {upload_path}")
            # Create the directory if it doesn't exist
            os.makedirs(upload_path, exist_ok=True)
            logger.info(f"Created upload directory: {upload_path}")
            
    except Exception as e:
        logger.error(f"Error deleting files: {e}")


def clear_all_data() -> None:
    """Clear all data from database and delete all files."""
    try:
        # First ensure database is initialized
        init_db()
        
        # Then delete jobs
        delete_all_jobs()
        
        # Then delete files
        delete_job_files()
        
        logger.info("All data cleared from database and files deleted")
    except Exception as e:
        logger.error(f"Error clearing all data: {e}")
        raise


def get_connection():
    """Get a database connection (for backward compatibility)."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def reset_database() -> None:
    """Completely reset the database (drop and recreate)."""
    logger.info("Resetting database...")
    
    with get_db_connection() as conn:
        # Drop table if exists
        conn.execute("DROP TABLE IF EXISTS jobs")
        conn.execute("DROP INDEX IF EXISTS idx_jobs_status")
    
    # Reinitialize
    init_db()
    logger.info("Database completely reset")