import streamlit as st
import pandas as pd
import requests
import base64
import os
import threading
import time
from database import init_db, add_job, get_next_job, update_job, get_all_jobs

# --- Configuration ---
VISION_URL = os.getenv("VISION_URL")
TEXT_URL = os.getenv("TEXT_URL")
UPLOAD_DIR = os.getenv("UPLOAD_DIR")
os.makedirs(UPLOAD_DIR, exist_ok=True)
init_db()

# --- Background Worker ---
def worker_loop():
    while True:
        job = get_next_job()
        if not job:
            time.sleep(2)
            continue
        
        job_id, filename = job
        update_job(job_id, "PROCESSING")
        
        try:
            # 1. Vision Processing
            with open(os.path.join(UPLOAD_DIR, filename), "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
            
            vision_resp = requests.post(VISION_URL, json={
                "model": "vision-model",
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": "Transcribe the Arabic text in this image."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]}]
            }).json()
            raw_text = vision_resp['choices'][0]['message']['content']

            # 2. Text Correction
            text_resp = requests.post(TEXT_URL, json={
                "model": "text-model",
                "messages": [{"role": "user", "content": f"Fix OCR errors in this Arabic text: {raw_text}"}]
            }).json()
            corrected_text = text_resp['choices'][0]['message']['content']

            update_job(job_id, "COMPLETED", raw_text, corrected_text)
        except Exception as e:
            update_job(job_id, f"FAILED: {str(e)}")

# Start worker once
if "worker_started" not in st.session_state:
    threading.Thread(target=worker_loop, daemon=True).start()
    st.session_state.worker_started = True

# --- Streamlit UI ---
st.set_page_config(page_title="Arabic OCR MVP", layout="wide")
tab1, tab2 = st.tabs(["Batch Ingestion", "Results & History"])

with tab1:
    st.header("Upload Documents")
    files = st.file_uploader("Drag images here", accept_multiple_files=True)
    if st.button("Start Processing"):
        for f in files:
            with open(os.path.join(UPLOAD_DIR, f.name), "wb") as save_file:
                save_file.write(f.read())
            add_job(f.name)
        st.success(f"Queued {len(files)} files.")

with tab2:
    st.header("Processing History")
    jobs = get_all_jobs()
    if jobs:
        df = pd.DataFrame(jobs, columns=["ID", "Filename", "Status", "Raw Text", "Corrected Text", "Date"])
        st.table(df)