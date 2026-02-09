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
from PIL import Image

from database import (
    JobStatus,
    add_job,
    get_all_jobs,
    get_job_stats,
    get_next_job,
    init_db,
    update_job,
    delete_all_jobs,  # We need this function
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


# Language translations
TRANSLATIONS = {
    "en": {
        "title": "Arabic OCR System",
        "subtitle": "Extract and correct Arabic text from document images.",
        "upload_tab": "📤 Upload & Results",
        "upload_header": "Upload Documents",
        "upload_description": "Upload images containing Arabic text for OCR processing.",
        "upload_placeholder": "Drag and drop images here",
        "upload_button": "Start Processing",
        "queued_success": "Queued {count} file(s) for processing. Results will appear here when ready.",
        "results_header": "Processing Results",
        "refresh_button": "Refresh",
        "clear_results": "Clear All & Start New",
        "clear_confirm": "Clear all previous results and start fresh?",
        "no_jobs": "No jobs in the queue. Upload some images to get started.",
        "no_completed": "No completed jobs to display. Upload and process some images first.",
        "extracted_text": "Extracted Text",
        "download_text": "Download Text",
        "images": "Images",
        "status": "Status",
        "pending": "Pending",
        "processing": "Processing",
        "completed": "Completed",
        "failed": "Failed",
        "file": "File",
        "corrected": "Corrected Text",
        "created": "Created At",
        "language_select": "Select Language",
        "no_corrected": "No corrected text available for this image.",
        "all_files": "All Files",
        "processing_queue": "Processing Queue",
        "view_results": "View Results",
        "current_session": "Current Session Results",
        "new_session": "New Session"
    },
    "ar": {
        "title": "OCR للغة العربية",
        "subtitle": "استخراج وتصحيح النص العربي من صور المستندات.",
        "upload_tab": "📤 الرفع والنتائج",
        "upload_header": "رفع المستندات",
        "upload_description": "ارفع صور تحتوي على نص عربي للمعالجة بواسطة OCR.",
        "upload_placeholder": "اسحب وأفلت الصور هنا",
        "upload_button": "بدء",
        "queued_success": "تمت إضافة {count} ملف(ملفات) إلى قائمة الانتظار للمعالجة. ستظهر النتائج هنا عندما تكون جاهزة.",
        "results_header": "نتائج",
        "refresh_button": "تحديث",
        "clear_results": "مسح الكل وبدء جديد",
        "clear_confirm": "مسح كل النتائج السابقة وبدء جلسة جديدة؟",
        "no_jobs": "لا توجد مهام في قائمة الانتظار. ارفع بعض الصور للبدء.",
        "no_completed": "لا توجد مهام مكتملة للعرض. ارفع ومعالج بعض الصور أولاً.",
        "extracted_text": "النص المستخرج",
        "download_text": "تحميل النص",
        "images": "الصور",
        "status": "الحالة",
        "pending": "قيد الانتظار",
        "processing": "قيد المعالجة",
        "completed": "مكتمل",
        "failed": "فشل",
        "file": "الملف",
        "corrected": "النص المصحح",
        "created": "تاريخ الإنشاء",
        "language_select": "اختر اللغة",
        "no_corrected": "لا يوجد نص مصحح متاح لهذه الصورة.",
        "all_files": "جميع الملفات",
        "processing_queue": "قائمة الانتظار",
        "view_results": "عرض النتائج",
        "current_session": "نتائج الجلسة الحالية",
        "new_session": "جلسة جديدة"
    }
}


def get_text(key: str) -> str:
    """Get translated text based on current language."""
    lang = st.session_state.get("language", "en")
    return TRANSLATIONS[lang].get(key, key)


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

def render_language_selector() -> None:
    """Render language selector as a small icon in top right."""
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col5:
        current_lang = st.session_state.get("language", "en")
        
        # Simple toggle - just show flag/icon, text appears on hover
        st.markdown("""
        <style>
        .lang-toggle-btn {
            min-width: 50px !important;
            width: 50px !important;
            padding: 0.25rem !important;
            font-size: 1.2rem !important;
        }
        .lang-toggle-btn:hover::after {
            content: " Switch";
            font-size: 0.8rem;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Show only flag/emoji in button
        if current_lang == "en":
            if st.button("🇺🇸", key="lang_toggle", help="Switch to Arabic / التبديل إلى العربية"):
                st.session_state.language = "ar"
                st.rerun()
        else:
            if st.button("🇸🇦", key="lang_toggle", help="Switch to English / التبديل إلى الإنجليزية"):
                st.session_state.language = "en"
                st.rerun()

def clear_previous_data() -> bool:
    """Clear all previous data from database and files."""
    try:
        # Get all jobs first to know what files to delete
        jobs = get_all_jobs()
        
        # Delete uploaded image files and generated text files
        for job in jobs:
            filename = job[1]
            image_path = UPLOAD_DIR / filename
            md_path = image_path.with_suffix(".md")
            
            # Delete image file if it exists
            if image_path.exists():
                try:
                    image_path.unlink()
                    logger.info(f"Deleted image file: {image_path}")
                except Exception as e:
                    logger.error(f"Failed to delete image file {image_path}: {e}")
            
            # Delete markdown file if it exists
            if md_path.exists():
                try:
                    md_path.unlink()
                    logger.info(f"Deleted text file: {md_path}")
                except Exception as e:
                    logger.error(f"Failed to delete text file {md_path}: {e}")
        
        # Clear all jobs from database
        delete_all_jobs()
        
        # Reset session state
        if "selected_image" in st.session_state:
            st.session_state.selected_image = 0
        
        logger.info("All previous data cleared")
        return True
    except Exception as e:
        logger.error(f"Error clearing previous data: {e}")
        return False


def render_upload_and_results() -> None:
    """Render the upload and results in a single tab."""
    # Add clear results button at the top
    st.header(get_text("upload_header"))
    
    # Check if we should clear previous data
    if "clear_data_on_upload" not in st.session_state:
        st.session_state.clear_data_on_upload = False
    
    if st.session_state.clear_data_on_upload:
        if clear_previous_data():
            st.success(get_text("new_session"))
            st.session_state.clear_data_on_upload = False
            st.rerun()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(get_text("upload_description"))
    with col2:
        if st.button(get_text("clear_results"), type="secondary", use_container_width=True):
            st.session_state.clear_data_on_upload = True
            st.rerun()

    files = st.file_uploader(
        get_text("upload_placeholder"),
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg", "tiff", "bmp"]
    )

    if st.button(get_text("upload_button"), type="primary", disabled=not files):
        # Clear previous data if this is the first upload of a new session
        if "first_upload" not in st.session_state:
            clear_previous_data()
            st.session_state.first_upload = False
        
        queued_count = 0
        for file in files:
            file_path = UPLOAD_DIR / file.name
            with open(file_path, "wb") as f:
                f.write(file.read())
            add_job(file.name)
            queued_count += 1

        st.success(get_text("queued_success").format(count=queued_count))
        st.rerun()
    
    st.markdown("---")
    
    # Results section - only show current session results
    st.header(get_text("results_header"))
    
    # Get all jobs (should only be from current session if we cleared properly)
    jobs = get_all_jobs()
    
    if not jobs:
        st.info(get_text("no_jobs"))
        return
    
    # Filter jobs that were created in this session
    # We'll show all jobs since we cleared previous ones
    completed_jobs = [job for job in jobs if job[2] == JobStatus.COMPLETED]
    pending_jobs = [job for job in jobs if job[2] in [JobStatus.PENDING, JobStatus.PROCESSING]]
    failed_jobs = [job for job in jobs if job[2].startswith(JobStatus.FAILED)]
    
    # Display statistics for current session only
    if jobs:
        cols = st.columns(4)
        cols[0].metric(get_text("pending"), len(pending_jobs))
        cols[1].metric(get_text("completed"), len(completed_jobs))
        cols[2].metric(get_text("failed"), len(failed_jobs))
        cols[3].metric(get_text("all_files"), len(jobs))
    
    # Refresh button
    if st.button(get_text("refresh_button")):
        st.rerun()
    
    # Check if there are completed jobs to show results
    if completed_jobs:
        st.subheader(get_text("current_session"))
        
        # Auto-select the first completed image if none selected
        if "selected_image" not in st.session_state or st.session_state.selected_image >= len(completed_jobs):
            st.session_state.selected_image = 0
        
        # Create two main columns: left for images, right for text
        left_col, right_col = st.columns([1, 1])
        
        with left_col:
            # Create tabs for each completed image in current session
            image_tabs = st.tabs([f"{job[1]}" for job in completed_jobs])
            
            for idx, (tab, job) in enumerate(zip(image_tabs, completed_jobs)):
                with tab:
                    filename = job[1]
                    image_path = UPLOAD_DIR / filename
                    
                    if image_path.exists():
                        try:
                            # Display image with smaller size
                            image = Image.open(image_path)
                            
                            # Calculate display size (max width 350px, maintain aspect ratio)
                            max_width = 350
                            if image.width > max_width:
                                ratio = max_width / image.width
                                display_width = max_width
                                display_height = int(image.height * ratio)
                            else:
                                display_width = image.width
                                display_height = image.height
                            
                            # Display image without caption
                            st.image(
                                image, 
                                width=display_width,
                                use_container_width=False
                            )
                            
                            # When this tab is active, update the selected image index
                            if tab._active:  # Check if this tab is active
                                st.session_state.selected_image = idx
                            
                            # Show file info below image
                            st.caption(f"{filename}")
                            st.caption(f"{get_text('created')}: {job[5]}")
                            st.caption(f"{get_text('status')}: {get_text('completed')}")
                            
                        except Exception as e:
                            st.error(f"Error loading image: {str(e)}")
                    else:
                        st.warning(f"Image file not found: {filename}")
        
        with right_col:
            st.subheader(get_text("extracted_text"))
            
            # Display text for the selected image
            if st.session_state.selected_image < len(completed_jobs):
                job = completed_jobs[st.session_state.selected_image]
                corrected_text = job[4]  # Corrected Text is at index 4
                
                if corrected_text:
                    # Get current language for text direction
                    lang = st.session_state.get("language", "en")
                    
                    if lang == "ar":
                        # Arabic text with RTL styling
                        st.markdown(
                            f"""
                            <div dir="rtl" style="text-align: right; font-family: 'Arial', sans-serif; 
                            font-size: 16px; line-height: 1.8; padding: 20px; border: 1px solid #ddd; 
                            border-radius: 10px; background-color: #f9f9f9; min-height: 400px; 
                            max-height: 500px; overflow-y: auto;">
                            {corrected_text}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    else:
                        # English or other LTR text
                        st.markdown(
                            f"""
                            <div dir="ltr" style="text-align: left; font-family: 'Arial', sans-serif; 
                            font-size: 16px; line-height: 1.6; padding: 20px; border: 1px solid #ddd; 
                            border-radius: 10px; background-color: #f9f9f9; min-height: 400px;
                            max-height: 500px; overflow-y: auto;">
                            {corrected_text}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    
                    # Add download button for the text
                    st.download_button(
                        label=get_text("download_text"),
                        data=corrected_text,
                        file_name=f"{job[1].split('.')[0]}_extracted.txt",
                        mime="text/plain",
                        key=f"download_{job[0]}"
                    )
                else:
                    st.warning(get_text("no_corrected"))
        
        # Show pending/processing jobs in an expander
        if pending_jobs or failed_jobs:
            with st.expander(get_text("processing_queue")):
                # Show pending/processing jobs
                if pending_jobs:
                    st.write(f"**{get_text('pending')} / {get_text('processing')}:**")
                    for job in pending_jobs:
                        st.write(f"📄 {job[1]} - {get_text('status')}: {get_text(job[2].lower())}")
                
                # Show failed jobs
                if failed_jobs:
                    st.write(f"**{get_text('failed')}:**")
                    for job in failed_jobs:
                        st.write(f"❌ {job[1]} - {get_text('status')}: {get_text('failed')}")
    else:
        # Show only processing queue if no completed jobs yet
        st.info(get_text("no_completed"))
        
        if pending_jobs or failed_jobs:
            st.subheader(get_text("processing_queue"))
            
            # Show pending/processing jobs
            if pending_jobs:
                st.write(f"**{get_text('pending')} / {get_text('processing')}:**")
                for job in pending_jobs:
                    st.write(f"📄 {job[1]} - {get_text('status')}: {get_text(job[2].lower())}")
            
            # Show failed jobs
            if failed_jobs:
                st.write(f"**{get_text('failed')}:**")
                for job in failed_jobs:
                    st.write(f"❌ {job[1]} - {get_text('status')}: {get_text('failed')}")


def main() -> None:
    """Main application entry point."""
    st.set_page_config(
        page_title="Arabic OCR System",
        page_icon="📝",
        layout="wide"
    )

    # Initialize session state
    if "language" not in st.session_state:
        st.session_state.language = "en"
    
    if "selected_image" not in st.session_state:
        st.session_state.selected_image = 0
    
    if "first_upload" not in st.session_state:
        st.session_state.first_upload = True
    
    if "clear_data_on_upload" not in st.session_state:
        st.session_state.clear_data_on_upload = False

    # Create header row with title and language selector
    header_col1, header_col2 = st.columns([4, 1])
    
    with header_col1:
        # Display title and subtitle based on selected language
        st.title(get_text("title"))
        st.markdown(get_text("subtitle"))
    
    with header_col2:
        # Render language selector in top right
        render_language_selector()

    # Start background worker
    start_worker()

    # Single tab for everything
    render_upload_and_results()


if __name__ == "__main__":
    main()