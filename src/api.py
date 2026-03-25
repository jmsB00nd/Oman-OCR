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

import pandas as pd
import requests
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
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
def process_image_with_tesseract(image_path: Path) -> str:
    """Uses Tesseract to extract raw text, supporting English and Arabic."""
    try:
        img = Image.open(image_path)
        # Using both Arabic and English. Tesseract will attempt to detect both.
        text = pytesseract.image_to_string(img, lang='ara+eng')
        return text
    except Exception as e:
        logger.error(f"Tesseract extraction failed: {e}")
        raise

def structure_text_with_llm(raw_text: str) -> str:
    """Uses the LLM to extract only tables and relevant financial notes."""
    system_prompt = (
        "You are a specialized financial data extraction agent. "
        "Your goal is to extract ONLY tables and supplemental financial notes from the provided OCR text. "
        "\n\nSTRICT RULES:\n"
        "1. TABLES: Reconstruct all financial grids, ledgers, or balance sheets into clean Markdown tables.\n"
        "2. NOTES: Extract paragraphs that provide context to the numbers (e.g., accounting policies, "
        "explanations of line items, or legal disclosures). These may NOT always start with numbers like (1) or [1].\n"
        "3. EXCLUDE: Do not include headers, footers, page numbers, or decorative text.\n"
        "4. LANGUAGE: Maintain the original Arabic and English text as found in the document.\n"
        "5. NO HALLUCINATION: If a value is unreadable, use '---'. Do not invent figures."
    )
    
    response = requests.post(
        TEXT_URL,
        json={
            "model": "/models/text",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract tables and notes from this text:\n\n{raw_text}"}
            ],
            "temperature": 0.0, # Set to 0 for maximum extraction accuracy
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def filter_tables_and_notes(text: str) -> str:
    """
    Cleans the LLM output to ensure only the Markdown content is passed to Excel.
    This version is more permissive to capture notes that don't start with digits.
    """
    if not text:
        return ""
        
    lines = text.splitlines()
    filtered_lines = []
    
    for line in lines:
        stripped = line.strip()
        # Keep table rows
        if stripped.startswith('|'):
            filtered_lines.append(line)
        # Keep non-empty lines that aren't markdown artifacts (like ``` or headers)
        elif stripped and not stripped.startswith('#') and not stripped.startswith('```'):
            filtered_lines.append(line)
            
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
            
            raw_text = process_image_with_tesseract(image_path)
            
            corrected_text = structure_text_with_llm(raw_text)
            
            filtered_text = filter_tables_and_notes(corrected_text)

            image_path.with_name(f"{image_path.stem}_raw.md").write_text(raw_text, encoding="utf-8")
            image_path.with_suffix(".md").write_text(corrected_text, encoding="utf-8")
            save_markdown_to_excel(filtered_text, image_path.with_suffix(".xlsx"))

            update_job(job_id, JobStatus.COMPLETED, raw_text, corrected_text)
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
            # Use pdf2image to convert PDF bytes to PIL Images at 300 DPI
            pages = convert_from_bytes(file_bytes, dpi=300)
            
            for page_num, page_image in enumerate(pages):
                img_name = f"{file_stem}_page_{page_num + 1}.jpg"
                img_path = str(file_dir / img_name)
                
                # Save the PIL image to disk for the worker to pick up
                page_image.save(img_path, "JPEG")
                
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