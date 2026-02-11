"""Arabic OCR Application - Main entry point with Enhanced UI."""

import logging
import streamlit as st
from dotenv import load_dotenv

from config import apply_custom_styles, LANGUAGES
from utils import get_text, start_worker
from render import render_language_selector, render_upload_and_results
from PIL import Image

from database import (
    init_db,
    clear_all_data,
)

# Configuration
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def main() -> None:
    """Main application entry point."""
    st.set_page_config(
        page_title="Arabic OCR System",
        page_icon=Image.open("logo.jpg"),
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Apply custom CSS styles
    apply_custom_styles()

    # Initialize session state
    if "language" not in st.session_state:
        st.session_state.language = "en"
    
    if "selected_image" not in st.session_state:
        st.session_state.selected_image = 0
    
    if "first_upload" not in st.session_state:
        st.session_state.first_upload = True
    
    if "clear_data_on_upload" not in st.session_state:
        st.session_state.clear_data_on_upload = False
    
    # Initialize database ONCE at the beginning
    if "db_initialized" not in st.session_state:
        with st.spinner("Initializing database..."):
            try:
                init_db()
                st.session_state.db_initialized = True
                logger.info("Database initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                st.error(f"Database initialization failed: {e}")
                return
    
    # Auto-clear previous data when app starts
    if "app_initialized" not in st.session_state:
        with st.spinner("Starting fresh session..."):
            try:
                # Clear all previous data on app start
                clear_all_data()
                st.session_state.app_initialized = True
                logger.info("App initialized - previous data cleared")
            except Exception as e:
                logger.error(f"Failed to clear previous data: {e}")
                # Continue anyway, but log the error
                st.session_state.app_initialized = True

    # Render language selector
    render_language_selector(LANGUAGES)
    
    # Create enhanced header
    st.markdown("""
    <div class="header-container">
        <h1 class="header-title">{}</h1>
        <p class="header-subtitle">{}</p>
    </div>
    """.format(get_text("title"), get_text("subtitle")), unsafe_allow_html=True)

    # Start background worker
    start_worker()

    # Single tab for everything
    render_upload_and_results()


if __name__ == "__main__":
    main()