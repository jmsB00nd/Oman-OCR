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
from bs4 import BeautifulSoup
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


def process_with_chandra(image_path: Path) -> str:
    """Uses Chandra OCR 2 via vLLM to extract structured markdown."""
    out_dir = image_path.parent / f"{image_path.stem}_chandra"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Route Chandra to the vLLM container
    env = os.environ.copy()
    env["VLLM_API_BASE"] = os.getenv("VLLM_API_BASE", "http://text-engine:8001/v1")
    env["VLLM_MODEL_NAME"] = os.getenv("VLLM_MODEL_NAME", "chandra")
    
    # ADD THE --max-output-tokens FLAG HERE
    cmd = [
        "chandra", 
        str(image_path), 
        str(out_dir), 
        "--method", "vllm",
        "--max-output-tokens", "8192"  
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



def save_markdown_to_excel(md_text: str, excel_path: Path) -> None:
    """Extracts HTML tables and notes to an Excel file."""
    if not md_text:
        return
        
    soup = BeautifulSoup(md_text, "html.parser")
    table_data = []
    
    # 1. Extract HTML Tables
    table_tags = soup.find_all("table")
    if table_tags:
        table = table_tags[0]
        
        for br in table.find_all("br"):
            br.replace_with(" ")
            
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            row_vals = [cell.get_text(strip=True) for cell in cells]
            if row_vals:
                table_data.append(row_vals)
                
        for t in table_tags:
            t.decompose()
            
    # 2. Extract Notes
    notes = []
    raw_text = soup.get_text(separator="\n")
    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("```"):
            notes.append(stripped)

    # 3. Save to Excel using Pandas
    try:
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            if table_data:
                # Calculate max columns to handle rows with colspans (like "ASSETS")
                max_cols = max(len(r) for r in table_data)
                headers = table_data[0]
                
                # Pad headers if necessary
                if len(headers) < max_cols:
                    headers.extend([f"Column_{i+1}" for i in range(len(headers), max_cols)])
                    
                # Pad data rows
                rows = []
                for r in table_data[1:]:
                    r.extend([""] * (max_cols - len(r)))
                    rows.append(r)
                    
                pd.DataFrame(rows, columns=headers).to_excel(writer, sheet_name="Table", index=False)
                
            if notes:
                pd.DataFrame(notes, columns=["Notes"]).to_excel(writer, sheet_name="Notes", index=False)
    except Exception as e:
        logger.error(f"Failed to generate Excel: {e}")
    
def filter_markdown_to_structured_data(md_text: str) -> str:
    """Filters Markdown to ONLY include the table and notes specifically referenced within it."""
    if not md_text:
        return ""
        
    soup = BeautifulSoup(md_text, "html.parser")
    table_tags = soup.find_all("table")
    
    # If there is no table, return empty string to enforce "nothing else" is displayed
    if not table_tags:
        return "" 
        
    table = table_tags[0]
    valid_markers = set()
    
    # Matches patterns like (1), [1], (a), [a]
    marker_pattern = re.compile(r'(\(\w+\)|\[\w+\])') 
    
    # 1. Extract valid note markers directly from the table cells
    for cell in table.find_all(["th", "td"]):
        valid_markers.update(marker_pattern.findall(cell.get_text()))
        
    # 2. Remove the table from the soup so we can process the remaining text
    for t in table_tags:
        t.decompose() 
        
    valid_notes = []
    raw_text = soup.get_text(separator="\n")
    
    # 3. Extract matching notes from the rest of the document
    for line in raw_text.splitlines():
        stripped = line.strip()
        
        # Strip potential "Note:" prefixes just in case the OCR added them
        clean_line = re.sub(r'^(Notes?:?\s*)', '', stripped, flags=re.IGNORECASE).strip()
        
        # A note is valid ONLY if it starts with a marker found in the table
        if clean_line and any(clean_line.startswith(marker) for marker in valid_markers):
            valid_notes.append(stripped) # Append the original stripped line
            
    # 4. Reconstruct clean output (HTML format handles tables/text flawlessly in Streamlit)
    output_html = [str(table)]
    if valid_notes:
        notes_html = "".join([f"<p>{n}</p>" for n in valid_notes])
        output_html.append(f"<div style='margin-top: 15px;'>{notes_html}</div>")
        
    return "\n".join(output_html)


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
            raw_md = process_with_chandra(image_path)
            
            # 2. FILTER the text strictly to the table and referenced notes
            filtered_md = filter_markdown_to_structured_data(raw_md)
            
            # 3. Save artifacts using the filtered text
            raw_placeholder = "N/A - Direct to Markdown via Chandra 2 End-to-End Vision Model."
            image_path.with_name(f"{image_path.stem}_raw.md").write_text(raw_placeholder, encoding="utf-8")
            image_path.with_suffix(".md").write_text(filtered_md, encoding="utf-8")
            
            # Use the existing BeautifulSoup-powered function
            save_markdown_to_excel(filtered_md, image_path.with_suffix(".xlsx"))
            
            # Update job with the newly filtered data
            update_job(job_id, JobStatus.COMPLETED, raw_placeholder, filtered_md)
            
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
    """Parses an HTML table and notes from Chandra OCR into a JSON dictionary."""
    if not md_text:
        return {"table": [], "notes": []} 
        
    soup = BeautifulSoup(md_text, "html.parser")
    table_data = []
    headers = []
    
    # 1. Parse HTML Tables
    table_tags = soup.find_all("table")
    if table_tags:
        table = table_tags[0] # Grab the primary table
        
        # Convert <br/> tags to spaces for cleaner keys/values
        for br in table.find_all("br"):
            br.replace_with(" ")
            
        for row in table.find_all("tr"):
            # Extract both headers and standard cells
            cells = row.find_all(["th", "td"])
            row_vals = [cell.get_text(strip=True) for cell in cells]
            
            if not row_vals:
                continue
                
            if not headers and row.find("th"):
                headers = row_vals
            elif not headers: # Fallback if Chandra doesn't use <th>
                headers = row_vals
            else:
                row_dict = {}
                for i, val in enumerate(row_vals):
                    key = headers[i] if i < len(headers) else f"Column_{i+1}"
                    row_dict[key] = val
                table_data.append(row_dict)
                
        # Remove the table from the soup so we can easily extract the notes
        for t in table_tags:
            t.decompose()
            
    # 2. Parse Remaining Text as Notes
    notes = []
    raw_text = soup.get_text(separator="\n")
    
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped: 
            continue
            
        # Skip standalone header lines
        if re.match(r'^#+\s*Notes?:?\s*$', stripped, re.IGNORECASE) or stripped.lower() in ['notes:', 'notes']:
            continue
            
        # Clean up Markdown formatting
        cleaned = re.sub(r'^[-*]\s+', '', stripped)
        cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)
        
        if cleaned:
            notes.append(cleaned)
            
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