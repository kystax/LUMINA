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
    Dark INK sidebar with Fraunces wordmark, page-anchor nav links,
    and a "Signed in — {name} · Sign out" strip at the bottom.
    Sign out calls logout() from auth_ui, which clears session state.
    """
    from auth_ui import logout   # lazy import to avoid circular refs
    from services.profile_service import get_subjects, create_subject, update_subject, delete_subject

    user         = st.session_state.get("user") or {}
    user_id      = user.get("user_id", 0)
    display_name = user.get("username") or "Guest"
    user_type    = (user.get("user_type") or "individual").capitalize()
    avatar_letter= display_name[:1].upper() if display_name else "?"

    # 1. Fetch current subjects list
    subjects = get_subjects(user_id) if user_id else []

    # 2. Check session state active subject
    if "active_subject" not in st.session_state:
        st.session_state.active_subject = subjects[0] if subjects else None
        # Don't auto-load old analysis — start clean
        st.session_state.lumina_session_analysis = None

    if settings_active:
        dashboard_href      = "?page=main#dashboard-section"
        user_analysis_href  = "?page=main#user-analysis-section"
        recent_analysis_href= "?page=main#recent-analysis-section"
        reports_href        = "?page=main#reports-section"
        settings_class      = "nav-anchor active"
    else:
        dashboard_href      = "#dashboard-section"
        user_analysis_href  = "#user-analysis-section"
        recent_analysis_href= "#recent-analysis-section"
        reports_href        = "#reports-section"
        settings_class      = "nav-anchor"

    with st.sidebar:
        render_html(
            f"""
            <!-- Brand block -->
            <div class="brand">
                <div>
                    <div class="brand-name">LUMINA</div>
                    <div class="brand-sub">Cognitive pattern monitoring</div>
                </div>
            </div>
            """
        )

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.subheader("👤 User Profile")

        has_analysis = st.session_state.get("lumina_session_analysis") is not None
        status_dot = "🟢" if has_analysis else "🔘"
        status_text = "Analysis Active" if has_analysis else "No Active Analysis"

        render_html(f"""
            <div style="
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 12px;
                margin: 6px 0 14px 0;
                font-size: 12px;
                line-height: 1.6;
            ">
                <div style="font-weight: 600; color: #ffffff; margin-bottom: 2px;">
                    {html.escape(display_name)}
                </div>
                <div style="color: rgba(255,255,255,0.6);">
                    {html.escape(user_type)} account
                </div>
                <div style="color: rgba(255,255,255,0.8); margin-top: 6px;">
                    {status_dot} {status_text}
                </div>
            </div>
        """)

        render_html(
            f"""
            <div class="menu-label">Main Menu</div>

            <nav class="sidebar-nav">
                <a class="nav-anchor"
                   href="{dashboard_href}"
                   target="_self">
                    Dashboard
                </a>

                <a class="nav-anchor"
                   href="{user_analysis_href}"
                   target="_self">
                    User Analysis
                </a>

                <a class="nav-anchor"
                   href="{recent_analysis_href}"
                   target="_self">
                    Recent Analysis
                </a>

                <a class="nav-anchor"
                   href="{reports_href}"
                   target="_self">
                    Reports
                </a>

                <a class="{settings_class}"
                   href="?page=settings"
                   target="_self">
                    Settings
                </a>
            </nav>
            """
        )

        st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)
        if st.button("↪  Sign out", key="sidebar_signout", width="stretch"):
            logout()


# ─────────────────────────────────────────────
# TOPBAR
# ─────────────────────────────────────────────

def render_topbar(title: str, subtitle: str) -> None:
    user         = st.session_state.get("user") or {}
    avatar_letter= html.escape((user.get("username") or "?")[:1].upper())

    render_html(
        f"""
        <div class="topbar">
            <div class="topbar-grid">
                <div>
                    <div class="page-title">{html.escape(title)}</div>
                    <div class="page-subtitle">{html.escape(subtitle)}</div>
                </div>
                <div class="top-actions">
                    <div class="search-pill">
                        ⌕&nbsp;&nbsp; Search users or reports
                        <span>⌘ K</span>
                    </div>
                    <div class="circle-action">♢</div>
                    <div class="avatar">{avatar_letter}</div>
                </div>
            </div>
        </div>
        """
    )


def render_profile_header_strip() -> None:
    """
    Renders the active profile header strip matching the React design:
    Name, relation, platform, analysis status, and action buttons.
    """
    user = st.session_state.get("user") or {}
    display_name = user.get("username") or "Researcher Account"
    has_analysis = st.session_state.get("lumina_session_analysis") is not None
    last_status = "Today" if has_analysis else "Not analyzed yet"

    c1, c2 = st.columns([3, 1.2], gap="small")
    with c1:
        render_html(
            f"""
            <div style="margin-bottom: 8px;">
                <div style="font-size: 12px; color: #6B7280; display: flex; align-items: center; gap: 6px; margin-bottom: 2px;">
                    👤 Active Analysis Profile
                </div>
                <div style="font-family: 'Fraunces', serif; font-size: 26px; font-weight: 500; color: #1B2430; line-height: 1.2;">
                    {html.escape(display_name)}
                </div>
                <div style="font-size: 13px; color: #6B7280; margin-top: 4px;">
                    Cognitive pattern monitoring · last analyzed {last_status}
                </div>
            </div>
            """
        )
    with c2:
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        btn_col1, btn_col2 = st.columns([1, 1], gap="small")
        with btn_col1:
            if st.button("⬆ Upload data", key="header_upload_btn", type="primary", width="stretch"):
                st.session_state["show_upload_modal"] = True
                st.rerun()
        with btn_col2:
            from services.report_service import generate_analysis_pdf, create_pdf_report
            user = st.session_state.get("user") or {}
            subj_name = display_name or user.get("display_name") or user.get("username") or "Avery"
            analysis = st.session_state.get("lumina_session_analysis") or {}
            if analysis:
                pdf_data_bytes = generate_analysis_pdf(
                    result=analysis,
                    subject_name=subj_name,
                    username=subj_name,
                )
            else:
                pdf_data_bytes = create_pdf_report()

            st.download_button(
                "📄 Export report",
                data=pdf_data_bytes,
                file_name=f"{subj_name.lower().replace(' ', '_')}_risk_report.pdf",
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
    """Return an HTML risk pill using the new RUST/AMBER/TEAL palette."""
    risk_key = level.lower()

    dot_colors = {
        "high":   "#B4573E",  # RUST
        "medium": "#C08A2E",  # AMBER
        "low":    "#3F6B62",  # TEAL
    }
    dot_color = dot_colors.get(risk_key, "#6B7280")

    return (
        f'<span class="risk-pill risk-{risk_key}">'
        f'<span class="dot risk-dot" style="background:{dot_color};"></span>'
        f"{html.escape(level)}</span>"
    )
