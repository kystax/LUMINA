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
    page_title="Lumina Cognitive Risk AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css("assets/style.css")
load_css("assets/upload_section.css")

# Warm up mBERT model once at server startup
try:
    from modules.nlp.classifier import get_mbert
    get_mbert()
except Exception as e:
    print(f"[LUMINA] Warmup notice: {e}")

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
