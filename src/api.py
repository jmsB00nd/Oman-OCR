"""FastAPI Backend for Arabic Document Processor."""

import base64
import logging
import os
import re
import shutil
import threading
import time
from pathlib import Path
from typing import List

import fitz
import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import (
    JobStatus,
    add_job,
    clear_db,
    get_all_jobs,
    get_next_job,
    init_db,
    update_job,
)

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

VISION_URL = os.getenv("VISION_URL", "http://localhost:8000/v1/chat/completions")
TEXT_URL = os.getenv("TEXT_URL", "http://localhost:8001/v1/chat/completions")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))
WORKER_POLL_INTERVAL = 2

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Arabic OCR API")

# Allow Streamlit to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the uploads directory to serve images directly to the frontend
app.mount("/images", StaticFiles(directory=UPLOAD_DIR), name="images")


# --- OCR Processing Functions ---
def process_image_with_vision(image_path: Path) -> str:
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
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                        {"type": "text", "text": "Free OCR."},
                    ],
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.0,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def correct_text_with_llm(raw_text: str) -> str:
    response = requests.post(
        TEXT_URL,
        json={
            "model": "/models/text",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Fix OCR errors in this text but DO NOT alter the Markdown table structure. "
                        "Keep all '|' delimiters exactly where they are."
                        f"{raw_text}"
                    ),
                }
            ],
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def filter_tables_and_notes(text: str) -> str:
    if not text:
        return ""
    filtered_lines = []
    note_pattern = re.compile(r'^\s*(\(\d+\)|\[\d+\])\s+')
    in_note_block = False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('|'):
            filtered_lines.append(line)
            in_note_block = False
        elif note_pattern.match(stripped):
            if filtered_lines and filtered_lines[-1].strip() != "":
                filtered_lines.append("") 
            filtered_lines.append(line)
            in_note_block = True
        elif in_note_block and stripped != "":
            filtered_lines.append(line)
        elif stripped == "":
            in_note_block = False

    return '\n'.join(filtered_lines).strip()


def save_markdown_to_excel(md_text: str, excel_path: Path) -> None:
    lines = md_text.splitlines()
    table_data = []
    notes = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped: continue
        if stripped.startswith('|'):
            if re.match(r'^\|[\-\s\|]+\|$', stripped) or re.match(r'^\|[\-\s\|]+$', stripped):
                continue
            row_vals = [col.strip() for col in stripped.split('|')]
            row_vals = row_vals[1:-1] if stripped.endswith('|') else row_vals[1:]
            table_data.append(row_vals)
        else:
            notes.append(stripped)
            
    try:
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            if table_data:
                headers = table_data[0]
                rows = []
                for r in table_data[1:]:
                    if len(r) < len(headers): r.extend([''] * (len(headers) - len(r)))
                    elif len(r) > len(headers): r = r[:len(headers)]
                    rows.append(r)
                pd.DataFrame(rows, columns=headers).to_excel(writer, sheet_name='Table', index=False)
            if notes:
                pd.DataFrame(notes, columns=["Notes"]).to_excel(writer, sheet_name='Notes', index=False)
    except Exception as e:
        logger.error(f"Failed to generate Excel: {e}")


# --- Background Worker ---
def worker_loop() -> None:
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
            raw_text = process_image_with_vision(image_path)
            filtered_text = filter_tables_and_notes(raw_text)
            corrected_text = correct_text_with_llm(filtered_text)

            image_path.with_name(f"{image_path.stem}_raw.md").write_text(raw_text, encoding="utf-8")
            image_path.with_suffix(".md").write_text(corrected_text, encoding="utf-8")
            save_markdown_to_excel(corrected_text, image_path.with_suffix(".xlsx"))

            update_job(job_id, JobStatus.COMPLETED, filtered_text, corrected_text)
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            update_job(job_id, f"{JobStatus.FAILED}: {str(e)}")


@app.on_event("startup")
def startup_event():
    init_db()
    threading.Thread(target=worker_loop, daemon=True).start()


# --- API Endpoints ---
@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    queued = 0
    for f in files:
        file_bytes = await f.read()
        file_stem = Path(f.filename).stem
        file_dir = UPLOAD_DIR / file_stem
        file_dir.mkdir(parents=True, exist_ok=True)
        
        if f.filename.lower().endswith(".pdf"):
            pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page_num in range(len(pdf_doc)):
                page = pdf_doc.load_page(page_num)
                pix = page.get_pixmap(dpi=300)
                img_name = f"{file_stem}_page_{page_num + 1}.jpg"
                pix.save(str(file_dir / img_name))
                add_job(f"{file_stem}/{img_name}")
                queued += 1
        else:
            with open(file_dir / f.filename, "wb") as out:
                out.write(file_bytes)
            add_job(f"{file_stem}/{f.filename}")
            queued += 1
            
    return {"queued": queued}


@app.get("/jobs")
def fetch_jobs():
    """Returns all jobs as dictionaries."""
    return [dict(row) for row in get_all_jobs()]


@app.post("/clear")
def clear_all():
    clear_db()
    for p in UPLOAD_DIR.iterdir():
        try:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        except Exception:
            pass
    return {"status": "cleared"}