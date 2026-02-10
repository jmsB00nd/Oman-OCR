import streamlit as st
import html
import difflib
from PIL import Image
from typing import Optional, List, Tuple, Dict, Any
import time

from utils import get_text, clear_previous_data

from fraud_detection import TextComparator, FraudDetectionRules

from config import UPLOAD_DIR

from database import (
    JobStatus,
    add_job,
    get_all_jobs,
)

def render_language_selector(LANGUAGES) -> None:
    """Render floating language selector."""

    if "lang" not in st.session_state:
        st.session_state.lang = "en"

    col1, col2, col3 = st.columns([8, 1, 1])
    with col3:  # top-right corner
        selected = st.selectbox(
        "",
        options=list(LANGUAGES.keys()),
        format_func=lambda x: LANGUAGES[x],
        index=list(LANGUAGES.keys()).index(st.session_state.lang),
        label_visibility="collapsed",
        key="login_lang_selector"
        )

    if selected != st.session_state.language:
        st.session_state.language = selected
        st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)

def render_statistics(jobs) -> None:
    """Render statistics cards."""
    completed_jobs = [job for job in jobs if job[2] == JobStatus.COMPLETED]
    pending_jobs = [job for job in jobs if job[2] in [JobStatus.PENDING, JobStatus.PROCESSING]]
    failed_jobs = [job for job in jobs if job[2].startswith(JobStatus.FAILED)]
    
    st.markdown(f"<h3 style='margin-bottom: 2rem;'>{get_text('stats_header')}</h3>", 
                unsafe_allow_html=True)
    
    cols = st.columns(5)
    
    with cols[0]:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">{}</div>
            <div class="metric-label">{}</div>
        </div>
        """.format(len(pending_jobs), get_text("pending")), unsafe_allow_html=True)
    
    with cols[1]:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">{}</div>
            <div class="metric-label">{}</div>
        </div>
        """.format(len(completed_jobs), get_text("completed")), unsafe_allow_html=True)
    
    with cols[2]:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">{}</div>
            <div class="metric-label">{}</div>
        </div>
        """.format(len(failed_jobs), get_text("failed")), unsafe_allow_html=True)
    
    with cols[3]:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">{}</div>
            <div class="metric-label">{}</div>
        </div>
        """.format(len(jobs), get_text("all_files")), unsafe_allow_html=True)
    
    with cols[4]:
        # Calculate success rate
        success_rate = (len(completed_jobs) / len(jobs) * 100) if jobs else 0
        st.markdown(f"""
        <div class="metric-card">
        <div class="metric-value">{success_rate:.1f}%</div>
        <div class="metric-label">{get_text("success_rate")}</div>
        </div>
        """,
    unsafe_allow_html=True
)


def render_fraud_analysis(analysis: Dict, raw_text: str, corrected_text: str):
    """Render comprehensive fraud analysis view."""
    
    # Risk score card
    risk_color = {
        'high': '#f56565',
        'medium': '#ed8936',
        'low': '#48bb78'
    }.get(analysis['risk_level'], '#718096')
    
    st.markdown(f"""
    <div style="text-align: center; padding: 1.5rem; background: white; 
              border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); 
              margin-bottom: 1.5rem; border: 2px solid {risk_color};">
        <div style="font-size: 3rem; font-weight: bold; color: {risk_color};">
            {analysis['total_risk_score']:.0f}
        </div>
        <div style="font-size: 1rem; color: #718096; margin-bottom: 0.5rem;">
            Fraud Risk Score
        </div>
        <div style="display: inline-block; padding: 0.5rem 1.5rem; 
                  background: {risk_color}; color: white; border-radius: 20px;
                  font-weight: bold; text-transform: uppercase;">
            {analysis['risk_level']} Risk
        </div>
        <div style="margin-top: 1rem; font-size: 1.1rem; color: #4a5568;">
            Recommendation: <strong>{analysis['recommendation']}</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Detailed violations
    if analysis['violations']:
        st.subheader("🚨 Detected Issues")
        for violation in analysis['violations']:
            with st.expander(f"{violation['rule']} - {violation['severity'].upper()}"):
                st.write(f"**Description:** {FraudDetectionRules.RULES[violation['rule']]['description']}")
                st.write(f"**Details:** {violation['details']}")
    
    # Historical trend (if multiple documents)
    st.subheader("📈 Change Pattern Analysis")
    
    # Visualize change patterns
    changes = TextComparator.word_level_diff(raw_text, corrected_text)
    
    if changes:
        # Create a simple bar chart of change types
        change_counts = {}
        for change in changes:
            change_counts[change['type']] = change_counts.get(change['type'], 0) + 1
        
        # Display as metrics
        cols = st.columns(len(change_counts))
        for idx, (change_type, count) in enumerate(change_counts.items()):
            with cols[idx]:
                st.metric(
                    label=change_type.title(),
                    value=count,
                    delta=None
                )

def render_upload_and_results() -> None:
    """Render the upload and results in a single tab with enhanced UI."""
    
    # Header section
    st.markdown(f"""
    <div class="custom-card" style="margin-bottom: 2rem;">
        <h2 style="color: #667eea; margin-bottom: 1rem;">{get_text('upload_header')}</h2>
        <p style="color: #6c757d; margin-bottom: 0.5rem;">{get_text('upload_description')}</p>
        <p style="color: #adb5bd; font-size: 0.9rem;">{get_text('upload_instructions')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Check if we should clear previous data
    if "clear_data_on_upload" not in st.session_state:
        st.session_state.clear_data_on_upload = False
    
    if st.session_state.clear_data_on_upload:
        with st.spinner("🔄 Clearing previous session..."):
            if clear_previous_data():
                st.success(get_text("new_session"))
                st.session_state.clear_data_on_upload = False
                st.rerun()
    
    # Upload section with custom styling
    col1, col2, col3, col4 = st.columns([3, 2, 1, 1])

    with col1:
        files = st.file_uploader(
            get_text("upload_placeholder"),
            accept_multiple_files=True,
            type=["png", "jpg", "jpeg", "tiff", "bmp"],
            key="file_uploader"
        )
    
    with col4:
        if st.button(get_text("clear_results"), type="secondary", use_container_width=True):
            #if st.checkbox("✅ Confirm clear all data"):
            st.session_state.clear_data_on_upload = True
            st.rerun()
        
    for i, file in enumerate(files, 1):
        st.write(f"{i}. **{file.name}** ({file.size / 1024:.1f} KB)")
    
    # Process button
    if files:
        col1, col2, col3 = st.columns([2, 1, 2])
        with col2:
            if st.button(get_text("upload_button"), use_container_width=True, type="primary"):
                # Clear previous data if this is the first upload of a new session
                if "first_upload" not in st.session_state:
                    with st.spinner("🔄 Preparing new session..."):
                        clear_previous_data()
                        st.session_state.first_upload = False
                
                #with st.spinner("📤 Uploading and queuing files..."):
                queued_count = 0
                for file in files:
                    file_path = UPLOAD_DIR / file.name
                    with open(file_path, "wb") as f:
                        f.write(file.read())
                    add_job(file.name)
                    queued_count += 1

                st.success(get_text("queued_success").format(count=queued_count))
                time.sleep(2)
                st.rerun()
    
    st.markdown("---")
    
    # Results section
    st.markdown(f"""
    <div style="margin-top: 2rem;">
        <h2 style="color: #667eea; margin-bottom: 1rem;">{get_text('results_header')}</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Get all jobs
    jobs = get_all_jobs()
    
    if not jobs:
        st.markdown(f"""
        <div class="custom-card" style="text-align: center; padding: 3rem;">
            <div style="font-size: 4rem; margin-bottom: 1rem; color: #adb5bd;">📭</div>
            <h3 style="color: #6c757d;">{get_text('no_jobs')}</h3>
            <p style="color: #adb5bd;">{get_text('upload_description')}</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # Render statistics
    render_statistics(jobs)
    
    # Refresh button
    # if st.button(get_text("refresh_button"), use_container_width=True):
    #     st.rerun()
    
    completed_jobs = [job for job in jobs if job[2] == JobStatus.COMPLETED]
    pending_jobs = [job for job in jobs if job[2] in [JobStatus.PENDING, JobStatus.PROCESSING]]
    failed_jobs = [job for job in jobs if job[2].startswith(JobStatus.FAILED)]
    
    # Show results if completed jobs exist
    if completed_jobs:
        st.markdown(f"<h3 style='margin-top: 2rem;'>{get_text('current_session')}</h3>", 
                   unsafe_allow_html=True)
        
        # Auto-select the first completed image if none selected
        if "selected_image" not in st.session_state or st.session_state.selected_image >= len(completed_jobs):
            st.session_state.selected_image = 0
        
        # NEW: Create THREE columns instead of two
        left_col, middle_col, right_col = st.columns([0.8, 1.2, 1.2])
        
        with left_col:
            
            image_tabs = st.tabs([f"📄 {job[1]}" for job in completed_jobs])
            
            for idx, (tab, job) in enumerate(zip(image_tabs, completed_jobs)):
                with tab:
                    filename = job[1]
                    image_path = UPLOAD_DIR / filename
                    
                    if image_path.exists():
                        try:
                            # Display image with enhanced styling
                            image = Image.open(image_path)
                            
                            # Calculate display size
                            max_width = 350
                            if image.width > max_width:
                                ratio = max_width / image.width
                                display_width = max_width
                                display_height = int(image.height * ratio)
                            else:
                                display_width = image.width
                                display_height = image.height
                            
                            # Display image with custom styling
                            st.markdown("<div class='image-preview'>", unsafe_allow_html=True)
                            st.image(
                                image, 
                                width=display_width,
                                use_container_width=False,
                                caption=""
                            )
                            st.markdown("</div>", unsafe_allow_html=True)
                            
                            # When this tab is active, update the selected image index
                            if tab._active:
                                st.session_state.selected_image = idx
                            
                            # Show file info with icons
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**{get_text('file')}:**<br>{filename}", 
                                          unsafe_allow_html=True)
                            with col2:
                                st.markdown(f"**{get_text('created')}:**<br>{job[5]}", 
                                          unsafe_allow_html=True)
                            
                            # Status badge
                            st.markdown(f"**{get_text('status')}:**<br><span class='status-completed'>{get_text('completed')}</span>", 
                                      unsafe_allow_html=True)
                                
                        except Exception as e:
                            st.error(f"Error loading image: {str(e)}")
                    else:
                        st.warning(f"Image file not found: {filename}")
            st.markdown("</div>", unsafe_allow_html=True)
        
        with middle_col:
            
            # Warning badge for unprocessed text
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #ff6b6b, #ee5a24); 
                        color: white; padding: 0.5rem 1rem; border-radius: 20px; 
                        display: inline-block; margin-bottom: 1rem; font-weight: 600;">
                {get_text("unprocessed_text")}
            </div>
            """, unsafe_allow_html=True)
            
            # Display raw text for the selected image
            if st.session_state.selected_image < len(completed_jobs):
                job = completed_jobs[st.session_state.selected_image]
                raw_text = job[3] if len(job) > 3 else None  # Raw Text is at index 3
                corrected_text = job[4] if len(job) > 4 else None  # Corrected Text is at index 4
                
                if raw_text:
                    # Get current language for text direction
                    lang = st.session_state.get("language", "en")
                    
                    # Calculate similarity if we have both texts
                    similarity = None
                    if raw_text and corrected_text:
                        similarity = TextComparator.calculate_similarity(raw_text, corrected_text)
                    
                    # Text display with custom styling
                    text_class = "rtl" if lang == "ar" else "ltr"
                    st.markdown(f"""
                    <div class="text-display {text_class}" 
                         style="background: #fff5f5; border-color: #feb2b2;">
                        <div style="font-size: 0.9rem; color: #718096; margin-bottom: 0.5rem;">
                            Length: {len(raw_text)} chars
                            {f'| Similarity: {similarity:.1f}%' if similarity else ''}
                        </div>
                        {raw_text}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Statistics expander
                    with st.expander("📊 Raw Text Analysis"):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Character Count", len(raw_text))
                        with col2:
                            st.metric("Word Count", len(raw_text.split()))
                        with col3:
                            st.metric("Line Count", len(raw_text.split('\n')))
                        
                        if similarity:
                            st.progress(similarity / 100, f"Similarity: {similarity:.1f}%")
                    
                    # Download button for raw text
                    col1, col2, col3 = st.columns([1, 1, 1])
                    
                    with col2:
                        st.download_button(
                        label=get_text("download_raw"),
                        data=raw_text,
                        file_name=f"{job[1].split('.')[0]}_raw.txt",
                        mime="text/plain",
                        key=f"download_raw_{job[0]}",
                        use_container_width=True
                        )
                else:
                    st.warning("No raw text available")
            st.markdown("</div>", unsafe_allow_html=True)
        
        with right_col:
            # NEW: Tabs for Corrected Text and Comparison
            view_tabs = st.tabs([get_text("corrected"), get_text("comparison_view")])
            
            with view_tabs[0]:            
                # AI-Powered badge
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #667eea, #764ba2); 
                            color: white; padding: 0.5rem 1rem; border-radius: 20px; 
                            display: inline-block; margin-bottom: 1rem; font-weight: 600;">
                    {get_text('ai_powered')}
                </div>
                """, unsafe_allow_html=True)
                
                # Display corrected text for the selected image
                if st.session_state.selected_image < len(completed_jobs):
                    job = completed_jobs[st.session_state.selected_image]
                    corrected_text = job[4] if len(job) > 4 else None  # Corrected Text is at index 4
                    
                    if corrected_text:
                        # Get current language for text direction
                        lang = st.session_state.get("language", "en")
                        
                        # Text display with custom styling
                        text_class = "rtl" if lang == "ar" else "ltr"
                        st.markdown(f"""
                        <div class="text-display {text_class}" 
                             style="background: #f0fff4; border-color: #9ae6b4;">
                            <div style="font-size: 0.9rem; color: #718096; margin-bottom: 0.5rem;">
                                Length: {len(corrected_text)} chars
                            </div>
                            {corrected_text}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.markdown("---")

                        # Download button with enhanced styling
                        col1, col2, col3 = st.columns([1, 1, 1])
                        with col2:
                            st.download_button(
                                label=get_text("download_text"),
                                data=corrected_text,
                                file_name=f"{job[1].split('.')[0]}_corrected.txt",
                                mime="text/plain",
                                key=f"download_{job[0]}",
                                use_container_width=True
                            )
                    else:
                        st.warning(get_text("no_corrected"))
                st.markdown("</div>", unsafe_allow_html=True)
            
            with view_tabs[1]:
                
                # Comparison badge
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #f6ad55, #ed8936); 
                            color: white; padding: 0.5rem 1rem; border-radius: 20px; 
                            display: inline-block; margin-bottom: 1rem; font-weight: 600;">
                    🔄 Change Analysis
                </div>
                """, unsafe_allow_html=True)
                
                if st.session_state.selected_image < len(completed_jobs):
                    job = completed_jobs[st.session_state.selected_image]
                    raw_text = job[3] if len(job) > 3 else None
                    corrected_text = job[4] if len(job) > 4 else None
                    
                    if raw_text and corrected_text:
                        # Generate comparison
                        similarity = TextComparator.calculate_similarity(raw_text, corrected_text)
                        
                        # Generate character-level diff
                        diff = list(difflib.ndiff(raw_text, corrected_text))
                        diff_html = []
                        
                        for char in diff:
                            if char.startswith('+ '):
                                diff_html.append(f'<span style="background-color: #c6f6d5; color: #22543d; padding: 2px; border-radius: 3px;">{html.escape(char[2:])}</span>')
                            elif char.startswith('- '):
                                diff_html.append(f'<span style="background-color: #fed7d7; color: #742a2a; padding: 2px; border-radius: 3px; text-decoration: line-through;">{html.escape(char[2:])}</span>')
                            elif char.startswith('  '):
                                diff_html.append(html.escape(char[2:]))
                        
                        diff_html = ''.join(diff_html)
                        
                        # Get current language for text direction
                        lang = st.session_state.get("language", "en")
                        text_class = "rtl" if lang == "ar" else "ltr"
                        
                        # Display comparison metrics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Similarity", f"{similarity:.1f}%")
                        with col2:
                            changes = len([d for d in diff if d.startswith('+ ') or d.startswith('- ')])
                            st.metric("Changes", changes)
                        with col3:
                            change_ratio = abs(len(corrected_text) - len(raw_text)) / max(len(raw_text), 1)
                            st.metric("Change Ratio", f"{change_ratio:.2%}")
                        
                        # Progress bar for similarity
                        color = "green" if similarity > 90 else "orange" if similarity > 70 else "red"
                        st.markdown(f"""
                        <div style="margin: 1rem 0;">
                            <div style="background: #e2e8f0; height: 10px; border-radius: 5px;">
                                <div style="background: {color}; width: {similarity}%; 
                                          height: 100%; border-radius: 5px;"></div>
                            </div>
                            <div style="font-size: 0.9rem; color: #718096; text-align: center; margin-top: 0.25rem;">
                                Text Similarity
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Word-level comparison
                        raw_words = raw_text.split()
                        corrected_words = corrected_text.split()
                        
                        word_diffs = []
                        for i, (raw_word, corrected_word) in enumerate(zip(raw_words, corrected_words)):
                            if raw_word != corrected_word:
                                word_diffs.append({
                                    'position': i,
                                    'raw': raw_word,
                                    'corrected': corrected_word,
                                    'type': 'replaced' if raw_word and corrected_word else 'deleted' if raw_word else 'inserted'
                                })
                        
                        # Display differences
                        st.markdown(f"""
                        <div class="text-display {text_class}" 
                             style="background: #f7fafc; border-color: #cbd5e0; 
                                    font-family: 'Courier New', monospace; font-size: 0.9rem;">
                            <div style="font-size: 0.9rem; color: #718096; margin-bottom: 0.5rem;">
                                Character-level differences:
                            </div>
                            {diff_html}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Legend
                        st.markdown("""
                        <div style="margin-top: 0.5rem; font-size: 0.9rem; color: #718096;">
                            <span style="background-color: #c6f6d5; padding: 2px 5px; border-radius: 3px; margin-right: 1rem;">
                                Green: Inserted
                            </span>
                            <span style="background-color: #fed7d7; padding: 2px 5px; border-radius: 3px;">
                                Red: Deleted
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Show word-level changes if any
                        if word_diffs:
                            with st.expander(f"📝 Word-level Changes ({len(word_diffs)})"):
                                for diff in word_diffs[:10]:  # Show first 10 to avoid clutter
                                    st.write(f"**{get_text("position")} {diff['position']}:**")
                                    st.write(f"  {get_text("raw")}: `{diff['raw']}` → {get_text("corrected")}: `{diff['corrected']}` ({diff['type']})")
                                
                                if len(word_diffs) > 10:
                                    st.write(f"... and {len(word_diffs) - 10} more changes")
                        
                        # Download comparison report
                        comparison_report = f"""
                        COMPARISON REPORT
                        =================
                        File: {job[1]}
                        Timestamp: {job[5]}
                        
                        STATISTICS
                        ----------
                        Similarity: {similarity:.1f}%
                        Raw Length: {len(raw_text)} chars
                        Corrected Length: {len(corrected_text)} chars
                        Changes Detected: {changes}
                        Change Ratio: {change_ratio:.2%}
                        
                        WORD-LEVEL CHANGES
                        ------------------
                        """
                        
                        for diff in word_diffs:
                            comparison_report += f"\n{get_text("position")} {diff['position']}: '{diff['raw']}' → '{diff['corrected']}' ({diff['type']})"
                        
                        comparison_report += f"""
                        
                        {get_text("RAW TEXT")}
                        --------
                        {raw_text}
                        
                        {get_text("CORRECTED TEXT")}
                        --------------
                        {corrected_text}
                        """
                        
                        col1, col2, col3 = st.columns([1, 1, 1])
                        
                        with col2:
                            st.download_button(
                            label=get_text("download_report"),
                            data=comparison_report,
                            file_name=f"{job[1].split('.')[0]}_comparison.txt",
                            mime="text/plain",
                            key=f"comparison_{job[0]}",
                            use_container_width=True
                            )
                        
                    else:
                        st.warning("Both raw and corrected text are required for comparison")
                st.markdown("</div>", unsafe_allow_html=True)
        
        # Show pending/processing jobs in an expander
        if pending_jobs or failed_jobs:
            with st.expander(f"🔍 {get_text('processing_queue')}", expanded=True):
                # Show pending/processing jobs
                if pending_jobs:
                    st.markdown(f"**{get_text('processing_queue')}:**")
                    for job in pending_jobs:
                        status_class = "status-processing" if job[2] == JobStatus.PROCESSING else "status-pending"
                        status_text = get_text('processing') if job[2] == JobStatus.PROCESSING else get_text('pending')
                        
                        st.markdown(f"""
                        <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                            <div style="flex: 1;">
                                📄 <strong>{job[1]}</strong>
                            </div>
                            <div>
                                <span class="{status_class}">{status_text}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Show failed jobs
                if failed_jobs:
                    st.markdown(f"**{get_text('failed')}:**")
                    for job in failed_jobs:
                        st.markdown(f"""
                        <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                            <div style="flex: 1;">
                                ❌ <strong>{job[1]}</strong>
                            </div>
                            <div>
                                <span class="status-failed">{get_text('failed')}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
    else:
        # Show processing queue if no completed jobs yet
        st.markdown(f"""
        <div class="custom-card" style="text-align: center; padding: 3rem;">
            <div style="font-size: 4rem; margin-bottom: 1rem; color: #17a2b8;">⏳</div>
            <h3 style="color: #6c757d;">{get_text('no_completed')}</h3>
            <p style="color: #adb5bd;">Processing in progress...</p>
        </div>
        """, unsafe_allow_html=True)
        
        if pending_jobs or failed_jobs:
            with st.expander(f"🔍 {get_text('processing_queue')}", expanded=True):
                # Show pending/processing jobs
                if pending_jobs:
                    st.markdown(f"**{get_text('processing_queue')}:**")
                    for job in pending_jobs:
                        status_class = "status-processing" if job[2] == JobStatus.PROCESSING else "status-pending"
                        status_text = get_text('processing') if job[2] == JobStatus.PROCESSING else get_text('pending')
                        
                        st.markdown(f"""
                        <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                            <div style="flex: 1;">
                                📄 <strong>{job[1]}</strong>
                            </div>
                            <div>
                                <span class="{status_class}">{status_text}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Show failed jobs
                if failed_jobs:
                    st.markdown(f"**{get_text('failed')}:**")
                    for job in failed_jobs:
                        st.markdown(f"""
                        <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                            <div style="flex: 1;">
                                ❌ <strong>{job[1]}</strong>
                            </div>
                            <div>
                                <span class="status-failed">{get_text('failed')}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)