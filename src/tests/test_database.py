"""Tests for database operations."""

import sqlite3
import sys
from pathlib import Path

import pytest

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database import (
    DB_PATH,
    JobStatus,
    add_job,
    get_all_jobs,
    get_db_connection,
    get_job_stats,
    get_next_job,
    init_db,
    update_job,
)


class TestJobStatus:
    """Tests for JobStatus constants."""

    def test_status_values(self):
        """Verify job status constants."""
        assert JobStatus.PENDING == "PENDING"
        assert JobStatus.PROCESSING == "PROCESSING"
        assert JobStatus.COMPLETED == "COMPLETED"
        assert JobStatus.FAILED == "FAILED"


class TestInitDb:
    """Tests for database initialization."""

    def test_init_db_creates_tables(self, temp_db, monkeypatch):
        """Test that init_db creates the jobs table."""
        monkeypatch.setattr("database.DB_PATH", temp_db)

        init_db()

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
            )
            assert cursor.fetchone() is not None

    def test_init_db_creates_index(self, temp_db, monkeypatch):
        """Test that init_db creates the status index."""
        monkeypatch.setattr("database.DB_PATH", temp_db)

        init_db()

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_jobs_status'"
            )
            assert cursor.fetchone() is not None

    def test_init_db_idempotent(self, temp_db, monkeypatch):
        """Test that init_db can be called multiple times safely."""
        monkeypatch.setattr("database.DB_PATH", temp_db)

        init_db()
        init_db()  # Should not raise an error

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='jobs'")
            assert cursor.fetchone()[0] == 1


class TestAddJob:
    """Tests for adding jobs."""

    def test_add_job_returns_uuid(self, temp_db, monkeypatch):
        """Test that add_job returns a valid UUID."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        job_id = add_job("test.jpg")

        assert job_id is not None
        assert len(job_id) == 36  # UUID format

    def test_add_job_creates_pending_entry(self, temp_db, monkeypatch):
        """Test that add_job creates a PENDING job entry."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        job_id = add_job("test.jpg")

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT filename, status FROM jobs WHERE id = ?", (job_id,)
            )
            row = cursor.fetchone()
            assert row[0] == "test.jpg"
            assert row[1] == JobStatus.PENDING

    def test_add_multiple_jobs(self, temp_db, monkeypatch):
        """Test adding multiple jobs."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        job_ids = [add_job(f"test{i}.jpg") for i in range(5)]

        assert len(set(job_ids)) == 5  # All unique IDs

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM jobs")
            assert cursor.fetchone()[0] == 5


class TestGetNextJob:
    """Tests for retrieving the next pending job."""

    def test_get_next_job_returns_oldest_pending(self, temp_db, monkeypatch):
        """Test that get_next_job returns the oldest pending job."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        first_job = add_job("first.jpg")
        add_job("second.jpg")
        add_job("third.jpg")

        result = get_next_job()

        assert result is not None
        assert result[0] == first_job
        assert result[1] == "first.jpg"

    def test_get_next_job_returns_none_when_empty(self, temp_db, monkeypatch):
        """Test that get_next_job returns None when no pending jobs."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        result = get_next_job()

        assert result is None

    def test_get_next_job_skips_processing_jobs(self, temp_db, monkeypatch):
        """Test that get_next_job skips jobs that are already processing."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        first_job = add_job("first.jpg")
        second_job = add_job("second.jpg")

        update_job(first_job, JobStatus.PROCESSING)

        result = get_next_job()

        assert result is not None
        assert result[0] == second_job

    def test_get_next_job_skips_completed_jobs(self, temp_db, monkeypatch):
        """Test that get_next_job skips completed jobs."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        first_job = add_job("first.jpg")
        second_job = add_job("second.jpg")

        update_job(first_job, JobStatus.COMPLETED, "raw", "corrected")

        result = get_next_job()

        assert result is not None
        assert result[0] == second_job


class TestUpdateJob:
    """Tests for updating job status."""

    def test_update_job_status(self, temp_db, monkeypatch):
        """Test updating job status."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        job_id = add_job("test.jpg")
        update_job(job_id, JobStatus.PROCESSING)

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
            assert cursor.fetchone()[0] == JobStatus.PROCESSING

    def test_update_job_with_text(self, temp_db, monkeypatch):
        """Test updating job with raw and corrected text."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        job_id = add_job("test.jpg")
        raw_text = "السلام علیکم"
        corrected_text = "السلام عليكم"

        update_job(job_id, JobStatus.COMPLETED, raw_text, corrected_text)

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT status, raw_text, corrected_text FROM jobs WHERE id = ?",
                (job_id,)
            )
            row = cursor.fetchone()
            assert row[0] == JobStatus.COMPLETED
            assert row[1] == raw_text
            assert row[2] == corrected_text

    def test_update_job_failed_status(self, temp_db, monkeypatch):
        """Test updating job with failed status and error message."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        job_id = add_job("test.jpg")
        error_status = f"{JobStatus.FAILED}: Connection timeout"

        update_job(job_id, error_status)

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
            assert cursor.fetchone()[0] == error_status


class TestGetAllJobs:
    """Tests for retrieving all jobs."""

    def test_get_all_jobs_empty(self, temp_db, monkeypatch):
        """Test get_all_jobs with empty database."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        result = get_all_jobs()

        assert result == []

    def test_get_all_jobs_returns_all(self, temp_db, monkeypatch):
        """Test get_all_jobs returns all jobs."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        for i in range(5):
            add_job(f"test{i}.jpg")

        result = get_all_jobs()

        assert len(result) == 5

    def test_get_all_jobs_ordered_by_date_desc(self, temp_db, monkeypatch):
        """Test that get_all_jobs returns jobs in descending date order."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        add_job("first.jpg")
        add_job("second.jpg")
        add_job("third.jpg")

        result = get_all_jobs()

        # Most recent should be first
        assert result[0][1] == "third.jpg"
        assert result[2][1] == "first.jpg"


class TestGetJobStats:
    """Tests for job statistics."""

    def test_get_job_stats_empty(self, temp_db, monkeypatch):
        """Test get_job_stats with empty database."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        result = get_job_stats()

        assert result == {}

    def test_get_job_stats_counts_by_status(self, temp_db, monkeypatch):
        """Test that get_job_stats correctly counts jobs by status."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        # Add jobs with different statuses
        pending_jobs = [add_job(f"pending{i}.jpg") for i in range(3)]
        processing_job = add_job("processing.jpg")
        completed_jobs = [add_job(f"completed{i}.jpg") for i in range(2)]

        update_job(processing_job, JobStatus.PROCESSING)
        for job_id in completed_jobs:
            update_job(job_id, JobStatus.COMPLETED, "raw", "corrected")

        result = get_job_stats()

        assert result[JobStatus.PENDING] == 3
        assert result[JobStatus.PROCESSING] == 1
        assert result[JobStatus.COMPLETED] == 2


class TestDbConnection:
    """Tests for database connection context manager."""

    def test_connection_commits_on_success(self, temp_db, monkeypatch):
        """Test that connection commits changes on success."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO jobs (id, filename, status) VALUES (?, ?, ?)",
                ("test-id", "test.jpg", "PENDING")
            )

        # Verify data was committed
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM jobs")
            assert cursor.fetchone()[0] == 1

    def test_connection_rollbacks_on_error(self, temp_db, monkeypatch):
        """Test that connection rolls back on error."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        init_db()

        try:
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO jobs (id, filename, status) VALUES (?, ?, ?)",
                    ("test-id", "test.jpg", "PENDING")
                )
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # Verify data was rolled back
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM jobs")
            assert cursor.fetchone()[0] == 0
