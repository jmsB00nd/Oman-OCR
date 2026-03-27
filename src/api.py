"""FastAPI Backend for Arabic Document Processor (Chandra OCR 2)."""

import base64
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import List

import pandas as pd
import requests
from PIL import Image
from pdf2image import convert_from_bytes
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import difflib

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


# --- NEW: Chandra Processing Function ---
def process_with_chandra(image_path: Path) -> str:
    """Uses Chandra OCR 2 via vLLM to extract structured markdown."""
    out_dir = image_path.parent / f"{image_path.stem}_chandra"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Route Chandra to the vLLM container
    env = os.environ.copy()
    env["VLLM_API_BASE"] = os.getenv("VLLM_API_BASE", "http://text-engine:8001/v1")
    env["VLLM_MODEL_NAME"] = os.getenv("VLLM_MODEL_NAME", "chandra")
    
    cmd = [
        "chandra", 
        str(image_path), 
        str(out_dir), 
        "--method", "vllm"
    ]
    
    try:
        subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Chandra OCR failed: {e.stderr}")
        raise RuntimeError(f"Chandra extraction failed: {e.stderr}")
        
    # Find the generated markdown file
    md_files = list(out_dir.rglob("*.md"))
    if not md_files:
        raise FileNotFoundError("Chandra OCR did not produce a markdown file.")
    
    target_md = next((f for f in md_files if image_path.stem in f.name), md_files[0])
    return target_md.read_text(encoding="utf-8")


def filter_tables_and_notes(text: str) -> str:
    """
    Cleans the output to ensure only the Markdown content is passed to Excel.
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
            
            # 1. End-to-End Extraction
            md_text = process_with_chandra(image_path)
            
            # 2. Filter for Excel export
            filtered_text = filter_tables_and_notes(md_text)
            
            # 3. Save artifacts
            raw_placeholder = "N/A - Direct to Markdown via Chandra 2 End-to-End Vision Model."
            image_path.with_name(f"{image_path.stem}_raw.md").write_text(raw_placeholder, encoding="utf-8")
            image_path.with_suffix(".md").write_text(md_text, encoding="utf-8")
            save_markdown_to_excel(filtered_text, image_path.with_suffix(".xlsx"))
            
            # Update job (Using the placeholder for raw_text to not break the UI's diff viewer)
            update_job(job_id, JobStatus.COMPLETED, raw_placeholder, md_text)
            
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

def markdown_to_json(md_text: str) -> dict:
    """Parses a Markdown table and notes into a structured JSON dictionary."""
    if not md_text:
        return {"table": [], "notes": []} 
        
    lines = md_text.splitlines()
    table_data = []
    notes = []
    headers = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped: 
            continue
            
        if stripped.startswith('|'):
            # Skip Markdown separator lines like |---|---|
            if re.match(r'^\|[\-\s\|]+\|$', stripped) or re.match(r'^\|[\-\s\|]+$', stripped):
                continue
                
            # Extract row values
            row_vals = [col.strip() for col in stripped.split('|')]
            row_vals = row_vals[1:-1] if stripped.endswith('|') else row_vals[1:]
            
            if not headers:
                # First valid row becomes our dictionary keys
                headers = row_vals
            else:
                # Map row values to the header keys
                row_dict = {}
                for i, val in enumerate(row_vals):
                    key = headers[i] if i < len(headers) else f"Column_{i+1}"
                    row_dict[key] = val
                table_data.append(row_dict)
        else:
            # Clean up and normalize notes
            cleaned_note = stripped
            
            # Skip standalone header lines like "### Notes:" or "Notes:"
            if re.match(r'^#+\s*Notes?:?\s*$', cleaned_note, re.IGNORECASE) or cleaned_note.lower() in ['notes:', 'notes']:
                continue
                
            # Remove leading bullet points (- or *)
            cleaned_note = re.sub(r'^[-*]\s+', '', cleaned_note)
            
            # Remove markdown bolding formatting (e.g., **Note 1** -> Note 1)
            cleaned_note = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned_note)
            
            # Add to the list if the line isn't empty after cleaning
            if cleaned_note:
                notes.append(cleaned_note)
                
    return {
        "table": table_data,
        "notes": notes 
    }
    

@app.get("/jobs/structured")
def fetch_jobs_structured():
    """
    Returns jobs formatted as structured JSON arrays instead of Markdown strings,
    and removes the raw_text from the response. Ideal for external API consumption.
    """
    jobs = []
    
    for row in get_all_jobs():
        job_dict = dict(row)
        
        # 1. Initialize default metrics
        metrics = {
            "similarity": 0.0,
            "changes": 0,
            "change_ratio": 0.0
        }
        
        raw_text = job_dict.get("raw_text") or ""
        corrected_text = job_dict.get("corrected_text") or ""
        
        # 2. Calculate metrics using the raw text BEFORE removing it
        if raw_text and corrected_text:
            sim = difflib.SequenceMatcher(None, raw_text, corrected_text).ratio() * 100
            
            char_diff = list(difflib.ndiff(raw_text, corrected_text))
            changes_count = sum(1 for d in char_diff if d.startswith("+ ") or d.startswith("- "))
            
            change_ratio = abs(len(corrected_text) - len(raw_text)) / max(len(raw_text), 1)
            
            metrics = {
                "similarity": round(sim, 2),
                "changes": changes_count,
                "change_ratio": round(change_ratio, 4)
            }
            
        job_dict["metrics"] = metrics
        
        # 3. Parse the markdown into a JSON structure
        parsed_data = markdown_to_json(corrected_text)
        
        # 4. Replace the markdown string with the JSON array & notes
        job_dict["corrected_text"] = parsed_data["table"]
        job_dict["notes"] = parsed_data["notes"]
        
        # 5. Remove raw_text from the final dictionary
        job_dict.pop("raw_text", None)
        
        jobs.append(job_dict)
        
    return jobs


@app.get("/jobs")
def fetch_jobs():
    """Returns all jobs as dictionaries, including text comparison metrics."""
    jobs = []
    
    for row in get_all_jobs():
        job_dict = dict(row)
        
        # Initialize default metrics
        metrics = {
            "similarity": 0.0,
            "changes": 0,
            "change_ratio": 0.0
        }
        
        raw_text = job_dict.get("raw_text") or ""
        corrected_text = job_dict.get("corrected_text") or ""
        
        # Calculate metrics if both texts are available
        if raw_text and corrected_text:
            # Calculate Similarity
            sim = difflib.SequenceMatcher(None, raw_text, corrected_text).ratio() * 100
            
            # Calculate Changes
            char_diff = list(difflib.ndiff(raw_text, corrected_text))
            changes_count = sum(1 for d in char_diff if d.startswith("+ ") or d.startswith("- "))
            
            # Calculate Change Ratio
            change_ratio = abs(len(corrected_text) - len(raw_text)) / max(len(raw_text), 1)
            
            # Update metrics object with rounded values
            metrics = {
                "similarity": round(sim, 2),
                "changes": changes_count,
                "change_ratio": round(change_ratio, 4)
            }
            
        # Attach metrics to the job
        job_dict["metrics"] = metrics
        jobs.append(job_dict)
        
    return jobs


@app.post("/clear")
def clear_all():
    clear_db()
    for p in UPLOAD_DIR.iterdir():
        try:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        except Exception:
            pass
    return {"status": "cleared"}