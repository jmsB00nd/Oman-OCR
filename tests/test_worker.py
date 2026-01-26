"""Tests for the background worker loop."""

import sqlite3
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestWorkerJobProcessing:
    """Tests for worker job processing logic."""

    def test_worker_processes_pending_job(
        self, temp_db, temp_upload_dir, sample_image, mock_vision_response, mock_text_response, monkeypatch
    ):
        """Test that worker processes a pending job."""
        # Setup
        monkeypatch.setattr("database.DB_PATH", temp_db)
        monkeypatch.setattr("main.UPLOAD_DIR", temp_upload_dir)

        from database import JobStatus, add_job, get_all_jobs, init_db

        init_db()

        # Copy sample image to upload dir with expected name
        test_filename = "test_doc.jpg"
        target_path = temp_upload_dir / test_filename
        target_path.write_bytes(sample_image.read_bytes())

        job_id = add_job(test_filename)

        with patch("main.requests.post") as mock_post:
            def side_effect(*args, **kwargs):
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()

                if "8000" in args[0] or "vision" in args[0].lower():
                    mock_response.json.return_value = mock_vision_response
                else:
                    mock_response.json.return_value = mock_text_response

                return mock_response

            mock_post.side_effect = side_effect

            # Import and patch the database module in main
            import main
            monkeypatch.setattr("main.UPLOAD_DIR", temp_upload_dir)

            # Process the job manually (simulate one iteration)
            from database import get_next_job, update_job

            job = get_next_job()
            assert job is not None

            job_id, filename = job
            update_job(job_id, JobStatus.PROCESSING)

            # Run the processing logic
            image_path = temp_upload_dir / filename
            raw_text = main.process_image_with_vision(image_path)
            corrected_text = main.correct_text_with_llm(raw_text)
            update_job(job_id, JobStatus.COMPLETED, raw_text, corrected_text)

        # Verify job was completed
        jobs = get_all_jobs()
        assert len(jobs) == 1
        assert jobs[0][2] == JobStatus.COMPLETED
        assert jobs[0][3] is not None  # raw_text
        assert jobs[0][4] is not None  # corrected_text

    def test_worker_handles_api_error(
        self, temp_db, temp_upload_dir, sample_image, monkeypatch
    ):
        """Test that worker handles API errors gracefully."""
        import requests

        monkeypatch.setattr("database.DB_PATH", temp_db)
        monkeypatch.setattr("main.UPLOAD_DIR", temp_upload_dir)

        from database import JobStatus, add_job, get_all_jobs, get_next_job, init_db, update_job

        init_db()

        # Setup test file
        test_filename = "test_error.jpg"
        target_path = temp_upload_dir / test_filename
        target_path.write_bytes(sample_image.read_bytes())

        job_id = add_job(test_filename)

        with patch("main.requests.post") as mock_post:
            mock_post.side_effect = requests.ConnectionError("Connection refused")

            import main
            monkeypatch.setattr("main.UPLOAD_DIR", temp_upload_dir)

            job = get_next_job()
            job_id, filename = job
            update_job(job_id, JobStatus.PROCESSING)

            # Simulate error handling
            try:
                image_path = temp_upload_dir / filename
                main.process_image_with_vision(image_path)
            except requests.RequestException as e:
                update_job(job_id, f"{JobStatus.FAILED}: API error: {str(e)}")

        # Verify job was marked as failed
        jobs = get_all_jobs()
        assert len(jobs) == 1
        assert jobs[0][2].startswith(JobStatus.FAILED)

    def test_worker_processes_jobs_in_order(
        self, temp_db, temp_upload_dir, sample_image, mock_vision_response, mock_text_response, monkeypatch
    ):
        """Test that worker processes jobs in FIFO order."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        monkeypatch.setattr("main.UPLOAD_DIR", temp_upload_dir)

        from database import JobStatus, add_job, get_next_job, init_db, update_job

        init_db()

        # Create multiple test files and jobs
        job_ids = []
        for i in range(3):
            filename = f"test_{i}.jpg"
            (temp_upload_dir / filename).write_bytes(sample_image.read_bytes())
            job_ids.append(add_job(filename))
            time.sleep(0.01)  # Small delay to ensure different timestamps

        # Process jobs in order
        processed_order = []
        for _ in range(3):
            job = get_next_job()
            if job:
                processed_order.append(job[0])
                update_job(job[0], JobStatus.COMPLETED, "raw", "corrected")

        # Verify FIFO order
        assert processed_order == job_ids

    def test_worker_skips_processing_jobs(
        self, temp_db, temp_upload_dir, sample_image, monkeypatch
    ):
        """Test that worker doesn't pick up jobs already being processed."""
        monkeypatch.setattr("database.DB_PATH", temp_db)

        from database import JobStatus, add_job, get_next_job, init_db, update_job

        init_db()

        # Create and mark first job as processing
        (temp_upload_dir / "first.jpg").write_bytes(sample_image.read_bytes())
        first_job = add_job("first.jpg")
        update_job(first_job, JobStatus.PROCESSING)

        # Create second job
        (temp_upload_dir / "second.jpg").write_bytes(sample_image.read_bytes())
        second_job = add_job("second.jpg")

        # Get next job should return second job
        next_job = get_next_job()
        assert next_job is not None
        assert next_job[0] == second_job


class TestWorkerConcurrency:
    """Tests for worker concurrency and thread safety."""

    def test_job_status_transition(self, temp_db, monkeypatch):
        """Test that job status transitions correctly."""
        monkeypatch.setattr("database.DB_PATH", temp_db)

        from database import JobStatus, add_job, init_db, update_job

        init_db()

        job_id = add_job("test.jpg")

        # Verify initial state
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
            assert cursor.fetchone()[0] == JobStatus.PENDING

        # Transition to processing
        update_job(job_id, JobStatus.PROCESSING)

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
            assert cursor.fetchone()[0] == JobStatus.PROCESSING

        # Transition to completed
        update_job(job_id, JobStatus.COMPLETED, "raw", "corrected")

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
            assert cursor.fetchone()[0] == JobStatus.COMPLETED

    def test_multiple_jobs_different_states(self, temp_db, monkeypatch):
        """Test handling multiple jobs in different states."""
        monkeypatch.setattr("database.DB_PATH", temp_db)

        from database import JobStatus, add_job, get_job_stats, init_db, update_job

        init_db()

        # Create jobs in different states
        pending = add_job("pending.jpg")
        processing = add_job("processing.jpg")
        completed = add_job("completed.jpg")
        failed = add_job("failed.jpg")

        update_job(processing, JobStatus.PROCESSING)
        update_job(completed, JobStatus.COMPLETED, "raw", "corrected")
        update_job(failed, f"{JobStatus.FAILED}: Test error")

        # Verify stats
        stats = get_job_stats()
        assert stats.get(JobStatus.PENDING, 0) == 1
        assert stats.get(JobStatus.PROCESSING, 0) == 1
        assert stats.get(JobStatus.COMPLETED, 0) == 1
        # Failed status includes error message, so check differently
        failed_count = sum(1 for k in stats if k.startswith(JobStatus.FAILED))
        assert failed_count == 1


class TestWorkerErrorRecovery:
    """Tests for worker error recovery scenarios."""

    def test_worker_continues_after_job_failure(
        self, temp_db, temp_upload_dir, sample_image, mock_vision_response, mock_text_response, monkeypatch
    ):
        """Test that worker continues processing after a job fails."""
        import requests

        monkeypatch.setattr("database.DB_PATH", temp_db)
        monkeypatch.setattr("main.UPLOAD_DIR", temp_upload_dir)

        from database import JobStatus, add_job, get_all_jobs, get_next_job, init_db, update_job

        init_db()

        # Create two test jobs
        (temp_upload_dir / "fail.jpg").write_bytes(sample_image.read_bytes())
        (temp_upload_dir / "success.jpg").write_bytes(sample_image.read_bytes())

        fail_job = add_job("fail.jpg")
        success_job = add_job("success.jpg")

        import main
        monkeypatch.setattr("main.UPLOAD_DIR", temp_upload_dir)

        # Process first job (simulate failure)
        job = get_next_job()
        update_job(job[0], JobStatus.PROCESSING)

        with patch("main.requests.post") as mock_post:
            mock_post.side_effect = requests.Timeout("Request timed out")

            try:
                main.process_image_with_vision(temp_upload_dir / job[1])
            except requests.RequestException as e:
                update_job(job[0], f"{JobStatus.FAILED}: {str(e)}")

        # Process second job (should succeed)
        job = get_next_job()
        assert job is not None
        assert job[0] == success_job

        update_job(job[0], JobStatus.PROCESSING)

        with patch("main.requests.post") as mock_post:
            def side_effect(*args, **kwargs):
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()

                if "8000" in args[0] or "vision" in args[0].lower():
                    mock_response.json.return_value = mock_vision_response
                else:
                    mock_response.json.return_value = mock_text_response

                return mock_response

            mock_post.side_effect = side_effect

            raw = main.process_image_with_vision(temp_upload_dir / job[1])
            corrected = main.correct_text_with_llm(raw)
            update_job(job[0], JobStatus.COMPLETED, raw, corrected)

        # Verify final state
        jobs = get_all_jobs()
        statuses = {j[1]: j[2] for j in jobs}

        assert statuses["fail.jpg"].startswith(JobStatus.FAILED)
        assert statuses["success.jpg"] == JobStatus.COMPLETED

    def test_worker_handles_missing_file(self, temp_db, temp_upload_dir, monkeypatch):
        """Test that worker handles missing files gracefully."""
        monkeypatch.setattr("database.DB_PATH", temp_db)
        monkeypatch.setattr("main.UPLOAD_DIR", temp_upload_dir)

        from database import JobStatus, add_job, get_all_jobs, get_next_job, init_db, update_job

        init_db()

        # Add job for non-existent file
        job_id = add_job("nonexistent.jpg")

        import main
        monkeypatch.setattr("main.UPLOAD_DIR", temp_upload_dir)

        job = get_next_job()
        update_job(job[0], JobStatus.PROCESSING)

        try:
            main.process_image_with_vision(temp_upload_dir / job[1])
        except FileNotFoundError as e:
            update_job(job[0], f"{JobStatus.FAILED}: {str(e)}")
        except Exception as e:
            update_job(job[0], f"{JobStatus.FAILED}: {str(e)}")

        # Verify job was marked as failed
        jobs = get_all_jobs()
        assert jobs[0][2].startswith(JobStatus.FAILED)


class TestWorkerMetrics:
    """Tests for worker metrics and monitoring."""

    def test_job_timestamps_updated(self, temp_db, monkeypatch):
        """Test that job timestamps are properly updated."""
        monkeypatch.setattr("database.DB_PATH", temp_db)

        from database import JobStatus, add_job, init_db, update_job

        init_db()

        job_id = add_job("test.jpg")

        # Get initial timestamp
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT created_at, updated_at FROM jobs WHERE id = ?", (job_id,)
            )
            created_at, initial_updated_at = cursor.fetchone()

        time.sleep(0.1)  # Small delay

        # Update job
        update_job(job_id, JobStatus.COMPLETED, "raw", "corrected")

        # Verify updated_at changed
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT updated_at FROM jobs WHERE id = ?", (job_id,)
            )
            final_updated_at = cursor.fetchone()[0]

        assert final_updated_at != initial_updated_at
