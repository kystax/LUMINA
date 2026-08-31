from __future__ import annotations

import html

import streamlit as st

from config import COLORS
from utils import render_html


def color(value: str) -> str:
    return COLORS.get(value, value)


# ─────────────────────────────────────────────
# SIDEBAR  (matches lumina_dashboard JSX)
# ─────────────────────────────────────────────

def render_sidebar(settings_active: bool = False) -> None:
    """
    Dark Teal sidebar matching reference image:
    - Brain icon logo + LUMINA Cognitive Pattern Risk Analyzer
    - Navigation items with icons (Dashboard, Upload Data, My Analyses, Reports, Settings, Help & About)
    - Bottom disclaimer card: LUMINA is for research and risk screening purposes only. Version 1.0.0
    - Sign out action
    """
    from auth_ui import logout
    from services.profile_service import get_subjects

    user         = st.session_state.get("user") or {}
    user_id      = user.get("user_id", 0)
    display_name = user.get("username") or "user2"

    # Fetch current subjects list
    subjects = get_subjects(user_id) if user_id else []
    if "active_subject" not in st.session_state:
        st.session_state.active_subject = subjects[0] if subjects else None
        st.session_state.lumina_session_analysis = None

    dash_cls = "nav-item-link" if settings_active else "nav-item-link active"
    sett_cls = "nav-item-link active" if settings_active else "nav-item-link"

    with st.sidebar:
        render_html(
            f"""
            <!-- Brand block -->
            <div class="sidebar-brand-block">
                <div class="sidebar-brand-logo">
                    <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#42ABA1" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-2.04"/>
                        <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-2.04"/>
                    </svg>
                </div>
                <div>
                    <div class="sidebar-brand-title">LUMINA</div>
                    <div class="sidebar-brand-tagline">Cognitive Pattern<br>Risk Analyzer</div>
                </div>
            </div>

            <!-- Navigation menu -->
            <nav class="sidebar-nav-list">
                <a class="{dash_cls}" href="?page=main#dashboard-section" target="_self">
                    <span class="nav-item-icon">🏠</span>
                    <span>Dashboard</span>
                </a>
                <a class="nav-item-link" href="?page=main#dashboard-section" target="_self">
                    <span class="nav-item-icon">☁️</span>
                    <span>Upload Data</span>
                </a>
                <a class="nav-item-link" href="?page=main#user-analysis-section" target="_self">
                    <span class="nav-item-icon">📁</span>
                    <span>My Analyses</span>
                </a>
                <a class="nav-item-link" href="?page=main#reports-section" target="_self">
                    <span class="nav-item-icon">📄</span>
                    <span>Reports</span>
                </a>
                <a class="{sett_cls}" href="?page=settings" target="_self">
                    <span class="nav-item-icon">⚙️</span>
                    <span>Settings</span>
                </a>
                <a class="nav-item-link" href="?page=main#reports-section" target="_self">
                    <span class="nav-item-icon">❓</span>
                    <span>Help & About</span>
                </a>
            </nav>

            <!-- Bottom disclaimer card -->
            <div class="sidebar-footer-card">
                <div class="sidebar-disclaimer">
                    <span style="font-size:13px; opacity:0.85;">ℹ️</span>
                    <span>LUMINA is for research and risk screening purposes only. Not a clinical diagnosis.</span>
                </div>
                <div class="sidebar-version">Version 1.0.0</div>
            </div>
            """
        )

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        if st.button("Sign out", key="sidebar_signout", width="stretch", type="secondary"):
            logout()


# ─────────────────────────────────────────────
# PROFILE HEADER STRIP
# ─────────────────────────────────────────────

def render_profile_header_strip() -> None:
    """
    Renders the active profile header strip matching the reference image:
    - Active profile label
    - Name (e.g. user2) + Not analyzed yet / Analysis active badge
    - Subtitle: Your cognitive pattern overview
    - Right: Last analyzed + Upload data + Export report buttons
    """
    user = st.session_state.get("user") or {}
    display_name = user.get("username") or "user2"
    has_analysis = st.session_state.get("lumina_session_analysis") is not None
    last_status = "Today" if has_analysis else "—"
    badge_label = "Analysis active" if has_analysis else "Not analyzed yet"

    c1, c2 = st.columns([3, 2.2], gap="medium")
    with c1:
        render_html(
            f"""
            <div class="header-profile-wrap">
                <div class="header-profile-label">Active profile</div>
                <div class="header-profile-row">
                    <span class="header-profile-name">{html.escape(display_name)}</span>
                    <span class="header-profile-badge">{badge_label}</span>
                </div>
                <div class="header-profile-sub">Your cognitive pattern overview</div>
            </div>
            """
        )
    with c2:
        st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
        btn_c1, btn_c2, btn_c3 = st.columns([1.1, 1.4, 1.4], gap="small")
        with btn_c1:
            render_html(
                f"""
                <div class="header-last-analyzed">
                    <span class="last-analyzed-icon">🕒</span>
                    <div>
                        <div class="last-analyzed-label">Last analyzed</div>
                        <div class="last-analyzed-val">{last_status}</div>
                    </div>
                </div>
                """
            )
        with btn_c2:
            if st.button("☁️ Upload data", key="header_upload_btn", type="primary", width="stretch"):
                st.session_state["show_upload_modal"] = True
                st.rerun()
        with btn_c3:
            from services.report_service import generate_analysis_pdf, create_pdf_report
            from services.risk_service import get_recent_risk_results, get_sessions_for_run, get_analysis_by_session_id
            user = st.session_state.get("user") or {}
            subj_name = display_name or user.get("display_name") or user.get("username") or "user2"
            analysis = st.session_state.get("lumina_session_analysis") or {}

            # If not in live session state, fetch user's latest analysis from database
            if not analysis:
                user_id = user.get("user_id") or user.get("id")
                recent_results = get_recent_risk_results(limit=1, user_id=user_id) if user_id else []
                if recent_results:
                    latest = recent_results[0]
                    if isinstance(latest, (list, tuple)) and len(latest) > 4:
                        run_id = latest[4]
                        sess_ids = get_sessions_for_run(run_id)
                        if sess_ids:
                            latest_session = get_analysis_by_session_id(sess_ids[0])
                            if latest_session:
                                analysis = latest_session

            if analysis:
                pdf_data_bytes = generate_analysis_pdf(
                    result=analysis,
                    subject_name=subj_name,
                    username=subj_name,
                )
            else:
                pdf_data_bytes = create_pdf_report(
                    subject_name=subj_name,
                    username=subj_name,
                )

            st.download_button(
                "⬇️ Export report",
                data=pdf_data_bytes,
                file_name=f"{subj_name.lower().replace(' ', '_')}_pattern_report.pdf",
                mime="application/pdf",
                width="stretch",
                key="header_export_btn",
            )





# ─────────────────────────────────────────────
# SECTION HEADING
# ─────────────────────────────────────────────

def render_section_heading(title: str, subtitle: str) -> None:
    render_html(
        f"""
        <div class="section-heading">
            <div class="section-title">{html.escape(title)}</div>
            <div class="section-subtitle">{html.escape(subtitle)}</div>
        </div>
        """
    )


# ─────────────────────────────────────────────
# CARD HEADING
# ─────────────────────────────────────────────

def card_heading(
    title: str,
    subtitle: str,
    tag: str = "",
    tag_class: str = "",
) -> None:
    tag_html = (
        f'<span class="tag {html.escape(tag_class)}">'
        f"{html.escape(tag)}</span>"
        if tag
        else ""
    )

    render_html(
        f"""
        <div class="card-heading">
            <div>
                <div class="card-title">{html.escape(title)}</div>
                <div class="card-subtitle">{html.escape(subtitle)}</div>
            </div>
            {tag_html}
        </div>
        """
    )


# ─────────────────────────────────────────────
# RISK BADGE
# ─────────────────────────────────────────────

def risk_badge(level: str) -> str:
    """Return an HTML pattern variation pill using the LUMINA CALM palette."""
    risk_key = level.lower()

    dot_colors = {
        "high":     "#A96D67",  # Soft Clay / Elevated
        "elevated": "#A96D67",
        "medium":   "#B49A68",  # Soft Amber / Moderate
        "moderate": "#B49A68",
        "low":      "#78917C",  # Soft Sage / Lower
        "stable":   "#78917C",
    }
    dot_color = dot_colors.get(risk_key, "#6F5A8E")

    return (
        f'<span class="risk-pill risk-{risk_key}">'
        f'<span class="dot risk-dot" style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{dot_color};margin-right:5px;"></span>'
        f"{html.escape(level)}</span>"
    )

