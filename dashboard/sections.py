from __future__ import annotations

import html
import datetime as _dt
import pandas as pd
import streamlit as st

from charts import (
    make_ego_network,
    make_follower_timeline,
    make_gauge,
    make_composite_trend_chart,
    make_engagement_bar_chart,
    make_abm_trajectory_chart,
)
from components import card_heading, color, risk_badge
from config import COLORS
from modules.config.thresholds import FEATURE_THRESHOLDS, GAUGE_THRESHOLDS
from services.dashboard_service import (
    get_risk_distribution,
    get_total_analyses_count,
)
from services.insights_service import build_ai_insights_from_result
from services.risk_service import get_recent_risk_results, get_average_risk_score
from utils import render_html


def _current_user_id() -> int | None:
    user = st.session_state.get("user") or {}
    return user.get("user_id")


def _session_analysis() -> dict | None:
    """The most recently completed analysis in this session. None if no analysis run/active."""
    return st.session_state.get("lumina_session_analysis")


def _build_trend_data(analysis: dict | None) -> list[dict] | None:
    if not analysis:
        return None
    nlp_res = analysis.get("nlp") or {}
    sna_res = analysis.get("sna") or {}
    sna_trend = analysis.get("sna_trend") or {}
    nlp_trend = analysis.get("nlp_trend") or {}

    cur_nlp = round(float(nlp_res.get("risk_score", 0.0)) * 100)
    cur_sna = round(float(sna_res.get("withdrawal_score", 0.0)) * 100)

    periods = ["last_3_years", "last_year", "last_6_months", "last_3_months", "last_month", "last_week", "all_time"]
    windows = ["M-6", "M-5", "M-4", "M-3", "M-2", "M-1", "Now"]
    out = []

    last_valid_nlp = cur_nlp
    last_valid_sna = cur_sna

    for i, (w, p) in enumerate(zip(windows, periods)):
        p_sna = sna_trend.get(p, {}) if isinstance(sna_trend, dict) else {}
        p_nlp = nlp_trend.get(p, {}) if isinstance(nlp_trend, dict) else {}

        if p_nlp and "risk_score" in p_nlp:
            nlp_val = round(float(p_nlp["risk_score"]) * 100)
            last_valid_nlp = nlp_val
        else:
            nlp_val = last_valid_nlp

        if p_sna and "withdrawal_score" in p_sna:
            sna_val = round(float(p_sna["withdrawal_score"]) * 100)
            last_valid_sna = sna_val
        else:
            sna_val = last_valid_sna

        eng_count = 0
        if isinstance(p_sna, dict) and "comment_count" in p_sna:
            eng_count += int(p_sna.get("comment_count", 0))
        if isinstance(p_nlp, dict) and "sample_count_in_period" in p_nlp:
            eng_count = max(eng_count, int(p_nlp.get("sample_count_in_period", 0)))
        if eng_count == 0:
            eng_count = max(1, round((100 - sna_val) * 0.4))

        comp_val = round(nlp_val * 0.6 + sna_val * 0.4)

        out.append({
            "window": w,
            "nlp": nlp_val,
            "sna": sna_val,
            "composite": comp_val,
            "engagement_count": eng_count,
        })
    return out


def _build_abm_data(analysis: dict | None) -> dict | None:
    if not analysis or not analysis.get("outcome_scenarios"):
        return None
    scenarios = analysis["outcome_scenarios"]
    w_out = scenarios.get("without_support") or []
    w_supp = scenarios.get("with_support") or []
    if not w_out or not w_supp:
        return None

    horizons = ["Now", "+3mo", "+6mo", "+12mo"]
    step_indices = [0, min(3, len(w_out)-1), min(6, len(w_out)-1), min(12, len(w_out)-1)]

    base_list = []
    for h, idx in zip(horizons, step_indices):
        base_list.append({
            "horizon": h,
            "noSupport": round(w_out[idx]),
            "withSupport": round(w_supp[idx]),
        })

    # Factor scenarios
    factor_scenarios = {}
    raw_factor_scenarios = scenarios.get("factor_scenarios") or {}
    for f_key, f_series in raw_factor_scenarios.items():
        if f_series:
            factor_scenarios[f_key] = [
                {"horizon": h, "mitigated": round(f_series[idx])}
                for h, idx in zip(horizons, step_indices)
            ]

    combined_series = scenarios.get("combined_mitigation")
    if combined_series:
        factor_scenarios["combined_all"] = [
            {"horizon": h, "mitigated": round(combined_series[idx])}
            for h, idx in zip(horizons, step_indices)
        ]

    return {
        "base": base_list,
        "factor_scenarios": factor_scenarios,
        "factor_impacts": scenarios.get("factor_impacts") or [],
    }


def render_user_analysis_tabs() -> None:
    """
    Renders the tabbed User Analysis matching the React LuminaDashboard design:
    [Overview] [Language] [Social behavior] [Simulation]
    Calculates and displays real values when analysis exists, or zero state when no analysis.
    """
    tab_overview, tab_language, tab_social, tab_simulation = st.tabs(
        ["Overview", "Language", "Social behavior", "Simulation"]
    )

    analysis = _session_analysis()
    nlp_result = analysis.get("nlp") if analysis else None
    sna_result = analysis.get("sna") if analysis else None

    # Calculate real score if analysis exists, else 0
    score_is_incomplete = False
    card_title = "Composite Risk Score"
    card_subtitle = "Overall cognitive pattern risk"

    if analysis:
        comp_score = analysis.get("composite_risk_score")
        if comp_score is None and analysis.get("combined_scores"):
            comp_score = analysis["combined_scores"].get("final_score")
        if comp_score is None and nlp_result:
            comp_score = nlp_result.get("risk_score", 0.0)
            score_is_incomplete = True

        risk_score_pct = round(float(comp_score or 0.0) * 100)
        if score_is_incomplete:
            card_title = "NLP-only (partial) — composite unavailable"
            card_subtitle = "Linguistic sub-score only; multi-module composite calculation unavailable"
            score_tag, score_tag_class = "Incomplete (Partial)", "tag-amber"
        elif risk_score_pct >= GAUGE_THRESHOLDS["med_max"]:
            score_tag, score_tag_class = "Elevated pattern change", "tag-rust"
        elif risk_score_pct >= GAUGE_THRESHOLDS["low_max"]:
            score_tag, score_tag_class = "Moderate pattern change", "tag-amber"
        else:
            score_tag, score_tag_class = "Stable pattern change", "tag-green"
    else:
        risk_score_pct = 0
        score_tag, score_tag_class = "NO DATA", "tag-green"

    trend_data = _build_trend_data(analysis)
    abm_data = _build_abm_data(analysis)

    # ── TAB 1: OVERVIEW ──────────────────────────────────────────────
    with tab_overview:
        c1, c2 = st.columns([1, 2], gap="medium")

        with c1:
            with st.container(border=True):
                card_heading(
                    card_title,
                    card_subtitle,
                    score_tag,
                    score_tag_class,
                )

                st.plotly_chart(
                    make_gauge(risk_score_pct, incomplete=score_is_incomplete),
                    width="stretch",
                    theme=None,
                    config={"displayModeBar": False, "responsive": True},
                )

                render_html(
                    """
                    <div style="font-size: 11.5px; color: #6B7280; text-align: center; margin-top: 4px; line-height: 1.5;">
                        Reflects behavioral change over time, not a clinical diagnosis.
                    </div>
                    """
                )
                if analysis:
                    render_html(
                        """
                        <div class="info-alert-box" style="margin-top: 12px; padding: 10px 12px;">
                            ⚠️ <b>Sinhala content:</b> complexity score reliability reduced due to English reference model calibration.
                        </div>
                        """
                    )

        with c2:
            with st.container(border=True):
                card_heading(
                    "Composite risk over time",
                    "NLP and SNA sub-scores across windows",
                )

                st.plotly_chart(
                    make_composite_trend_chart(trend_data),
                    width="stretch",
                    theme=None,
                    config={"displayModeBar": False, "responsive": True},
                )

        st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

        # 4 Metric Cards Grid with real or zero values
        m_col1, m_col2, m_col3, m_col4 = st.columns(4, gap="medium")

        if analysis and sna_result:
            pf_val = f"{sna_result.get('posting_frequency', 0):.1f}/mo"
            contacts_val = str(sna_result.get("dm_contact_count", 0))
            eng_val = f"{sna_result.get('interaction_diversity', 0):.2f}"
        else:
            pf_val = "-"
            contacts_val = "0"
            eng_val = "-"

        if analysis and nlp_result:
            ttr_val = f"{nlp_result.get('ttr', 0.0):.2f}"
        else:
            ttr_val = "-"

        with m_col1:
            render_html(
                f"""
                <div class="overview-stat-card">
                    <div style="font-size: 16px;">📈</div>
                    <div class="overview-stat-val">{pf_val}</div>
                    <div class="overview-stat-sub">Posting frequency</div>
                </div>
                """
            )
        with m_col2:
            render_html(
                f"""
                <div class="overview-stat-card">
                    <div style="font-size: 16px;">💬</div>
                    <div class="overview-stat-val">{contacts_val}</div>
                    <div class="overview-stat-sub">Unique contacts messaged</div>
                </div>
                """
            )
        with m_col3:
            render_html(
                f"""
                <div class="overview-stat-card">
                    <div style="font-size: 16px;">❤️</div>
                    <div class="overview-stat-val">{eng_val}</div>
                    <div class="overview-stat-sub">Interaction diversity</div>
                </div>
                """
            )
        with m_col4:
            render_html(
                f"""
                <div class="overview-stat-card">
                    <div style="font-size: 16px;">📉</div>
                    <div class="overview-stat-val">{ttr_val}</div>
                    <div class="overview-stat-sub">Lexical diversity (TTR)</div>
                </div>
                """
            )

    # ── TAB 2: LANGUAGE (NLP) ─────────────────────────────────────────
    with tab_language:
        l_col1, l_col2 = st.columns([1, 1], gap="medium")

        with l_col1:
            with st.container(border=True):
                card_heading(
                    "Language metrics",
                    "Natural language processing feature analysis",
                )

                if nlp_result:
                    ttr_v = f"{nlp_result.get('ttr', 0.0):.2f}"
                    cmplx_v = f"{nlp_result.get('complexity', 0.0):.2f}"
                    avg_len_v = f"{nlp_result.get('avg_word_length', 0.0):.1f}"
                    rep_v = f"{nlp_result.get('repetition', 0.0):.2f}"
                else:
                    ttr_v = "-"
                    cmplx_v = "-"
                    avg_len_v = "-"
                    rep_v = "-"

                render_html(
                    f"""
                    <div class="metric-row">
                        <span class="metric-label">Lexical diversity (TTR)</span>
                        <div class="metric-val-group">
                            <span class="metric-value">{ttr_v}</span>
                        </div>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Avg. word length</span>
                        <div class="metric-val-group">
                            <span class="metric-value">{avg_len_v}</span>
                        </div>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Sentence complexity</span>
                        <div class="metric-val-group">
                            <span class="metric-value">{cmplx_v}</span>
                        </div>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Repetition score</span>
                        <div class="metric-val-group">
                            <span class="metric-value">{rep_v}</span>
                        </div>
                    </div>
                    """
                )

        with l_col2:
            with st.container(border=True):
                card_heading(
                    "Language distribution",
                    "Detected content language breakdown",
                )

                if nlp_result:
                    lang_dist = nlp_result.get("language_distribution") or {"en": 1.0}
                    en_frac = float(lang_dist.get("en", 0.0))
                    si_frac = float(lang_dist.get("si", 0.0)) + float(lang_dist.get("mixed", 0.0)) + float(lang_dist.get("ta", 0.0))
                    other_frac = sum(float(val) for key, val in lang_dist.items() if key not in ["en", "si", "mixed", "ta"])

                    total = en_frac + si_frac + other_frac
                    if total > 0:
                        en_val = round((en_frac / total) * 100)
                        si_val = round((si_frac / total) * 100)
                        other_val = max(0, 100 - en_val - si_val)
                    else:
                        en_val, si_val, other_val = 100, 0, 0

                    other_row_html = ""
                    if other_val > 0:
                        other_row_html = f"""
                            <div class="progress-row">
                                <div class="progress-meta">
                                    <span class="progress-name">Other / Unclear</span>
                                    <span class="progress-value" style="color: #6B7280;">{other_val}%</span>
                                </div>
                                <div class="progress-track">
                                    <div class="progress-fill" style="width: {other_val}%; background: #9CA3AF;"></div>
                                </div>
                            </div>
                        """

                    render_html(
                        f"""
                        <div class="progress-list">
                            <div class="progress-row">
                                <div class="progress-meta">
                                    <span class="progress-name">English</span>
                                    <span class="progress-value" style="color: #3F6B62;">{en_val}%</span>
                                </div>
                                <div class="progress-track">
                                    <div class="progress-fill" style="width: {en_val}%; background: #3F6B62;"></div>
                                </div>
                            </div>
                            <div class="progress-row">
                                <div class="progress-meta">
                                    <span class="progress-name">Sinhala / Romanized Sinhala</span>
                                    <span class="progress-value" style="color: #C08A2E;">{si_val}%</span>
                                </div>
                                <div class="progress-track">
                                    <div class="progress-fill" style="width: {si_val}%; background: #C08A2E;"></div>
                                </div>
                            </div>
                            {other_row_html}
                        </div>
                        <div class="info-alert-box">
                            Complexity scoring uses an English-language reference model. Scores for Sinhala / Romanized Sinhala content carry reduced reliability.
                        </div>
                        """
                    )
                else:
                    render_html(
                        """
                        <div style="font-size: 12px; color: #6B7280; text-align: center; padding: 24px 0;">
                            No language data available — upload a ZIP file above to analyze language patterns.
                        </div>
                        """
                    )

    # ── TAB 3: SOCIAL BEHAVIOR (SNA) ─────────────────────────────────
    with tab_social:
        s_col1, s_col2 = st.columns([1, 1], gap="medium")

        with s_col1:
            with st.container(border=True):
                card_heading(
                    "Social behavior metrics",
                    "Network interaction and engagement patterns",
                )

                if sna_result:
                    pf_v = f"{sna_result.get('posting_frequency', 0.0):.1f}/mo"
                    ns_v = str(sna_result.get("network_size", 0))
                    dm_v = str(sna_result.get("dm_contact_count", 0))
                    div_v = f"{sna_result.get('interaction_diversity', 0.0):.2f}"
                else:
                    pf_v = "-"
                    ns_v = "0"
                    dm_v = "0"
                    div_v = "-"

                render_html(
                    f"""
                    <div class="metric-row">
                        <span class="metric-label">Posting frequency</span>
                        <div class="metric-val-group">
                            <span class="metric-value">{pf_v}</span>
                        </div>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Network size</span>
                        <div class="metric-val-group">
                            <span class="metric-value">{ns_v}</span>
                        </div>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Interaction diversity</span>
                        <div class="metric-val-group">
                            <span class="metric-value">{div_v}</span>
                        </div>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Unique people messaged</span>
                        <div class="metric-val-group">
                            <span class="metric-value">{dm_v}</span>
                        </div>
                    </div>
                    """
                )

        with s_col2:
            with st.container(border=True):
                card_heading(
                    "Engagement received, by window",
                    "Social interaction volume over monthly windows",
                )

                st.plotly_chart(
                    make_engagement_bar_chart(trend_data),
                    width="stretch",
                    theme=None,
                    config={"displayModeBar": False, "responsive": True},
                )

    # ── TAB 4: SIMULATION (ABM) ───────────────────────────────────────
    with tab_simulation:
        with st.container(border=True):
            card_heading(
                "Projected trajectory (ABM)",
                "Simulated composite risk trajectories seeded from current pattern data and modifiable risk factors",
            )

            base_chart_data = abm_data.get("base") if isinstance(abm_data, dict) else abm_data
            factor_impacts = abm_data.get("factor_impacts") if isinstance(abm_data, dict) else []
            factor_scenarios = abm_data.get("factor_scenarios", {}) if isinstance(abm_data, dict) else {}

            mitigated_data = None
            mitigated_label = "Factor Mitigated"

            if factor_impacts:
                scenario_options = ["Baseline (Without Support vs Active Support)"] + [f["name"] for f in factor_impacts]
                selected_scenario_name = st.selectbox(
                    "Filter Trajectory Scenario View",
                    options=scenario_options,
                    key="abm_scenario_view_selector",
                    help="Select a specific modifiable risk factor to project its individual mitigation trajectory against the baseline.",
                )

                if selected_scenario_name != "Baseline (Without Support vs Active Support)":
                    # Find matching factor
                    matched = next((f for f in factor_impacts if f["name"] == selected_scenario_name), None)
                    if matched:
                        f_key = matched["key"]
                        mitigated_data = factor_scenarios.get(f_key)
                        mitigated_label = f"Mitigated: {matched['name']}"

            st.plotly_chart(
                make_abm_trajectory_chart(
                    base_chart_data,
                    mitigated_data=mitigated_data,
                    mitigated_label=mitigated_label,
                ),
                width="stretch",
                theme=None,
                config={"displayModeBar": False, "responsive": True},
            )

            if factor_impacts:
                st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                st.markdown("##### 🎯 Modifiable Risk Factor Trajectory Impact")
                st.caption(
                    "Estimated cognitive risk reduction at +12 months if specific modifiable dementia risk factors are addressed:"
                )

                rows_html = ""
                for imp in factor_impacts:
                    badge_class = "tag-green" if imp["key"] == "combined_all" else "tag-amber"
                    rows_html += f"""
                        <tr style="border-bottom: 1px solid #E5E7EB; font-size: 13px;">
                            <td style="padding: 8px 10px; font-weight: 600; color: #111827;">{html.escape(imp['name'])}</td>
                            <td style="padding: 8px 10px; text-align: center;">
                                <span class="risk-badge {badge_class}" style="font-size: 12px; font-weight: 700;">-{imp['reduction_at_12m']} pts at +12mo</span>
                            </td>
                            <td style="padding: 8px 10px; color: #4B5563; font-size: 12px;">{html.escape(imp['guidance'])}</td>
                        </tr>
                    """

                render_html(
                    f"""
                    <div class="responsive-table-wrapper">
                        <table style="width: 100%; border-collapse: collapse; margin-top: 6px; min-width: 540px;">
                            <thead>
                                <tr style="background-color: #F9FAFB; border-bottom: 2px solid #E5E7EB; text-align: left; font-size: 12px; color: #6B7280;">
                                    <th style="padding: 8px 10px;">MODIFIABLE FACTOR</th>
                                    <th style="padding: 8px 10px; text-align: center;">ESTIMATED IMPACT</th>
                                    <th style="padding: 8px 10px;">CLINICAL & LIFESTYLE GUIDANCE</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows_html}
                            </tbody>
                        </table>
                    </div>
                    """
                )
            elif analysis:
                st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                render_html(
                    """
                    <div style="font-size: 12px; color: #6B7280; background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 6px; padding: 10px 12px;">
                        ℹ️ <b>No modifiable risk factors selected:</b> To project specific risk trajectories (e.g. smoking cessation, physical activity increase, social contact increase), select applicable risk factors under the <b>Lancet Commission Intake</b> section before running analysis.
                    </div>
                    """
                )

            if analysis:
                render_html(
                    """
                    <div class="teal-info-box" style="margin-top: 12px;">
                        💡 <b>Simulation Disclaimer:</b> Simulation is a modeled projection based on agent-based interaction dynamics, not a clinical forecast. Use to compare intervention scenarios, not to predict individual outcomes.
                    </div>
                    """
                )


def render_recent_analyses() -> None:
    with st.container(border=True):
        card_heading(
            "Recent Analyses",
            "Your latest 6 records",
        )

        from services.risk_service import get_analysis_by_session_id, get_sessions_for_run
        from services.report_service import generate_analysis_pdf
        recent_results = get_recent_risk_results(user_id=_current_user_id())

        if not recent_results:
            render_html("""
                <div style="text-align:center; padding: 20px; color: #6B7280; font-size: 12px;">
                    No previous analysis records found. Upload a ZIP file above to create your first analysis record.
                </div>
            """)
            return

        h1, h2, h3, h4, h5, h6 = st.columns([1.5, 1.2, 1.2, 1.2, 1.2, 1.2])
        with h1: st.markdown("**USER NAME**")
        with h2: st.markdown("**DATE**")
        with h3: st.markdown("**RISK LEVEL**")
        with h4: st.markdown("**SCORE**")
        with h5: st.markdown("**STATUS**")
        with h6: st.markdown("**REPORT**")

        st.markdown("<hr style='margin: 4px 0 10px 0; border-color: #DEE1DB;'>", unsafe_allow_html=True)

        for i, result in enumerate(recent_results):
            # Handle tuple or dict row safely
            if isinstance(result, dict):
                display_name  = result.get("display_name") or "User"
                date_str      = str(result.get("created_at") or "")[:10]
                raw_risk      = result.get("combined_class") or result.get("risk_level")
                score_val     = result.get("combined_score") or result.get("risk_score") or 0.0
                run_id        = result.get("run_id") or i
                platforms_str = result.get("platforms") or ""
                session_count = result.get("session_count") or 1
            else:
                display_name  = result[0]
                date_str      = str(result[1])[:10]
                raw_risk      = result[2]
                score_val     = result[3]
                run_id        = result[4] if len(result) > 4 else i
                platforms_str = result[5] if len(result) > 5 else ""
                session_count = result[6] if len(result) > 6 else 1

            raw_risk_str = str(raw_risk or "Low")
            risk_level = {"HC": "Low", "MCI": "Medium", "AD_Risk": "High"}.get(raw_risk_str, raw_risk_str)
            score_class = f"score-{risk_level.lower()}"

            c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1.2, 1.2, 1.2, 1.2, 1.2])
            with c1:
                st.write(f"**{display_name}**")
                if platforms_str:
                    st.caption(platforms_str)
            with c2:
                st.write(date_str)
            with c3:
                render_html(risk_badge(risk_level))
            with c4:
                render_html(f'<span class="{score_class}">{round(float(score_val or 0) * 100)}</span><span class="score-total">/100</span>')
            with c5:
                render_html('<span class="status-pill status-completed">Completed</span>')
            with c6:
                # Build the PDF using all sessions belonging to this run
                session_ids = get_sessions_for_run(run_id) if run_id else []

                # Fetch per-platform data from DB for each session
                per_platform_list: list[dict] = []
                first_sess_analysis: dict | None = None
                for sid in session_ids:
                    sess_data = get_analysis_by_session_id(sid)
                    if sess_data:
                        if first_sess_analysis is None:
                            first_sess_analysis = sess_data
                        # Determine platform from DB session row
                        try:
                            from database.connection import get_connection, release_connection
                            _conn = get_connection()
                            if _conn:
                                _cur = _conn.cursor()
                                _cur.execute("SELECT platform FROM sessions WHERE session_id = %s", (sid,))
                                _prow = _cur.fetchone()
                                _plat = str(_prow[0]).capitalize() if _prow and _prow[0] else "Unknown"
                                _cur.close()
                                release_connection(_conn)
                            else:
                                _plat = "Unknown"
                        except Exception:
                            _plat = "Unknown"

                        per_platform_list.append({
                            "platform": _plat,
                            "session_id": sid,
                            "nlp": sess_data.get("nlp") or {},
                            "sna": sess_data.get("sna") or {},
                            "sample_count": sess_data.get("sample_count", 0),
                            "composite_risk_score": sess_data.get("composite_risk_score"),
                        })

                # Build the result dict expected by generate_analysis_pdf
                base_analysis = first_sess_analysis or {}
                cs = base_analysis.get("combined_scores") or {
                    "final_score": float(score_val or 0),
                    "nlp_sna_score": float((base_analysis.get("nlp") or {}).get("risk_score", 0)),
                    "environmental_score": float((base_analysis.get("environmental") or {}).get("environmental_risk_score", 0)),
                    "symptom_score": float((base_analysis.get("environmental") or {}).get("symptom_severity", 0)),
                }
                pdf_result = {
                    **base_analysis,
                    "combined_scores": cs,
                    "sample_count": sum(p.get("sample_count", 0) for p in per_platform_list) or base_analysis.get("sample_count", 0),
                    "session_id": session_ids[0] if session_ids else run_id,
                    "run_id": run_id,
                    "platforms_used": [p["platform"].lower() for p in per_platform_list],
                }

                pdf_bytes = generate_analysis_pdf(
                    result=pdf_result,
                    subject_name=display_name,
                    username=display_name,
                    per_platform=per_platform_list if len(per_platform_list) > 1 else None,
                )
                st.download_button(
                    "PDF 📄",
                    data=pdf_bytes,
                    file_name=f"{display_name.lower().replace(' ', '_')}_run{run_id}_{date_str}.pdf",
                    mime="application/pdf",
                    key=f"btn_pdf_dl_{run_id}_{i}",
                    width="stretch",
                )


def render_reports() -> None:
    with st.container(border=True):
        card_heading(
            "Reports",
            "Ready to download",
        )

        user_id = _current_user_id()
        risk_data = get_risk_distribution(user_id)
        analysis = _session_analysis()
        nlp_res = (analysis.get("nlp") or {}) if analysis else {}
        sna_res = (analysis.get("sna") or {}) if analysis else {}

        pdf_summary = [
            ("High-risk analyses", str(risk_data.get("AD_Risk", 0))),
            ("Medium-risk analyses", str(risk_data.get("MCI", 0))),
            ("Low-risk analyses", str(risk_data.get("HC", 0))),
            ("Overall risk score", f"{round(get_average_risk_score(user_id) * 100)}/100"),
            ("Analyses completed", str(get_total_analyses_count(user_id))),
        ]

        if analysis:
            pdf_summary.extend([
                ("-------------------", "-------------------"),
                ("Latest Risk Class", str(nlp_res.get("risk_class") or "-")),
                ("Composite Risk Score", f"{round((analysis.get('composite_risk_score') or 0.0)*100)}/100"),
                ("NLP Risk Indicator", f"{round((nlp_res.get('risk_score') or 0.0)*100)}/100"),
                ("Lexical Diversity (TTR)", f"{(nlp_res.get('ttr') or 0.0):.4f}"),
                ("Sentence Complexity", f"{(nlp_res.get('complexity') or 0.0):.4f}"),
                ("mBERT Coherence", f"{(nlp_res.get('coherence') or 0.0):.4f}"),
                ("Word Repetition", f"{(nlp_res.get('repetition') or 0.0):.4f}"),
                ("Posting Frequency", f"{(sna_res.get('posting_frequency') or 0.0):.1f}/mo"),
                ("Network Size", str(sna_res.get("network_size") or 0)),
                ("Interaction Diversity", f"{(sna_res.get('interaction_diversity') or 0.0):.2f}"),
                ("DM Contacts", str(sna_res.get("dm_contact_count") or 0)),
            ])

        recent_results = get_recent_risk_results(limit=100, user_id=user_id)

        from services.report_service import generate_analysis_pdf, create_pdf_report, generate_csv_report

        user = st.session_state.get("user") or {}
        subj_name = user.get("display_name") or user.get("username") or "Avery"
        if analysis:
            pdf_bytes = generate_analysis_pdf(
                result=analysis,
                subject_name=subj_name,
                username=subj_name,
            )
        else:
            pdf_bytes = create_pdf_report()

        st.download_button(
            "Download PDF Report",
            data=pdf_bytes,
            file_name="lumina_cognitive_risk_report.pdf",
            mime="application/pdf",
            width="stretch",
        )

        st.download_button(
            "Export Analysis CSV",
            data=generate_csv_report(recent_results, nlp_res, sna_res),
            file_name="lumina_analysis_export.csv",
            mime="text/csv",
            width="stretch",
        )


def render_ai_insights() -> None:
    with st.container(border=True):
        card_heading(
            "AI Insights",
            "Generated from the latest analysis",
        )

        analysis = _session_analysis()
        if analysis:
            ai_insights = build_ai_insights_from_result(
                analysis.get("nlp"), analysis.get("sna")
            )
        else:
            ai_insights = []

        if not ai_insights:
            render_html(
                '<div class="ai-copy">'
                "No active analysis yet — upload a ZIP above to generate AI insights."
                "</div>"
            )
            return

        cards = ""

        for insight in ai_insights:
            status_class = f"status-{insight.get('status', 'ok')}"
            cards += f"""
                <div class="ai-card {status_class}">
                    <div class="ai-copy">
                        {html.escape(insight["text"])}
                    </div>
                    <div class="confidence">
                        <span>CONFIDENCE</span>
                        <strong>{insight["confidence"]}%</strong>
                    </div>
                    <div class="progress-track">
                        <div class="progress-fill confidence-fill"
                            style="width:{insight["confidence"]}%;">
                        </div>
                    </div>
                </div>
            """

        render_html(cards)


def render_follower_timeline() -> None:
    """
    Follower / following / subscriber count over time, parsed directly from uploaded ZIP.
    """
    with st.container(border=True):
        card_heading(
            "Follower & Following Timeline",
            "How your network has grown over time, from your export",
        )

        analysis = _session_analysis()
        if not analysis:
            render_html(
                '<div class="ai-copy">'
                "No analysis yet — upload a ZIP to see your follower timeline."
                "</div>"
            )
            return

        follower_data = analysis.get("follower_timeline") or {}
        series = follower_data.get("series") or {}
        platform = follower_data.get("platform", "")
        is_empty = follower_data.get("empty", True)

        if is_empty or not series:
            render_html(
                '<div class="ai-copy">'
                "This export doesn't include dated follower data we can chart."
                "</div>"
            )
            return

        window = st.radio(
            "Time window",
            options=["3m", "6m", "1y"],
            format_func=lambda x: {"3m": "3 months", "6m": "6 months", "1y": "1 year"}[x],
            horizontal=True,
            label_visibility="collapsed",
            key="lumina_follower_window",
        )

        st.plotly_chart(
            make_follower_timeline(series, platform=platform, window=window),
            width="stretch",
            theme=None,
            config={"displayModeBar": False, "responsive": True},
        )
