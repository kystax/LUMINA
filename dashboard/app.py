import os
import sys
import io
from pathlib import Path

# Ensure root and dashboard directories are in sys.path for cloud deployment
_current_dir = Path(__file__).resolve().parent
_root_dir = _current_dir.parent
for _p in [str(_current_dir), str(_root_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


if sys.platform == "win32":
    try:
        if isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if isinstance(sys.stderr, io.TextIOWrapper):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Fix Streamlit shutdown race condition on Windows ("RuntimeError: Event loop is closed")
try:
    import asyncio
    if sys.platform == "win32" and sys.version_info < (3, 14):
        set_policy = getattr(asyncio, "set_event_loop_policy", None)
        if set_policy:
            set_policy(asyncio.WindowsSelectorEventLoopPolicy())
except Exception:
    pass

try:
    import streamlit.runtime.app_session as app_session
    _orig_on_scriptrunner_event = app_session.AppSession._on_scriptrunner_event
    def _safe_on_scriptrunner_event(self, *args, **kwargs):
        try:
            return _orig_on_scriptrunner_event(self, *args, **kwargs)
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                return None
            raise
    app_session.AppSession._on_scriptrunner_event = _safe_on_scriptrunner_event
except Exception:
    pass

import streamlit as st

from components import render_sidebar
from pages import render_main_page, render_settings_page
from utils import load_css
from auth_ui import require_login

st.set_page_config(
    page_title="LUMINA – Cognitive Pattern Monitoring",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Inject Google Fonts via link tag (CSS @import is stripped by Streamlit markdown injection)
st.markdown(
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Serif+Display:ital@0;1&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">'
    '<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">',
    unsafe_allow_html=True,
)

load_css("assets/style.css")
load_css("assets/upload_section.css")
load_css("style_additions.css")

require_login()  # blocks everything below until authenticated

user = st.session_state.user

from services.profile_service import get_subjects

if "active_subject" not in st.session_state:
    subjects = get_subjects(user["user_id"]) if user else []
    st.session_state.active_subject = subjects[0] if subjects else None
    # Start with no analysis — results only appear after user runs analysis
    st.session_state.lumina_session_analysis = None

page = st.query_params.get("page", "main")

if isinstance(page, list):
    page = page[0] if page else "main"

page = page.lower()

render_sidebar(settings_active=(page == "settings"))

if page == "settings":
    render_settings_page()
else:
    render_main_page()
