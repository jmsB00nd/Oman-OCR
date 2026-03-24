"""Streamlit Frontend for Arabic Document Processor."""

import difflib
import html as html_lib
import os
from io import BytesIO
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8000")

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
        "queued_success": "✅ Queued files for processing.",
        "position": "Position",
    },
    "ar": {
        "title": "نظام التعرف الضوئي على النصوص العربية",
        "subtitle": "استخراج وتصحيح النصوص العربية من صور المستندات",
        "upload_header": "تحميل المستندات",
        "upload_description": "قم بتحميل الصور.",
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
        "queued_success": "✅ تمت إضافة الملفات للمعالجة.",
        "position": "الموضع",
    },
}

def t(key: str) -> str:
    lang = st.session_state.get("language", "en")
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)


CUSTOM_CSS = """
<style>
.stApp { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
.header-container { text-align: center; padding: 1.5rem 0 1rem; }
.header-title { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.4rem; font-weight: 800; margin-bottom: 0.25rem; }
.header-subtitle { color: #718096; font-size: 1.05rem; }
.metric-card { background: white; border-radius: 12px; padding: 1.2rem 1rem; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }
.metric-value { font-size: 1.8rem; font-weight: 700; color: #2d3748; }
.metric-label { font-size: 0.85rem; color: #718096; margin-top: 0.25rem; }
.custom-card { background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 12px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }
.text-display { padding: 1rem; border-radius: 10px; border: 1px solid #e2e8f0; min-height: 180px; max-height: 400px; overflow-y: auto; line-height: 1.8; font-size: 1rem; }
.text-display.rtl { direction: rtl; text-align: right; }
.text-display.ltr { direction: ltr; text-align: left; }
.image-preview { border-radius: 10px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.status-completed { background: #c6f6d5; color: #22543d; padding: 0.2rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 600; }
.status-processing { background: #bee3f8; color: #2a4365; padding: 0.2rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 600; }
.status-pending { background: #fefcbf; color: #744210; padding: 0.2rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 600; }
.status-failed { background: #fed7d7; color: #742a2a; padding: 0.2rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 600; }
</style>
"""

def calculate_similarity(text1: str, text2: str) -> float:
    return difflib.SequenceMatcher(None, text1, text2).ratio() * 100

def render_language_selector() -> None:
    _, _, col_lang = st.columns([8, 1, 1])
    with col_lang:
        selected = st.selectbox(
            "",
            options=list(LANGUAGES.keys()),
            format_func=lambda x: LANGUAGES[x],
            index=list(LANGUAGES.keys()).index(st.session_state.get("language", "en")),
            label_visibility="collapsed",
        )
    if selected != st.session_state.get("language", "en"):
        st.session_state.language = selected
        st.rerun()

def render_statistics(jobs: list) -> None:
    completed = [j for j in jobs if j["status"] == "COMPLETED"]
    pending = [j for j in jobs if j["status"] in ("PENDING", "PROCESSING")]
    failed = [j for j in jobs if j["status"].startswith("FAILED")]
    rate = (len(completed) / len(jobs) * 100) if jobs else 0

    st.markdown(f"<h3 style='margin-bottom:1.5rem;'>{t('stats_header')}</h3>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    for col, val, label in [(c1, len(pending), t("pending")), (c2, len(completed), t("completed")), (c3, len(failed), t("failed")), (c4, len(jobs), t("all_files"))]:
        col.markdown(f'<div class="metric-card"><div class="metric-value">{val}</div><div class="metric-label">{label}</div></div>', unsafe_allow_html=True)
    c5.markdown(f'<div class="metric-card"><div class="metric-value">{rate:.1f}%</div><div class="metric-label">{t("success_rate")}</div></div>', unsafe_allow_html=True)

def render_upload_section() -> None:
    st.markdown(
        f'<div class="custom-card" style="margin-bottom:2rem;">'
        f'<h2 style="color:#667eea;margin-bottom:0.5rem;">{t("upload_header")}</h2>'
        f'<p style="color:#6c757d;">{t("upload_description")}</p>'
        f'<p style="color:#adb5bd;font-size:0.9rem;">{t("upload_instructions")}</p></div>',
        unsafe_allow_html=True,
    )

    col_upload, _, _, col_clear = st.columns([3, 2, 1, 1])
    with col_upload:
        files = st.file_uploader(t("upload_placeholder"), accept_multiple_files=True, type=["png", "jpg", "jpeg", "tiff", "bmp", "pdf"])

    with col_clear:
        if st.button(t("clear_results"), type="secondary", use_container_width=True):
            requests.post(f"{API_URL}/clear")
            st.session_state.selected_image = 0
            st.success(t("new_session"))
            st.rerun()

    if files:
        for i, f in enumerate(files, 1):
            st.write(f"{i}. **{f.name}** ({f.size / 1024:.1f} KB)")
        _, col_btn, _ = st.columns([2, 1, 2])
        with col_btn:
            if st.button(t("upload_button"), use_container_width=True, type="primary"):
                # Send files to FastAPI
                files_payload = [("files", (f.name, f.getvalue(), f.type)) for f in files]
                response = requests.post(f"{API_URL}/upload", files=files_payload)
                if response.status_code == 200:
                    st.success(t("queued_success"))
                    st.rerun()

def render_results_section() -> None:
    st.markdown("---")
    st.markdown(f'<h2 style="color:#667eea;margin-bottom:1rem;">{t("results_header")}</h2>', unsafe_allow_html=True)

    try:
        jobs = requests.get(f"{API_URL}/jobs").json()
    except Exception:
        st.error("Cannot connect to backend API.")
        return

    if not jobs:
        st.markdown(f'<div class="custom-card" style="text-align:center;padding:3rem;"><div style="font-size:4rem;color:#adb5bd;">📭</div><h3 style="color:#6c757d;">{t("no_jobs")}</h3><p style="color:#adb5bd;">{t("upload_description")}</p></div>', unsafe_allow_html=True)
        return

    render_statistics(jobs)
    completed = [j for j in jobs if j["status"] == "COMPLETED"]
    pending = [j for j in jobs if j["status"] in ("PENDING", "PROCESSING")]
    failed = [j for j in jobs if j["status"].startswith("FAILED")]

    if completed:
        st.markdown(f"<h3 style='margin-top:2rem;'>{t('current_session')}</h3>", unsafe_allow_html=True)
        if "selected_image" not in st.session_state or st.session_state.selected_image >= len(completed):
            st.session_state.selected_image = 0

        left_col, mid_col, right_col = st.columns([0.8, 1.2, 1.2])

        with left_col:
            names = [f"📄 {j['filename']}" for j in completed]
            selected_tab = st.radio("Select Image", options=names, index=st.session_state.selected_image, label_visibility="collapsed")
            idx = names.index(selected_tab)
            if idx != st.session_state.selected_image:
                st.session_state.selected_image = idx
                st.rerun()

            job = completed[idx]
            
            # Fetch image directly from FastAPI URL
            img_url = f"{API_URL}/images/{job['filename']}"
            try:
                img_response = requests.get(img_url)
                img = Image.open(BytesIO(img_response.content))
                st.markdown('<div class="image-preview">', unsafe_allow_html=True)
                st.image(img, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            except Exception:
                st.warning("Image preview not available.")

            c1, c2 = st.columns(2)
            c1.markdown(f"**{t('file')}:**<br>{job['filename']}", unsafe_allow_html=True)
            c2.markdown(f"**{t('created')}:**<br>{job['created_at']}", unsafe_allow_html=True)

        with mid_col:
            st.markdown(f'<div style="background:linear-gradient(135deg,#ff6b6b,#ee5a24);color:white;padding:0.5rem 1rem;border-radius:20px;display:inline-block;margin-bottom:1rem;font-weight:600;">{t("unprocessed_text")}</div>', unsafe_allow_html=True)
            raw_text = job["raw_text"] or ""
            corrected_text = job["corrected_text"] or ""
            
            if raw_text:
                with st.container(height=400): st.markdown(raw_text)
                st.download_button(t("download_raw"), data=raw_text, file_name=f"{Path(job['filename']).stem}_raw.txt", key=f"dl_raw_{job['id']}", use_container_width=True)
            else:
                st.warning("No raw text available.")

        with right_col:
            tab_corrected, tab_compare = st.tabs([t("corrected"), t("comparison_view")])
            with tab_corrected:
                st.markdown(f'<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:0.5rem 1rem;border-radius:20px;display:inline-block;margin-bottom:1rem;font-weight:600;">{t("ai_powered")}</div>', unsafe_allow_html=True)
                if corrected_text:
                    with st.container(height=400): st.markdown(corrected_text)
                    st.download_button(t("download_text"), data=corrected_text, file_name=f"{Path(job['filename']).stem}_corrected.txt", key=f"dl_corr_{job['id']}", use_container_width=True)
                else:
                    st.warning(t("no_corrected"))
            with tab_compare:
                if raw_text and corrected_text:
                    sim = calculate_similarity(raw_text, corrected_text)
                    st.metric("Similarity", f"{sim:.1f}%")
                else:
                    st.warning("Comparison requires both texts.")

    if pending or failed:
        with st.expander(f"🔍 {t('processing_queue')}", expanded=True):
            if pending:
                st.markdown(f"**{t('processing_queue')}:**")
                for j in pending: st.markdown(f"📄 {j['filename']} - {j['status']}")
            if failed:
                st.markdown(f"**{t('failed')}:**")
                for j in failed: st.markdown(f"❌ {j['filename']} - FAILED")

def main() -> None:
    st.set_page_config(page_title="Arabic Document Processor", page_icon="📝", layout="wide", initial_sidebar_state="collapsed")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    if "language" not in st.session_state: st.session_state["language"] = "en"
    if "selected_image" not in st.session_state: st.session_state["selected_image"] = 0

    render_language_selector()
    st.markdown(f'<div class="header-container"><h1 class="header-title">{t("title")}</h1><p class="header-subtitle">{t("subtitle")}</p></div>', unsafe_allow_html=True)
    
    # Force UI to fetch API updates frequently if processing
    import time
    render_upload_section()
    render_results_section()
    time.sleep(2)
    st.rerun()

if __name__ == "__main__":
    main()