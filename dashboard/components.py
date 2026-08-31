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

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        render_html("<div class='menu-label'>User Profile</div>")

        has_analysis = st.session_state.get("lumina_session_analysis") is not None
        status_dot = '<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#6F5A8E;margin-right:4px;"></span>' if has_analysis else '<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#C9C0D2;margin-right:4px;"></span>'
        status_text = "Analysis Active" if has_analysis else "Awaiting Analysis"

        render_html(f"""
            <div class="sidebar-user-card">
                <div class="sidebar-user-name">
                    {html.escape(display_name)}
                </div>
                <div class="sidebar-user-role">
                    {html.escape(user_type)} account
                </div>
                <div class="sidebar-user-status">
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
            </nav>
            """
        )

        st.markdown("<div style='height:60px'></div>", unsafe_allow_html=True)
        if st.button("Sign out", key="sidebar_signout", width="stretch", type="secondary"):
            logout()


# ─────────────────────────────────────────────
# TOPBAR
# ─────────────────────────────────────────────

def render_topbar(title: str, subtitle: str, page: str = "main") -> None:
    """
    Full navigation bar matching the MediCore dashboard reference:
    - Left: page title + subtitle
    - Center: nav links (Dashboard, Analysis, Recent, Reports, Settings)
    - Right: search pill, notification bell, avatar
    """
    user         = st.session_state.get("user") or {}
    avatar_letter= html.escape((user.get("username") or "?")[:1].upper())
    display_name = html.escape((user.get("username") or "Guest"))

    # Determine active page for nav highlighting
    active_page = page.lower()

    def _nav_cls(name: str) -> str:
        return "topnav-link active" if active_page == name else "topnav-link"

    render_html(
        f"""
        <div class="lumina-topbar">
            <!-- Left: brand title + subtitle -->
            <div class="topbar-left">
                <div class="topbar-page-title">{html.escape(title)}</div>
                <div class="topbar-page-sub">Welcome, {display_name}</div>
            </div>

            <!-- Center: nav links -->
            <nav class="topbar-nav">
                <a class="{_nav_cls('main')}" href="?page=main#dashboard-section" target="_self">Dashboard</a>
                <a class="{_nav_cls('analysis')}" href="?page=main#user-analysis-section" target="_self">Analysis</a>
                <a class="{_nav_cls('recent')}" href="?page=main#recent-analysis-section" target="_self">Recent</a>
                <a class="{_nav_cls('reports')}" href="?page=main#reports-section" target="_self">Reports</a>
                <a class="{_nav_cls('settings')}" href="?page=settings" target="_self">Settings</a>
            </nav>

            <!-- Right: search + bell + avatar -->
            <div class="topbar-right">
                <div class="topbar-search">
                    <span class="topbar-search-icon">&#128269;</span>
                    <span class="topbar-search-text">Search patterns or records...</span>
                </div>
                <div class="topbar-bell" title="Notifications">
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                        <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                    </svg>
                </div>
                <div class="topbar-avatar">{avatar_letter}</div>
            </div>
        </div>
        """
    )


def render_profile_header_strip() -> None:
    """
    Renders the active profile header strip matching the calm purple design:
    Name, role, analysis status, and action buttons.
    """
    user = st.session_state.get("user") or {}
    display_name = user.get("username") or "Researcher Account"
    has_analysis = st.session_state.get("lumina_session_analysis") is not None
    last_status = "Today" if has_analysis else "Not analyzed yet"

    c1, c2 = st.columns([3, 1.3], gap="small")
    with c1:
        render_html(
            f"""
            <div style="margin-bottom: 8px;">
                <div style="font-size: 11.5px; color: #6F7470; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 2px;">
                    Active Profile
                </div>
                <div style="font-family: 'DM Serif Display', Georgia, serif; font-size: 28px; font-weight: 400; color: #292D2B; line-height: 1.2;">
                    {html.escape(display_name)}
                </div>
                <div style="font-size: 13px; color: #6F7470; margin-top: 4px;">
                    Your cognitive pattern overview · last analyzed {last_status}
                </div>
            </div>
            """
        )
    with c2:
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        btn_col1, btn_col2 = st.columns([1, 1], gap="small")
        with btn_col1:
            if st.button("Upload data", key="header_upload_btn", type="primary", width="stretch"):
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
                "Export report",
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

