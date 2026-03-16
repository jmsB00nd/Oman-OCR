"""Arabic Document Processor Application - Main entry point with Enhanced UI."""

import base64
import difflib
import html as html_lib
import logging
import os
import shutil
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image
import fitz

from database import (
    JobStatus,
    add_job,
    clear_db,
    get_all_jobs,
    get_job_stats,
    get_next_job,
    init_db,
    update_job,
)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

VISION_URL = os.getenv("VISION_URL", "http://localhost:8000/v1/chat/completions")
TEXT_URL = os.getenv("TEXT_URL", "http://localhost:8001/v1/chat/completions")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))
WORKER_POLL_INTERVAL = 2  # seconds

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

LANGUAGES = {"en": "🇬🇧 English", "ar": "🇸🇦 العربية"}

TRANSLATIONS = {
    "en": {
        "title": "Arabic OCR System",
        "subtitle": "Extract and correct Arabic text from document images",
        "upload_header": "Upload Documents",
        "upload_description": "Upload images containing Arabic text for OCR processing.",
        "upload_instructions": "Supported formats: PDF, PNG, JPG, JPEG, TIFF, BMP",
        "upload_placeholder": "Drag and drop images here",
        "upload_button": "🚀 Start Processing",
        "results_header": "Processing Results",
        "stats_header": "Statistics",
        "pending": "Pending",
        "processing": "Processing",
        "completed": "Completed",
        "failed": "Failed",
        "all_files": "Total Files",
        "success_rate": "Success Rate",
        "no_jobs": "No jobs yet",
        "no_completed": "No completed jobs yet",
        "current_session": "Completed Results",
        "processing_queue": "Processing Queue",
        "unprocessed_text": "⚠️ Raw VLM Output",
        "ai_powered": "✨ AI-Corrected",
        "corrected": "Corrected Text",
        "comparison_view": "🔍 Comparison",
        "file": "File",
        "created": "Created",
        "status": "Status",
        "download_raw": "📥 Download Raw",
        "download_text": "📥 Download Corrected",
        "download_report": "📥 Download Report",
        "no_corrected": "No corrected text available.",
        "clear_results": "🗑️ Clear All",
        "new_session": "Session cleared!",
        "queued_success": "✅ Queued {count} file(s) for processing.",
        "refresh_button": "🔄 Refresh",
        "position": "Position",
        "raw": "Raw",
    },
    "ar": {
        "title": "نظام التعرف الضوئي على النصوص العربية",
        "subtitle": "استخراج وتصحيح النصوص العربية من صور المستندات",
        "upload_header": "تحميل المستندات",
        "upload_description": "قم بتحميل الصور التي تحتوي على نص عربي للمعالجة.",
        "upload_instructions": "الصيغ المدعومة: PDF, PNG, JPG, JPEG, TIFF, BMP",
        "upload_placeholder": "اسحب وأفلت الصور هنا",
        "upload_button": "🚀 بدء المعالجة",
        "results_header": "نتائج المعالجة",
        "stats_header": "الإحصائيات",
        "pending": "قيد الانتظار",
        "processing": "قيد المعالجة",
        "completed": "مكتمل",
        "failed": "فشل",
        "all_files": "إجمالي الملفات",
        "success_rate": "نسبة النجاح",
        "no_jobs": "لا توجد مهام بعد",
        "no_completed": "لا توجد مهام مكتملة بعد",
        "current_session": "النتائج المكتملة",
        "processing_queue": "قائمة المعالجة",
        "unprocessed_text": "⚠️ نص خام",
        "ai_powered": "✨ مصحح بالذكاء الاصطناعي",
        "corrected": "النص المصحح",
        "comparison_view": "🔍 المقارنة",
        "file": "الملف",
        "created": "تاريخ الإنشاء",
        "status": "الحالة",
        "download_raw": "📥 تحميل الخام",
        "download_text": "📥 تحميل المصحح",
        "download_report": "📥 تحميل التقرير",
        "no_corrected": "لا يوجد نص مصحح.",
        "clear_results": "🗑️ مسح الكل",
        "new_session": "تم مسح الجلسة!",
        "queued_success": "✅ تمت إضافة {count} ملف(ات) للمعالجة.",
        "refresh_button": "🔄 تحديث",
        "position": "الموضع",
        "raw": "خام",
    },
}


def t(key: str) -> str:
    """Get translated text for the current language."""
    lang = st.session_state.get("language", "en")
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)


# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────────────────────────────────────

CUSTOM_CSS = """
<style>
/* --- Global --- */
.stApp { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }

/* Header */
.header-container {
    text-align: center;
    padding: 1.5rem 0 1rem;
}
.header-title {
    background: linear-gradient(135deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.4rem;
    font-weight: 800;
    margin-bottom: 0.25rem;
}
.header-subtitle {
    color: #718096;
    font-size: 1.05rem;
}

/* Metric cards */
.metric-card {
    background: white;
    border-radius: 12px;
    padding: 1.2rem 1rem;
    text-align: center;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    border: 1px solid #e2e8f0;
}
.metric-value { font-size: 1.8rem; font-weight: 700; color: #2d3748; }
.metric-label { font-size: 0.85rem; color: #718096; margin-top: 0.25rem; }

/* Custom card */
.custom-card {
    background: white;
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    border: 1px solid #e2e8f0;
}

/* Text displays */
.text-display {
    padding: 1rem;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
    min-height: 180px;
    max-height: 400px;
    overflow-y: auto;
    line-height: 1.8;
    font-size: 1rem;
}
.text-display.rtl { direction: rtl; text-align: right; }
.text-display.ltr { direction: ltr; text-align: left; }

/* Image preview */
.image-preview {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #e2e8f0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

/* Status badges */
.status-completed {
    background: #c6f6d5; color: #22543d;
    padding: 0.2rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 600;
}
.status-processing {
    background: #bee3f8; color: #2a4365;
    padding: 0.2rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 600;
}
.status-pending {
    background: #fefcbf; color: #744210;
    padding: 0.2rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 600;
}
.status-failed {
    background: #fed7d7; color: #742a2a;
    padding: 0.2rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 600;
}
</style>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Backend helpers (unchanged from your original main.py)
# ─────────────────────────────────────────────────────────────────────────────

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
                                "url": f"data:image/jpeg;base64,{img_b64}",
                            },
                        },
                        {
                            "type": "text",
                            "text": "Free OCR.",
                        },
                    ],
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
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def correct_text_with_llm(raw_text: str) -> str:
    """Send text to LLM for OCR error correction."""
    response = requests.post(
        TEXT_URL,
        json={
            "model": "/models/text",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Fix any OCR errors in this Arabic text and return "
                        f"only the corrected text: {raw_text}"
                    ),
                }
            ],
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def filter_tables_and_notes(text: str) -> str:
    """Filter markdown text to keep only tables and note references."""
    if not text:
        return ""

    filtered_lines = []
    # Matches notes starting with (1), [1], (٠), [٠] etc. (\d catches Arabic numerals too)
    note_pattern = re.compile(r'^\s*(\(\d+\)|\[\d+\])\s+')
    in_note_block = False

    for line in text.splitlines():
        stripped = line.strip()

        # Keep Table Rows
        if stripped.startswith('|'):
            filtered_lines.append(line)
            in_note_block = False
            
        # Keep Notes (and add a blank line above them for readability)
        elif note_pattern.match(stripped):
            if filtered_lines and filtered_lines[-1].strip() != "":
                filtered_lines.append("") 
            filtered_lines.append(line)
            in_note_block = True
            
        # Handle multi-line notes
        elif in_note_block and stripped != "":
            filtered_lines.append(line)
            
        # Empty lines break the multi-line note continuation
        elif stripped == "":
            in_note_block = False

    return '\n'.join(filtered_lines).strip()


def save_markdown_to_excel(md_text: str, excel_path: Path) -> None:
    """Parse markdown text to extract tables and notes, saving to an Excel file."""
    lines = md_text.splitlines()
    table_data = []
    notes = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Check if the line is part of a Markdown table
        if stripped.startswith('|'):
            # Skip the markdown separator rows (e.g., |---|---|)
            if re.match(r'^\|[\-\s\|]+\|$', stripped) or re.match(r'^\|[\-\s\|]+$', stripped):
                continue
            
            # Split row by pipe '|', ignoring the first and last empty strings from the edges
            row_vals = [col.strip() for col in stripped.split('|')]
            if stripped.endswith('|'):
                row_vals = row_vals[1:-1]
            else:
                row_vals = row_vals[1:]
            
            table_data.append(row_vals)
        else:
            # It's a note
            notes.append(stripped)
            
    # Write to Excel
    try:
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # Save Table
            if table_data:
                headers = table_data[0]
                rows = []
                # Ensure all rows have the same length as the header to avoid Pandas errors
                for r in table_data[1:]:
                    if len(r) < len(headers):
                        r.extend([''] * (len(headers) - len(r)))
                    elif len(r) > len(headers):
                        r = r[:len(headers)]
                    rows.append(r)
                
                df_table = pd.DataFrame(rows, columns=headers)
                df_table.to_excel(writer, sheet_name='Table', index=False)
            
            # Save Notes
            if notes:
                df_notes = pd.DataFrame(notes, columns=["Notes"])
                df_notes.to_excel(writer, sheet_name='Notes', index=False)
                
    except Exception as e:
        logger.error(f"Failed to generate Excel file: {e}")


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
            raw_text = process_image_with_vision(image_path)
            logger.info(f"Job {job_id}: Vision extraction complete")
            filtered_text = filter_tables_and_notes(raw_text)
            corrected_text = correct_text_with_llm(filtered_text)
            logger.info(f"Job {job_id}: Text correction complete")

            md_path = image_path.with_suffix(".md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(corrected_text)
            logger.info(f"Job {job_id}: Markdown written to {md_path}")

            excel_path = image_path.with_suffix(".xlsx")
            save_markdown_to_excel(corrected_text, excel_path)
            logger.info(f"Job {job_id}: Excel written to {excel_path}")

            update_job(job_id, JobStatus.COMPLETED, filtered_text, corrected_text)
            logger.info(f"Job {job_id}: Completed successfully")

        except requests.RequestException as e:
            error_msg = f"API error: {e}"
            logger.error(f"Job {job_id}: {error_msg}")
            update_job(job_id, f"{JobStatus.FAILED}: {error_msg}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Job {job_id}: {error_msg}")
            update_job(job_id, f"{JobStatus.FAILED}: {error_msg}")


def start_worker() -> None:
    """Start the background worker thread (once per session)."""
    if "worker_started" not in st.session_state:
        thread = threading.Thread(target=worker_loop, daemon=True)
        thread.start()
        st.session_state.worker_started = True
        logger.info("Background worker thread started")


def calculate_similarity(text1: str, text2: str) -> float:
    """Return percentage similarity between two strings."""
    return difflib.SequenceMatcher(None, text1, text2).ratio() * 100


def fix_data_permissions() -> None:
    """Attempt to fix data-directory ownership on Linux/Docker."""
    if sys.platform == "win32":
        return
    data_dir = str(UPLOAD_DIR.parent)
    try:
        subprocess.run(
            ["chown", "-R", "1000:1000", data_dir],
            check=False, capture_output=True, timeout=10,
        )
        subprocess.run(
            ["chmod", "-R", "755", data_dir],
            check=False, capture_output=True, timeout=10,
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# UI – Token gate & sidebar
# ─────────────────────────────────────────────────────────────────────────────

def render_token_gate() -> bool:
    """Block the UI until a Hugging Face token is available."""
    token = st.session_state.get("hf_token", os.getenv("HF_TOKEN", "")).strip()
    if token:
        return True

    st.warning(
        "### 🔑 Hugging Face Token Required\n\n"
        "This system downloads **google/gemma-3-4b-it** (Gemma 3 4B) — a gated model. "
        "Your token must have been granted access before model setup will work.\n\n"
        "**Steps:**\n"
        "1. Visit [huggingface.co/google/gemma-3-4b-it](https://huggingface.co/google/gemma-3-4b-it) "
        "and accept the licence.\n"
        "2. Generate a *read* token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).\n"
        "3. Paste the token below and click **Save & Continue**."
    )

    col_in, col_btn = st.columns([4, 1])
    with col_in:
        new_token = st.text_input(
            "HF Token", type="password", placeholder="hf_...",
            label_visibility="collapsed",
        )
    with col_btn:
        save = st.button("Save & Continue", type="primary")

    if save and new_token.strip():
        st.session_state["hf_token"] = new_token.strip()
        os.environ["HF_TOKEN"] = new_token.strip()
        st.rerun()
    elif save:
        st.error("Please enter a valid token.")
    return False


def render_hf_token_sidebar() -> None:
    """Always-visible token management widget."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔑 Hugging Face Token")
    current = st.session_state.get("hf_token", os.getenv("HF_TOKEN", ""))
    new_token = st.sidebar.text_input(
        "Token", value=current, type="password", placeholder="hf_...",
    )
    if new_token and new_token != current:
        st.session_state["hf_token"] = new_token
        os.environ["HF_TOKEN"] = new_token
        st.sidebar.success("Token updated.")
    elif not new_token:
        st.sidebar.warning("⚠️ No token — model downloads will fail.")


# ─────────────────────────────────────────────────────────────────────────────
# UI – Language selector
# ─────────────────────────────────────────────────────────────────────────────

def render_language_selector() -> None:
    """Top-right language picker."""
    _, _, col_lang = st.columns([8, 1, 1])
    with col_lang:
        selected = st.selectbox(
            "",
            options=list(LANGUAGES.keys()),
            format_func=lambda x: LANGUAGES[x],
            index=list(LANGUAGES.keys()).index(
                st.session_state.get("language", "en")
            ),
            label_visibility="collapsed",
            key="lang_selector",
        )
    if selected != st.session_state.get("language", "en"):
        st.session_state.language = selected
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# UI – Statistics
# ─────────────────────────────────────────────────────────────────────────────

def render_statistics(jobs: list) -> None:
    """Render stat cards above the results."""
    completed = [j for j in jobs if j[2] == JobStatus.COMPLETED]
    pending = [j for j in jobs if j[2] in (JobStatus.PENDING, JobStatus.PROCESSING)]
    failed = [j for j in jobs if j[2].startswith(JobStatus.FAILED)]
    rate = (len(completed) / len(jobs) * 100) if jobs else 0

    st.markdown(
        f"<h3 style='margin-bottom:1.5rem;'>{t('stats_header')}</h3>",
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4, c5 = st.columns(5)
    for col, val, label in [
        (c1, len(pending), t("pending")),
        (c2, len(completed), t("completed")),
        (c3, len(failed), t("failed")),
        (c4, len(jobs), t("all_files")),
    ]:
        col.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value">{val}</div>'
            f'<div class="metric-label">{label}</div></div>',
            unsafe_allow_html=True,
        )
    c5.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-value">{rate:.1f}%</div>'
        f'<div class="metric-label">{t("success_rate")}</div></div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# UI – Upload + Results (single-page layout)
# ─────────────────────────────────────────────────────────────────────────────

def render_upload_section() -> None:
    """File uploader + clear button."""
    st.markdown(
        f'<div class="custom-card" style="margin-bottom:2rem;">'
        f'<h2 style="color:#667eea;margin-bottom:0.5rem;">{t("upload_header")}</h2>'
        f'<p style="color:#6c757d;">{t("upload_description")}</p>'
        f'<p style="color:#adb5bd;font-size:0.9rem;">{t("upload_instructions")}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )

    col_upload, _, _, col_clear = st.columns([3, 2, 1, 1])

    with col_upload:
        files = st.file_uploader(
            t("upload_placeholder"),
            accept_multiple_files=True,
            # Added "pdf" to the accepted types list
            type=["png", "jpg", "jpeg", "tiff", "bmp", "pdf"],
            key="file_uploader",
        )

    with col_clear:
        if st.button(t("clear_results"), type="secondary", use_container_width=True):
            fix_data_permissions()
            clear_db()
            # remove uploaded files AND directories
            for p in UPLOAD_DIR.iterdir():
                try:
                    if p.is_dir():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
                except Exception:
                    pass
            st.session_state.selected_image = 0
            st.success(t("new_session"))
            st.rerun()

    if files:
        for i, f in enumerate(files, 1):
            st.write(f"{i}. **{f.name}** ({f.size / 1024:.1f} KB)")

        _, col_btn, _ = st.columns([2, 1, 2])
        with col_btn:
            if st.button(t("upload_button"), use_container_width=True, type="primary"):
                queued = 0
                for f in files:
                    file_bytes = f.read()
                    
                    # Create a dedicated directory for this uploaded file based on its name
                    file_stem = Path(f.name).stem
                    file_dir = UPLOAD_DIR / file_stem
                    file_dir.mkdir(parents=True, exist_ok=True)
                    
                    if f.name.lower().endswith(".pdf"):
                        # Open PDF from bytes
                        pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
                        
                        # Iterate through pages and save as images
                        for page_num in range(len(pdf_doc)):
                            page = pdf_doc.load_page(page_num)
                            pix = page.get_pixmap(dpi=150)
                            
                            img_name = f"{file_stem}_page_{page_num + 1}.jpg"
                            img_path = file_dir / img_name
                            
                            # Save the image and add relative path to database
                            pix.save(str(img_path))
                            rel_path = f"{file_stem}/{img_name}"
                            add_job(rel_path)
                            queued += 1
                    else:
                        fp = file_dir / f.name
                        with open(fp, "wb") as out:
                            out.write(file_bytes)
                        
                        # Store relative path in database
                        rel_path = f"{file_stem}/{f.name}"
                        add_job(rel_path)
                        queued += 1
                        
                st.success(t("queued_success").format(count=queued))
                time.sleep(1)
                st.rerun()


def render_results_section() -> None:
    """Three-column results view with image, raw text, corrected/comparison."""
    st.markdown("---")
    st.markdown(
        f'<h2 style="color:#667eea;margin-bottom:1rem;">{t("results_header")}</h2>',
        unsafe_allow_html=True,
    )

    jobs = get_all_jobs()

    if not jobs:
        st.markdown(
            f'<div class="custom-card" style="text-align:center;padding:3rem;">'
            f'<div style="font-size:4rem;color:#adb5bd;">📭</div>'
            f'<h3 style="color:#6c757d;">{t("no_jobs")}</h3>'
            f'<p style="color:#adb5bd;">{t("upload_description")}</p></div>',
            unsafe_allow_html=True,
        )
        return

    render_statistics(jobs)

    completed = [j for j in jobs if j[2] == JobStatus.COMPLETED]
    pending = [j for j in jobs if j[2] in (JobStatus.PENDING, JobStatus.PROCESSING)]
    failed = [j for j in jobs if j[2].startswith(JobStatus.FAILED)]

    # ── Completed results ─────────────────────────────────────────
    if completed:
        st.markdown(
            f"<h3 style='margin-top:2rem;'>{t('current_session')}</h3>",
            unsafe_allow_html=True,
        )

        if "selected_image" not in st.session_state or st.session_state.selected_image >= len(completed):
            st.session_state.selected_image = 0

        left_col, mid_col, right_col = st.columns([0.8, 1.2, 1.2])

        # ── Left: image selector + preview ────────────────────────
        with left_col:
            names = [f"📄 {j[1]}" for j in completed]
            selected_tab = st.radio(
                "Select Image",
                options=names,
                index=st.session_state.selected_image,
                key="image_selector",
                label_visibility="collapsed",
            )
            idx = names.index(selected_tab)
            if idx != st.session_state.selected_image:
                st.session_state.selected_image = idx
                st.rerun()

            job = completed[idx]
            filename = job[1]
            image_path = UPLOAD_DIR / filename

            if image_path.exists():
                try:
                    img = Image.open(image_path)
                    max_w = 350
                    disp_w = min(img.width, max_w)
                    st.markdown('<div class="image-preview">', unsafe_allow_html=True)
                    st.image(img, width=disp_w, use_container_width=False)
                    st.markdown("</div>", unsafe_allow_html=True)

                    c1, c2 = st.columns(2)
                    c1.markdown(f"**{t('file')}:**<br>{filename}", unsafe_allow_html=True)
                    c2.markdown(f"**{t('created')}:**<br>{job[5]}", unsafe_allow_html=True)
                    st.markdown(
                        f"**{t('status')}:** <span class='status-completed'>"
                        f"{t('completed')}</span>",
                        unsafe_allow_html=True,
                    )
                except Exception as e:
                    st.error(f"Error loading image: {e}")
            else:
                st.warning(f"Image not found: {filename}")

        # ── Middle: Raw VLM output ────────────────────────────────
        with mid_col:
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#ff6b6b,#ee5a24);'
                f'color:white;padding:0.5rem 1rem;border-radius:20px;'
                f'display:inline-block;margin-bottom:1rem;font-weight:600;">'
                f'{t("unprocessed_text")}</div>',
                unsafe_allow_html=True,
            )

            job = completed[st.session_state.selected_image]
            raw_text = job[3] or ""
            corrected_text = job[4] or ""
            lang = st.session_state.get("language", "en")
            text_cls = "rtl" if lang == "ar" else "ltr"

            if raw_text:
                similarity = calculate_similarity(raw_text, corrected_text) if corrected_text else None
                sim_str = f" | Similarity: {similarity:.1f}%" if similarity else ""
                
                st.markdown(
                    f'<div style="background:#fff5f5; border:1px solid #feb2b2; '
                    f'padding:0.5rem 1rem; border-radius:10px; margin-bottom:1rem;">'
                    f'<div style="font-size:0.85rem; color:#718096;">'
                    f'Length: {len(raw_text)} chars{sim_str}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                
                with st.container(height=400):
                    st.markdown(raw_text)

                with st.expander("📊 Raw Text Analysis"):
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Characters", len(raw_text))
                    m2.metric("Words", len(raw_text.split()))
                    m3.metric("Lines", len(raw_text.splitlines()))
                    if similarity:
                        st.progress(similarity / 100, f"Similarity: {similarity:.1f}%")

                _, dl, _ = st.columns([1, 1, 1])
                with dl:
                    st.download_button(
                        t("download_raw"),
                        data=raw_text,
                        file_name=f"{Path(job[1]).stem}_raw.txt",
                        mime="text/plain",
                        key=f"dl_raw_{job[0]}",
                        use_container_width=True,
                    )
            else:
                st.warning("No raw text available.")

        # ── Right: Corrected + Comparison tabs ────────────────────
        with right_col:
            tab_corrected, tab_compare = st.tabs(
                [t("corrected"), t("comparison_view")]
            )

            # --- Corrected text ---
            with tab_corrected:
                st.markdown(
                    f'<div style="background:linear-gradient(135deg,#667eea,#764ba2);'
                    f'color:white;padding:0.5rem 1rem;border-radius:20px;'
                    f'display:inline-block;margin-bottom:1rem;font-weight:600;">'
                    f'{t("ai_powered")}</div>',
                    unsafe_allow_html=True,
                )

                if corrected_text:
                    st.markdown(
                        f'<div style="background:#f0fff4;border:1px solid #9ae6b4; '
                        f'padding:0.5rem 1rem; border-radius:10px; margin-bottom:1rem;">'
                        f'<div style="font-size:0.85rem;color:#718096;">'
                        f'Length: {len(corrected_text)} chars</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    
                    with st.container(height=400):
                        st.markdown(corrected_text)
                        
                    st.markdown("---")
                    _, dl, _ = st.columns([1, 1, 1])
                    with dl:
                        st.download_button(
                            t("download_text"),
                            data=corrected_text,
                            file_name=f"{Path(job[1]).stem}_corrected.txt",
                            mime="text/plain",
                            key=f"dl_corr_{job[0]}",
                            use_container_width=True,
                        )
                else:
                    st.warning(t("no_corrected"))

            # --- Comparison view ---
            with tab_compare:
                st.markdown(
                    '<div style="background:linear-gradient(135deg,#f6ad55,#ed8936);'
                    'color:white;padding:0.5rem 1rem;border-radius:20px;'
                    'display:inline-block;margin-bottom:1rem;font-weight:600;">'
                    '🔄 Change Analysis</div>',
                    unsafe_allow_html=True,
                )

                if raw_text and corrected_text:
                    sim = calculate_similarity(raw_text, corrected_text)

                    # Character-level diff
                    char_diff = list(difflib.ndiff(raw_text, corrected_text))
                    diff_html_parts = []
                    for ch in char_diff:
                        if ch.startswith("+ "):
                            diff_html_parts.append(
                                f'<span style="background:#c6f6d5;color:#22543d;'
                                f'padding:2px;border-radius:3px;">'
                                f'{html_lib.escape(ch[2:])}</span>'
                            )
                        elif ch.startswith("- "):
                            diff_html_parts.append(
                                f'<span style="background:#fed7d7;color:#742a2a;'
                                f'padding:2px;border-radius:3px;'
                                f'text-decoration:line-through;">'
                                f'{html_lib.escape(ch[2:])}</span>'
                            )
                        elif ch.startswith("  "):
                            diff_html_parts.append(html_lib.escape(ch[2:]))
                    diff_html = "".join(diff_html_parts)

                    changes_count = sum(
                        1 for d in char_diff if d.startswith("+ ") or d.startswith("- ")
                    )
                    change_ratio = abs(len(corrected_text) - len(raw_text)) / max(len(raw_text), 1)

                    mc1, mc2, mc3 = st.columns(3)
                    mc1.metric("Similarity", f"{sim:.1f}%")
                    mc2.metric("Changes", changes_count)
                    mc3.metric("Change Ratio", f"{change_ratio:.2%}")

                    bar_color = (
                        "green" if sim > 90 else "orange" if sim > 70 else "red"
                    )
                    st.markdown(
                        f'<div style="margin:1rem 0;">'
                        f'<div style="background:#e2e8f0;height:10px;border-radius:5px;">'
                        f'<div style="background:{bar_color};width:{sim}%;'
                        f'height:100%;border-radius:5px;"></div></div>'
                        f'<div style="font-size:0.85rem;color:#718096;'
                        f'text-align:center;margin-top:0.25rem;">Text Similarity</div></div>',
                        unsafe_allow_html=True,
                    )

                    st.markdown(
                        f'<div class="text-display {text_cls}" '
                        f'style="background:#f7fafc;border-color:#cbd5e0;'
                        f'font-family:monospace;font-size:0.9rem;">'
                        f'<div style="font-size:0.85rem;color:#718096;'
                        f'margin-bottom:0.4rem;">Character-level differences:</div>'
                        f'{diff_html}</div>',
                        unsafe_allow_html=True,
                    )

                    st.markdown(
                        '<div style="margin-top:0.5rem;font-size:0.85rem;color:#718096;">'
                        '<span style="background:#c6f6d5;padding:2px 5px;border-radius:3px;'
                        'margin-right:1rem;">Green: Inserted</span>'
                        '<span style="background:#fed7d7;padding:2px 5px;border-radius:3px;">'
                        'Red: Deleted</span></div>',
                        unsafe_allow_html=True,
                    )

                    # Word-level changes
                    rw = raw_text.split()
                    cw = corrected_text.split()
                    word_diffs = []
                    for i, (a, b) in enumerate(zip(rw, cw)):
                        if a != b:
                            word_diffs.append({"pos": i, "raw": a, "corrected": b})

                    if word_diffs:
                        with st.expander(f"📝 Word-level Changes ({len(word_diffs)})"):
                            for wd in word_diffs[:10]:
                                st.write(
                                    f"**{t('position')} {wd['pos']}:** "
                                    f"`{wd['raw']}` → `{wd['corrected']}`"
                                )
                            if len(word_diffs) > 10:
                                st.write(f"… and {len(word_diffs) - 10} more")

                    # Downloadable report
                    report = (
                        f"COMPARISON REPORT\n{'=' * 40}\n"
                        f"File: {job[1]}\nTimestamp: {job[5]}\n\n"
                        f"Similarity: {sim:.1f}%\n"
                        f"Raw Length: {len(raw_text)}\n"
                        f"Corrected Length: {len(corrected_text)}\n"
                        f"Changes: {changes_count}\n"
                        f"Change Ratio: {change_ratio:.2%}\n\n"
                        f"RAW TEXT\n{'-' * 40}\n{raw_text}\n\n"
                        f"CORRECTED TEXT\n{'-' * 40}\n{corrected_text}\n"
                    )
                    _, dl, _ = st.columns([1, 1, 1])
                    with dl:
                        st.download_button(
                            t("download_report"),
                            data=report,
                            file_name=f"{Path(job[1]).stem}_comparison.txt",
                            mime="text/plain",
                            key=f"dl_report_{job[0]}",
                            use_container_width=True,
                        )
                else:
                    st.warning("Both raw and corrected text are required for comparison.")

    # ── Pending / failed queue ────────────────────────────────────
    if pending or failed:
        with st.expander(f"🔍 {t('processing_queue')}", expanded=True):
            if pending:
                st.markdown(f"**{t('processing_queue')}:**")
                for j in pending:
                    status_cls = (
                        "status-processing"
                        if j[2] == JobStatus.PROCESSING
                        else "status-pending"
                    )
                    status_txt = (
                        t("processing")
                        if j[2] == JobStatus.PROCESSING
                        else t("pending")
                    )
                    st.markdown(
                        f'<div style="display:flex;align-items:center;margin-bottom:0.5rem;">'
                        f'<div style="flex:1;">📄 <strong>{j[1]}</strong></div>'
                        f'<span class="{status_cls}">{status_txt}</span></div>',
                        unsafe_allow_html=True,
                    )
            if failed:
                st.markdown(f"**{t('failed')}:**")
                for j in failed:
                    st.markdown(
                        f'<div style="display:flex;align-items:center;margin-bottom:0.5rem;">'
                        f'<div style="flex:1;">❌ <strong>{j[1]}</strong></div>'
                        f'<span class="status-failed">{t("failed")}</span></div>',
                        unsafe_allow_html=True,
                    )
    elif not completed:
        st.markdown(
            f'<div class="custom-card" style="text-align:center;padding:3rem;">'
            f'<div style="font-size:4rem;color:#17a2b8;">⏳</div>'
            f'<h3 style="color:#6c757d;">{t("no_completed")}</h3>'
            f'<p style="color:#adb5bd;">Processing in progress…</p></div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Application entry point."""
    st.set_page_config(
        page_title="Arabic Document Processor",
        page_icon="📝",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Session state defaults
    for key, default in [
        ("language", "en"),
        ("selected_image", 0),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # Initialize database once
    if "db_initialized" not in st.session_state:
        init_db()
        st.session_state.db_initialized = True

    # Sidebar: HF token
    render_hf_token_sidebar()

    # Token gate
    if not render_token_gate():
        st.stop()

    # Language selector
    render_language_selector()

    # Header
    st.markdown(
        f'<div class="header-container">'
        f'<h1 class="header-title">{t("title")}</h1>'
        f'<p class="header-subtitle">{t("subtitle")}</p></div>',
        unsafe_allow_html=True,
    )

    # Start worker
    start_worker()

    # Render single-page layout
    render_upload_section()
    render_results_section()


if __name__ == "__main__":
    main()