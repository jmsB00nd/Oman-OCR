"""Arabic OCR Application - Main entry point."""

import base64
import logging
import os
import threading
import time
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

from database import (
    JobStatus,
    add_job,
    get_all_jobs,
    get_job_stats,
    get_next_job,
    init_db,
    update_job,
)

# Configuration
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

VISION_URL = os.getenv("VISION_URL", "http://localhost:8000/v1/chat/completions")
TEXT_URL = os.getenv("TEXT_URL", "http://localhost:8001/v1/chat/completions")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))
WORKER_POLL_INTERVAL = 2  # seconds

# Ensure upload directory exists
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Initialize database
init_db()


def process_image_with_vision(image_path: Path) -> str:
    """Send image to vision model for OCR extraction."""
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    response = requests.post(
        VISION_URL,
        json={
            "model": "/models/vision",
            "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_b64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": "Free OCR."
                            }
                        ]
                    }
                    ],
                    "max_tokens": 1024,
        "temperature": 0.0,
        "extra_body": {
            "skip_special_tokens": False,
            # args used to control custom logits processor
            "vllm_xargs": {
                "ngram_size": 30,
                "window_size": 90,
                # whitelist: <td>, </td>
                "whitelist_token_ids": [128821, 128822],
            },
        },
        },
        timeout=120
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def correct_text_with_llm(raw_text: str) -> str:
    """Send text to LLM for OCR error correction."""
    response = requests.post(
        TEXT_URL,
        json={
            "model": "/models/text",
            "messages": [{
                "role": "user",
                "content": f"Fix any OCR errors in this Arabic text and return only the corrected text: {raw_text}"
            }]
        },
        timeout=60
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def worker_loop() -> None:
    """Background worker that processes pending OCR jobs."""
    logger.info("Worker started")
    while True:
        job = get_next_job()
        if not job:
            time.sleep(WORKER_POLL_INTERVAL)
            continue

        job_id, filename = job
        logger.info(f"Processing job {job_id}: {filename}")
        update_job(job_id, JobStatus.PROCESSING)

        try:
            image_path = UPLOAD_DIR / filename

            # Step 1: Extract text from image
            raw_text = process_image_with_vision(image_path)
            logger.info(f"Job {job_id}: Vision extraction complete")

            # Step 2: Correct OCR errors
            corrected_text = correct_text_with_llm(raw_text)
            logger.info(f"Job {job_id}: Text correction complete")

            # Step 3: Write the .md file
            md_path = image_path.with_suffix(".md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(corrected_text)
            logger.info(f"Job {job_id}: Markdown file written to {md_path}")



            update_job(job_id, JobStatus.COMPLETED, raw_text, corrected_text)
            logger.info(f"Job {job_id}: Completed successfully")

        except requests.RequestException as e:
            error_msg = f"API error: {str(e)}"
            logger.error(f"Job {job_id}: {error_msg}")
            update_job(job_id, f"{JobStatus.FAILED}: {error_msg}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Job {job_id}: {error_msg}")
            update_job(job_id, f"{JobStatus.FAILED}: {error_msg}")


def start_worker() -> None:
    """Start the background worker thread."""
    if "worker_started" not in st.session_state:
        thread = threading.Thread(target=worker_loop, daemon=True)
        thread.start()
        st.session_state.worker_started = True
        logger.info("Background worker thread started")


def render_upload_tab() -> None:
    """Render the batch upload tab."""
    st.header("Upload Documents")
    st.markdown("Upload images containing Arabic text for OCR processing.")

    files = st.file_uploader(
        "Drag and drop images here",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg", "tiff", "bmp"]
    )

    if st.button("Start Processing", type="primary", disabled=not files):
        queued_count = 0
        for file in files:
            file_path = UPLOAD_DIR / file.name
            with open(file_path, "wb") as f:
                f.write(file.read())
            add_job(file.name)
            queued_count += 1

        st.success(f"Queued {queued_count} file(s) for processing.")
        st.rerun()


def render_results_tab() -> None:
    """Render the results and history tab."""
    st.header("Processing History")

    # Display statistics
    stats = get_job_stats()
    if stats:
        cols = st.columns(4)
        cols[0].metric("Pending", stats.get(JobStatus.PENDING, 0))
        cols[1].metric("Processing", stats.get(JobStatus.PROCESSING, 0))
        cols[2].metric("Completed", stats.get(JobStatus.COMPLETED, 0))
        cols[3].metric("Failed", len([k for k in stats if k.startswith(JobStatus.FAILED)]))

    # Refresh button
    if st.button("Refresh"):
        st.rerun()

    # Display jobs table
    jobs = get_all_jobs()
    if jobs:
        df = pd.DataFrame(
            jobs,
            columns=["ID", "Filename", "Status", "Raw Text", "Corrected Text", "Created At"]
        )
        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                "ID": st.column_config.TextColumn("Job ID", width="small"),
                "Filename": st.column_config.TextColumn("File", width="medium"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Raw Text": st.column_config.TextColumn("Raw OCR", width="large"),
                "Corrected Text": st.column_config.TextColumn("Corrected", width="large"),
                "Created At": st.column_config.DatetimeColumn("Created", width="medium"),
            }
        )
    else:
        st.info("No jobs in the queue. Upload some images to get started.")


def main() -> None:
    """Main application entry point."""
    st.set_page_config(
        page_title="Arabic OCR System",
        page_icon="📝",
        layout="wide"
    )

    st.title("Arabic OCR System")
    st.markdown("Extract and correct Arabic text from document images.")

    # Start background worker
    start_worker()

    # Render tabs
    tab1, tab2 = st.tabs(["📤 Batch Upload", "📋 Results & History"])

    with tab1:
        render_upload_tab()

    with tab2:
        render_results_tab()


if __name__ == "__main__":
    main()
