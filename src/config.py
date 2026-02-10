
import streamlit as st
from pathlib import Path
import os

VISION_URL = os.getenv("VISION_URL", "http://localhost:8000/v1/chat/completions")
TEXT_URL = os.getenv("TEXT_URL", "http://localhost:8001/v1/chat/completions")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))
WORKER_POLL_INTERVAL = 2  # seconds

# Language translations
TRANSLATIONS = {
    "en": {
        "title": "✨ Arabic OCR System",
        "subtitle": "Extract and correct Arabic text from document images with AI-powered precision",
        "main upload": "",
        "upload_tab": "📤 Upload & Process",
        "upload_header": "Upload Documents",
        "upload_description": "Upload images containing Arabic text for OCR processing.",
        "upload_placeholder": "📁 Drag and drop images here or click to browse",
        "upload_button": "🚀 Start Processing",
        "queued_success": "✅ Successfully queued {count} file(s) for processing",
        "results_header": "Processing Results",
        "refresh_button": "🔄 Refresh Status",
        "clear_results": "🗑️ Clear All & Start New Session",
        "clear_confirm": "Are you sure you want to clear all previous results and start fresh?",
        "no_jobs": "No jobs in the queue. Upload some images to get started.",
        "no_completed": "⏳ No completed jobs yet. Your results will appear here shortly.",
        "extracted_text": "Extracted & Corrected Text",
        "download_text": "⬇️ Download Text",
        "images": "Images",
        "status": "📊 Status",
        "pending": "⏳ Pending",
        "processing": "⚙️ Processing",
        "completed": "✅ Completed",
        "failed": "❌ Failed",
        "file": "📄 File",
        "corrected": "✨ Corrected Text",
        "comparison_view": "🔍 Comparison View",
        "created": "📅 Created At",
        "language_select": "🌐 Select Language",
        "no_corrected": "⚠️ No corrected text available for this image.",
        "all_files": "📂 All Files",
        "processing_queue": "⏳ Processing Queue",
        "view_results": "👁️ View Results",
        "current_session": "📋 Current Session Results",
        "new_session": "🆕 New Session Started",
        "stats_header": "📈 Processing Statistics",
        "upload_instructions": "Supported formats: PNG, JPG, JPEG, TIFF, BMP",
        "ai_powered": "Post Processed Text",
        "drop_here": "Drop files here",
        "max_files": "Maximum 10 files at once",
        "session_active": "🟢 Session Active",
        "time_elapsed": "⏱️ Time Elapsed",
        "selected_files": "📁 Selected Files",
        "download_report": "📥 Download Comparison Report",
        "raw_ocr": "Raw OCR Output",
        "download_raw": "⬇️ Download Raw Text",
        "get_comparison": "🔍 Text Comparison",
        "unprocessed_text": "Unprocessed Text",
        "success_rate": "Success Rate",
        "raw_text":"RAW TEXT",
        "corrected_text":"CORRECTED TEXT",
        "position": "Position",
        "raw" : "RAW",
        "corrected": "CORRECTED",
        "w_l_c": "Word-level Changes"
    },
    "ar": {
        "title": "✨ نظام التعرف الضوئي للعربية",
        "subtitle": "استخراج وتصحيح النصوص العربية من صور المستندات بدقة الذكاء الاصطناعي",
        "main upload": "",
        "upload_tab": "📤 الرفع والمعالجة",
        "upload_header": "رفع المستندات",
        "upload_description": "ارفع الصور التي تحتوي على نصوص عربية لمعالجتها.",
        "upload_placeholder": "📁 اسحب وأفلت الصور هنا أو اضغط للتصفح",
        "upload_button": "🚀 بدء المعالجة",
        "queued_success": "✅ تم بنجاح إضافة {count} ملف إلى قائمة الانتظار",
        "results_header": "نتائج المعالجة",
        "refresh_button": "🔄 تحديث الحالة",
        "clear_results": "🗑️ مسح الكل وبدء جلسة جديدة",
        "clear_confirm": "هل أنت متأكد من رغبتك في مسح جميع النتائج والبدء من جديد؟",
        "no_jobs": "قائمة الانتظار فارغة. ارفع بعض الصور للبدء.",
        "no_completed": "⏳ لا توجد مهام مكتملة بعد. ستظهر النتائج هنا قريباً.",
        "extracted_text": "النص المستخرج والمصحح",
        "download_text": "⬇️ تحميل النص",
        "images": "الصور",
        "status": "📊 الحالة",
        "pending": "⏳ قيد الانتظار",
        "processing": "⚙️ جاري المعالجة",
        "completed": "✅ مكتمل",
        "failed": "❌ فشل",
        "file": "📄 الملف",
        "corrected": "✨ النص المصحح",
        "comparison_view": "🔍 عرض المقارنة",
        "created": "📅 وقت الإنشاء",
        "language_select": "🌐 اختر اللغة",
        "no_corrected": "⚠️ لا يوجد نص مصحح متاح لهذه الصورة.",
        "all_files": "📂 جميع الملفات",
        "processing_queue": "⏳ قائمة الانتظار",
        "view_results": "👁️ عرض النتائج",
        "current_session": "📋 نتائج الجلسة الحالية",
        "new_session": "🆕 بدأت جلسة جديدة",
        "stats_header": "📈 إحصائيات المعالجة",
        "upload_instructions": "الصيغ المدعومة: PNG, JPG, JPEG, TIFF, BMP",
        "ai_powered": "النص بعد المعالجة الذكية",
        "drop_here": "أفلت الملفات هنا",
        "max_files": "الحد الأقصى 10 ملفات في المرة الواحدة",
        "session_active": "🟢 الجلسة نشطة",
        "time_elapsed": "⏱️ الوقت المنقضي",
        "selected_files": "📁 الملفات المختارة",
        "download_report": "📥 تحميل تقرير المقارنة",
        "raw_ocr": "مخرجات OCR الخام",
        "download_raw": "⬇️ تحميل النص الخام",
        "get_comparison": "🔍 مقارنة النصوص",
        "unprocessed_text": "نص غير معالج",
        "success_rate": "نسبة النجاح",
        "raw_text": "النص الخام",
        "corrected_text": "النص المصحح",
        "position": "الموقع",
        "raw": "خام",
        "corrected": "مصحح",
        "w_l_c": "تغييرات على مستوى الكلمات",
    }
}

def apply_custom_styles() -> None:
    """Apply custom CSS styles for enhanced UI."""
    st.markdown("""
    <style>
    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Header styling */
    .header-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        color: white;
    }
    
    .header-title {
        font-size: 2.5rem !important;
        font-weight: 800 !important;
        margin-bottom: 0.5rem !important;
        background: linear-gradient(45deg, #fff, #f0f0f0);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    
    .header-subtitle {
        font-size: 1.1rem !important;
        opacity: 0.9;
        margin-bottom: 0 !important;
    }
    
    /* Card styling */
    .custom-card {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 5px 20px rgba(0,0,0,0.08);
        border: 1px solid #eaeaea;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    .custom-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.12);
    }
    
    /* Upload area styling */
    .upload-area {
        border: 3px dashed #667eea;
        border-radius: 15px;
        padding: 3rem;
        text-align: center;
        background: linear-gradient(145deg, #f8f9ff, #ffffff);
        margin: 2rem 0;
        transition: all 0.3s ease;
    }
    
    .upload-area:hover {
        border-color: #764ba2;
        background: linear-gradient(145deg, #f0f2ff, #ffffff);
    }
    
    /* Button styling */
    .stButton > button {
        border-radius: 10px !important;
        padding: 0.75rem 2rem !important;
        font-weight: 600 !important;
        border: none !important;
        transition: all 0.3s ease !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4) !important;
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }
    
    /* Secondary button */
    .stButton > button[kind="secondary"] {
        background: linear-gradient(135deg, #6c757d 0%, #495057 100%) !important;
    }
    
    /* Status indicators */
    .status-pending {
        color: #ffc107;
        font-weight: 600;
        background: rgba(255, 193, 7, 0.1);
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        display: inline-block;
    }
    
    .status-processing {
        color: #17a2b8;
        font-weight: 600;
        background: rgba(23, 162, 184, 0.1);
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        display: inline-block;
        animation: pulse 1.5s infinite;
    }
    
    .status-completed {
        color: #28a745;
        font-weight: 600;
        background: rgba(40, 167, 69, 0.1);
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        display: inline-block;
    }
    
    .status-failed {
        color: #dc3545;
        font-weight: 600;
        background: rgba(220, 53, 69, 0.1);
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        display: inline-block;
    }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    
    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #f8f9ff, #ffffff);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        border: 1px solid rgba(102, 126, 234, 0.1);
    }
    
    .metric-value {
        font-size: 2.5rem !important;
        font-weight: 800 !important;
        background: linear-gradient(45deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem !important;
    }
    
    .metric-label {
        font-size: 0.9rem !important;
        color: #6c757d !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Text area styling */
    .text-display {
        background: linear-gradient(145deg, #f8f9ff, #ffffff);
        border-radius: 12px;
        padding: 1.5rem;
        min-height: 400px;
        max-height: 500px;
        overflow-y: auto;
        border: 1px solid rgba(102, 126, 234, 0.1);
        font-size: 1.1rem;
        line-height: 1.8;
    }
    
    .text-display.rtl {
        text-align: right;
        direction: rtl;
        font-family: 'Arial', 'Segoe UI', sans-serif;
    }
    
    .text-display.ltr {
        text-align: left;
        direction: ltr;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        background: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: linear-gradient(135deg, #f8f9ff, #ffffff);
        border-radius: 10px 10px 0 0;
        padding: 0.75rem 2rem;
        border: 1px solid rgba(102, 126, 234, 0.1);
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        color: white !important;
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
    }
    
    /* Language toggle */
    .language-toggle {
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 1000;
    }
    
    .lang-btn {
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        color: white !important;
        border-radius: 50% !important;
        width: 60px !important;
        height: 60px !important;
        font-size: 1.5rem !important;
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3) !important;
    }
    
    .lang-btn:hover {
        transform: scale(1.1);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4) !important;
    }
    
    /* Image preview */
    .image-preview {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        transition: transform 0.3s ease;
    }
    
    .image-preview:hover {
        transform: scale(1.02);
    }
    
    /* Progress bar */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea, #764ba2);
    }
    
    /* Success/Error messages */
    .stAlert {
        border-radius: 12px;
        border: none;
        box-shadow: 0 5px 15px rgba(0,0,0,0.08);
    }
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #667eea, #764ba2);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #764ba2, #667eea);
    }
    
    </style>
    """, unsafe_allow_html=True)