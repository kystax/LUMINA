import streamlit as st

from components import (
    render_section_heading,
    render_topbar,
    render_profile_header_strip,
)
from sections import (
    render_user_analysis_tabs,
    render_recent_analyses,
    render_reports,
    render_ai_insights,
    render_follower_timeline,
)
from upload_section import render_zip_upload_section
from utils import render_html


def _anchor(section_id: str) -> None:
    render_html(
        f'<div id="{section_id}" class="section-anchor"></div>'
    )


def render_main_page() -> None:
    """
    Render main dashboard matching the React LuminaDashboard layout:
    - Active Profile Header Card (with Upload Data and Export Report buttons)
    - Upload Data Section (expands/toggles when requested or directly visible)
    - Tabbed User Analysis ([Overview], [Language], [Social behavior], [Simulation])
    - Follower Timeline
    - Recent Analysis Table
    - Reports & AI Insights
    """
    render_topbar("Dashboard", "Cognitive pattern monitoring", page="main")
    render_profile_header_strip()

    # If Upload Data button clicked in header, show Upload section expander open
    show_upload = st.session_state.get("show_upload_modal", False)
    
    _anchor("dashboard-section")
    with st.expander("Upload & Analyze Export Data", expanded=show_upload or False):
        render_zip_upload_section()


    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

    _anchor("user-analysis-section")
    render_user_analysis_tabs()

    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

    _anchor("recent-analysis-section")
    render_section_heading(
        "Recent Analysis",
        "Review recently completed records",
    )
    render_recent_analyses()

    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

    _anchor("reports-section")
    render_section_heading(
        "Reports & AI Insights",
        "Download summary reports and review AI insights",
    )

    report_column, insight_column = st.columns(
        [1, 2],
        gap="medium",
    )

    with report_column:
        render_reports()

    with insight_column:
        render_ai_insights()


def render_settings_page() -> None:
    """Render Settings as a separate view."""
    render_topbar(
        "Settings",
        "Manage dashboard, analysis, account, and privacy preferences",
        page="settings",
    )

    with st.container(border=True):
        render_html(
            """
            <div class="settings-placeholder">
                <div class="settings-title">Dashboard Settings</div>
                <div class="settings-copy">
                    Add account, notification, privacy, model, and data-retention
                    settings in this page.
                </div>
                <a class="back-dashboard-link"
                   href="?page=main#dashboard-section"
                   target="_self">
                    ← Back to Dashboard
                </a>
            </div>
            """
        )
