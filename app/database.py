import sqlite3
import uuid
from datetime import datetime

DB_PATH = "/data/queue.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS jobs
            (id TEXT PRIMARY KEY, filename TEXT, status TEXT, 
             raw_text TEXT, corrected_text TEXT, created_at TIMESTAMP)''')

def add_job(filename):
    job_id = str(uuid.uuid4())
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO jobs (id, filename, status, created_at) VALUES (?, ?, ?, ?)",
                     (job_id, filename, "PENDING", datetime.now()))
    return job_id

def get_next_job():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT id, filename FROM jobs WHERE status='PENDING' ORDER BY created_at ASC LIMIT 1")
        return cursor.fetchone()

def update_job(job_id, status, raw_text=None, corrected_text=None):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE jobs SET status=?, raw_text=?, corrected_text=? WHERE id=?", 
                     (status, raw_text, corrected_text, job_id))

def get_all_jobs():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC")
        return cursor.fetchall()