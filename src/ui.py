"""Streamlit Frontend for Arabic Document Processor."""

import difflib
import os
import time
from io import BytesIO
from pathlib import Path
import html as html_lib
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
        "subtitle": "Extract and structure Arabic text from document images",
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
        "unprocessed_text": "⚠️ Raw OCR Output",
        "ai_powered": "✨ Structured Data",
        "corrected": "Structured Text",
        "comparison_view": "🔍 Comparison",
        "file": "File",
        "created": "Created",
        "status": "Status",
        "download_raw": "📥 Download Raw",
        "download_excel": "📥 Download Excel",
        "download_text": "📥 Download Structured",
        "download_report": "📥 Download Report",
        "no_corrected": "No structured text available.",
        "clear_results": "🗑️ Clear All",
        "new_session": "Session cleared!",
        "queued_success": "✅ Queued files for processing.",
        "position": "Position",
    },
    "ar": {
        "title": "نظام التعرف الضوئي على النصوص العربية",
        "subtitle": "استخراج وهيكلة النصوص العربية من صور المستندات",
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
        "unprocessed_text": "⚠️ نص التعرف الضوئي الخام",
        "ai_powered": "✨ بيانات منظمة",
        "corrected": "النص المنظم",
        "comparison_view": "🔍 المقارنة",
        "file": "الملف",
        "created": "تاريخ الإنشاء",
        "status": "الحالة",
        "download_raw": "📥 تحميل الخام",
        "download_excel": "📥 تحميل إكسيل",
        "download_text": "📥 تحميل المنظم",
        "download_report": "📥 تحميل التقرير",
        "no_corrected": "لا توجد بيانات منظمة.",
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
.image-preview { border-radius: 10px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
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
                files_payload = [("files", (f.name, f.getvalue(), f.type)) for f in files]
                response = requests.post(f"{API_URL}/upload", files=files_payload)
                if response.status_code == 200:
                    st.success(t("queued_success"))
                    st.rerun()

def render_results_section(jobs: list) -> None:
    st.markdown("---")
    st.markdown(f'<h2 style="color:#667eea;margin-bottom:1rem;">{t("results_header")}</h2>', unsafe_allow_html=True)

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
            img_url = f"{API_URL}/images/{job['filename']}"
            try:
                img_response = requests.get(img_url)
                img = Image.open(BytesIO(img_response.content))
                st.markdown('<div class="image-preview">', unsafe_allow_html=True)
                st.image(img, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            except Exception:
                st.warning("Image preview not available.")

        with mid_col:
            st.markdown(f'<div style="background:linear-gradient(135deg,#ff6b6b,#ee5a24);color:white;padding:0.5rem 1rem;border-radius:20px;display:inline-block;margin-bottom:1rem;font-weight:600;">{t("unprocessed_text")}</div>', unsafe_allow_html=True)
            raw_text = job["raw_text"] or ""
            if raw_text:
                with st.expander("📊 Raw Text Analysis"):
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Characters", len(raw_text))
                    m2.metric("Words", len(raw_text.split()))
                    m3.metric("Lines", len(raw_text.splitlines()))
                    
                with st.container(height=400): st.markdown(raw_text, unsafe_allow_html=True)
                
                # Existing Raw Download Button
                st.download_button(
                    t("download_raw"), 
                    data=raw_text, 
                    file_name=f"{Path(job['filename']).stem}_raw.txt", 
                    key=f"dl_raw_{job['id']}", 
                    use_container_width=True
                )
                
                excel_rel_path = Path(job['filename']).with_suffix('.xlsx').as_posix()
                excel_url = f"{API_URL}/images/{excel_rel_path}"
                
                try:
                    excel_response = requests.get(excel_url)
                    if excel_response.status_code == 200:
                        st.download_button(
                            label=t("download_excel"),
                            data=excel_response.content,
                            file_name=f"{Path(job['filename']).stem}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_excel_{job['id']}",
                            use_container_width=True
                        )
                except Exception:
                    pass

            else:
                st.warning("No raw text available.")

        with right_col:
            tab_corrected, tab_compare = st.tabs([t("corrected"), t("comparison_view")])
            corrected_text = job["corrected_text"] or ""
            with tab_corrected:
                st.markdown(f'<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:0.5rem 1rem;border-radius:20px;display:inline-block;margin-bottom:1rem;font-weight:600;">{t("ai_powered")}</div>', unsafe_allow_html=True)
                if corrected_text:
                    with st.container(height=400): st.markdown(corrected_text, unsafe_allow_html=True)
                    st.download_button(t("download_text"), data=corrected_text, file_name=f"{Path(job['filename']).stem}_structured.txt", key=f"dl_corr_{job['id']}", use_container_width=True)
                else:
                    st.warning(t("no_corrected"))
            with tab_compare:
                if raw_text and corrected_text:
                    sim = calculate_similarity(raw_text, corrected_text)
                    
                    # Character-level diff
                    char_diff = list(difflib.ndiff(raw_text, corrected_text))
                    diff_html_parts = []
                    for ch in char_diff:
                        if ch.startswith("+ "):
                            diff_html_parts.append(f'<span style="background:#c6f6d5;color:#22543d;padding:2px;border-radius:3px;">{html_lib.escape(ch[2:])}</span>')
                        elif ch.startswith("- "):
                            diff_html_parts.append(f'<span style="background:#fed7d7;color:#742a2a;padding:2px;border-radius:3px;text-decoration:line-through;">{html_lib.escape(ch[2:])}</span>')
                        elif ch.startswith("  "):
                            diff_html_parts.append(html_lib.escape(ch[2:]))
                    diff_html = "".join(diff_html_parts)

                    changes_count = sum(1 for d in char_diff if d.startswith("+ ") or d.startswith("- "))
                    change_ratio = abs(len(corrected_text) - len(raw_text)) / max(len(raw_text), 1)

                    mc1, mc2, mc3 = st.columns(3)
                    mc1.metric("Similarity", f"{sim:.1f}%")
                    mc2.metric("Changes", changes_count)
                    mc3.metric("Change Ratio", f"{change_ratio:.2%}")

                    bar_color = "green" if sim > 90 else "orange" if sim > 70 else "red"
                    st.markdown(
                        f'<div style="margin:1rem 0;">'
                        f'<div style="background:#e2e8f0;height:10px;border-radius:5px;">'
                        f'<div style="background:{bar_color};width:{sim}%;height:100%;border-radius:5px;"></div></div>'
                        f'<div style="font-size:0.85rem;color:#718096;text-align:center;margin-top:0.25rem;">Text Similarity</div></div>',
                        unsafe_allow_html=True,
                    )

                    lang = st.session_state.get("language", "en")
                    text_cls = "rtl" if lang == "ar" else "ltr"
                    
                    st.markdown(
                        f'<div class="{text_cls}" style="background:#f7fafc;border:1px solid #cbd5e0;border-radius:10px;padding:1rem;font-family:monospace;font-size:0.9rem;max-height:300px;overflow-y:auto;">'
                        f'<div style="font-size:0.85rem;color:#718096;margin-bottom:0.4rem;">Character-level differences:</div>'
                        f'{diff_html}</div>',
                        unsafe_allow_html=True,
                    )

                    st.markdown(
                        '<div style="margin-top:0.5rem;font-size:0.85rem;color:#718096;">'
                        '<span style="background:#c6f6d5;padding:2px 5px;border-radius:3px;margin-right:1rem;">Green: Inserted</span>'
                        '<span style="background:#fed7d7;padding:2px 5px;border-radius:3px;">Red: Deleted</span></div>',
                        unsafe_allow_html=True,
                    )

                    # Word-level changes
                    rw = raw_text.split()
                    cw = corrected_text.split()
                    word_diffs = [{"pos": i, "raw": a, "corrected": b} for i, (a, b) in enumerate(zip(rw, cw)) if a != b]

                    if word_diffs:
                        with st.expander(f"📝 Word-level Changes ({len(word_diffs)})"):
                            for wd in word_diffs[:10]:
                                st.write(f"**{t('position')} {wd['pos']}:** `{wd['raw']}` → `{wd['corrected']}`")
                            if len(word_diffs) > 10:
                                st.write(f"… and {len(word_diffs) - 10} more")
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
    
    render_upload_section()
    
    # Fetch jobs once to share between logic and UI
    try:
        jobs = requests.get(f"{API_URL}/jobs").json()
    except Exception:
        st.error("Cannot connect to backend API.")
        jobs = []

    render_results_section(jobs)

    active_jobs = [j for j in jobs if j["status"] in ("PENDING", "PROCESSING")]
    if active_jobs:
        time.sleep(3) 
        st.rerun()

if __name__ == "__main__":
    main()