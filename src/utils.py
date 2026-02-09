import requests
import os
import base64
from pathlib import Path
import streamlit as st
import logging
from config import TRANSLATIONS
from database import clear_all_data
import threading
import time

from config import UPLOAD_DIR, VISION_URL, TEXT_URL, WORKER_POLL_INTERVAL

from database import (
    JobStatus,
    get_next_job,
    update_job,
    clear_all_data,
)

# Ensure upload directory exists
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

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
                            "text": "Extract all Arabic text from this image. Return only the text, no explanations."
                        }
                    ]
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.0,
            "extra_body": {
                "skip_special_tokens": False,
                "vllm_xargs": {
                    "ngram_size": 30,
                    "window_size": 90,
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

def clear_previous_data() -> bool:
    """Clear all previous data from database and files."""
    try:
        # Clear all data
        clear_all_data()
        
        # Reset session state
        if "selected_image" in st.session_state:
            st.session_state.selected_image = 0
        
        logger.info("All previous data cleared")
        return True
    except Exception as e:
        logger.error(f"Error clearing previous data: {e}")
        return False
    
def get_text(key: str) -> str:
    """Get translated text based on current language."""
    lang = st.session_state.get("language", "en")
    return TRANSLATIONS[lang].get(key, key)

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
            raw_text = "567 raw text" #process_image_with_vision(image_path)
            logger.info(f"Job {job_id}: Vision extraction complete")

            # Step 2: Correct OCR errors
            corrected_text = "78 corrected text" #correct_text_with_llm(raw_text)
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
    