"""
LUMINA - Analysis Pipeline Orchestrator
Ties together: sessions -> text extraction -> NLP -> SNA -> ABM -> risk_results.

This is what upload_section.py calls after a ZIP is uploaded.
"""

from __future__ import annotations

from typing import Any
import os
import sys
from pathlib import Path

# Make sure the project root (parent of "dashboard") is importable, the same
# way auth.py does it — needed because Streamlit's working dir / sys.path
# does not automatically include the project root.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.append(str(_PROJECT_ROOT))

import io

if sys.platform == "win32":
    try:
        if isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if isinstance(sys.stderr, io.TextIOWrapper):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from database.connection import get_connection, release_connection  # noqa: E402


# ─────────────────────────────────────────────
# SESSION HANDLING
# ─────────────────────────────────────────────

def create_analysis_run(user_id: int, subject_id: int | None = None) -> int | None:
    """
    Create one parent `analysis_runs` row for a single "Run Analysis" click.
    Returns run_id (int) or None on failure.  Called once before the
    per-file session loop so all sessions share the same parent.
    """
    conn = get_connection()
    if not conn:
        return None
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO analysis_runs (user_id, subject_id)
            VALUES (%s, %s)
            RETURNING run_id
            """,
            (user_id, subject_id),
        )
        row = cur.fetchone()
        run_id = row[0] if row else None
        conn.commit()
        print(f"[LUMINA Pipeline] Analysis run created (run_id={run_id})")
        return run_id
    except Exception as e:
        conn.rollback()
        print(f"[LUMINA Pipeline] create_analysis_run error: {e}")
        return None
    finally:
        if cur:
            cur.close()
        release_connection(conn)


def finalize_analysis_run(
    run_id: int,
    session_ids: list[int],
    platforms: list[str],
) -> None:
    """
    After all per-file sessions complete, compute the sample-count-weighted
    mean of their final_scores and update the analysis_runs row.

    Weighting by sample_count ensures platforms with more text (more signal)
    have proportionally more influence on the combined score.
    """
    if not run_id or not session_ids:
        return

    conn = get_connection()
    if not conn:
        return
    cur = None
    try:
        cur = conn.cursor()

        # Fetch final_score and sample_count for each session
        cur.execute(
            """
            SELECT rr.final_score, COALESCE(ns.sample_count, 1)
            FROM risk_results rr
            LEFT JOIN nlp_scores ns ON ns.session_id = rr.session_id
            WHERE rr.session_id = ANY(%s)
            """,
            (session_ids,),
        )
        rows = cur.fetchall()

        if rows:
            total_weight = sum(float(r[1]) for r in rows)
            if total_weight <= 0:
                total_weight = len(rows)
            combined_score = round(
                sum(float(r[0]) * float(r[1]) for r in rows) / total_weight, 4
            )
        else:
            combined_score = 0.0

        # Map to risk class using the same thresholds as the rest of the system
        from modules.config.thresholds import RISK_CLASS_THRESHOLDS
        if combined_score < RISK_CLASS_THRESHOLDS["HC_MAX"]:
            combined_class = "HC"
        elif combined_score < RISK_CLASS_THRESHOLDS["MCI_MAX"]:
            combined_class = "MCI"
        else:
            combined_class = "AD_Risk"

        platforms_str = ", ".join(
            p.capitalize() for p in dict.fromkeys(platforms) if p and p != "unknown"
        ) or "unknown"

        cur.execute(
            """
            UPDATE analysis_runs
            SET combined_score = %s,
                combined_class = %s,
                platforms      = %s,
                session_count  = %s
            WHERE run_id = %s
            """,
            (combined_score, combined_class, platforms_str, len(session_ids), run_id),
        )
        conn.commit()
        print(
            f"[LUMINA Pipeline] Run {run_id} finalised: "
            f"{combined_class} ({combined_score}) across "
            f"{len(session_ids)} session(s) [{platforms_str}]"
        )
    except Exception as e:
        conn.rollback()
        print(f"[LUMINA Pipeline] finalize_analysis_run error: {e}")
    finally:
        if cur:
            cur.close()
        release_connection(conn)


def create_session(
    user_id: int,
    platform: str,
    file_path: str,
    subject_id: int | None = None,
    run_id: int | None = None,
) -> int | None:
    """Insert a row into `sessions` and return its session_id."""
    conn = get_connection()
    if not conn:
        return None

    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sessions (user_id, platform, data_file_path, subject_id, run_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING session_id
            """,
            (user_id, platform, file_path, subject_id, run_id),
        )
        row = cur.fetchone()
        session_id = row[0] if row else None
        conn.commit()
        return session_id
    except Exception as e:
        conn.rollback()
        print(f"[LUMINA Pipeline] create_session error: {e}")
        return None
    finally:
        if cur:
            cur.close()
        release_connection(conn)


# ─────────────────────────────────────────────
# NLP SCORES — INSERT (classifier.save_classification_to_db only UPDATEs,
# so a row needs to exist first)
# ─────────────────────────────────────────────

def save_nlp_features(nlp_result: dict, session_id: int) -> None:
    conn = get_connection()
    if not conn:
        return

    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO nlp_scores
                (session_id, ttr_score, complexity_score, coherence_score,
                 repetition_score, avg_word_length, avg_sentence_length,
                 sample_count, risk_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_id) DO UPDATE SET
                ttr_score = EXCLUDED.ttr_score,
                complexity_score = EXCLUDED.complexity_score,
                coherence_score = EXCLUDED.coherence_score,
                repetition_score = EXCLUDED.repetition_score,
                avg_word_length = EXCLUDED.avg_word_length,
                avg_sentence_length = EXCLUDED.avg_sentence_length,
                sample_count = EXCLUDED.sample_count,
                risk_score = EXCLUDED.risk_score
            """,
            (
                session_id,
                nlp_result.get("ttr", 0),
                nlp_result.get("complexity", 0),
                nlp_result.get("coherence", 0),
                nlp_result.get("repetition", 0),
                nlp_result.get("avg_word_length", 0),
                nlp_result.get("avg_sent_length", 0),
                nlp_result.get("sample_count", 0),
                nlp_result.get("risk_score", 0),
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[LUMINA Pipeline] save_nlp_features error: {e}")
    finally:
        if cur:
            cur.close()
        release_connection(conn)


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

def run_full_analysis(
    zip_path: str,
    username: str,
    user_id: int,
    platform: str = "unknown",
    subject_id: int | None = None,
    progress_callback=None,
    environmental_intake: dict | None = None,
    run_id: int | None = None,
) -> dict:
    """
    Run the full LUMINA pipeline on one uploaded ZIP file and persist every
    stage's results to PostgreSQL.

    progress_callback(str) is called with short status strings, so the
    Streamlit UI can show a live spinner/status message.
    """

    def _report(msg: str):
        print(f"[LUMINA Pipeline] {msg}")
        if progress_callback:
            progress_callback(msg)

    # Heavy imports (mBERT etc.) are done lazily, inside the function, so
    # the rest of the dashboard doesn't pay the model-loading cost on
    # every page load.
    from modules.sna.parser import extract_text_samples, save_samples_to_db
    from modules.sna.network import (
        extract_sna_metrics,
        save_sna_to_db,
        extract_sna_trends,
        extract_ego_network_names,
    )
    from modules.nlp.classifier import classify_risk, save_classification_to_db
    from modules.nlp.extractor import extract_features_by_period
    from modules.abm.model import LuminaABM, save_abm_to_db
    from modules.config.thresholds import ABM_SEED_WEIGHTS, ABM_DEFAULTS

    result: dict[str, Any] = {
        "session_id": None,
        "sample_count": 0,
        "nlp": None,
        "sna": None,
        "abm": None,
        "composite_risk_score": None,
        "outcome_scenarios": None,
        "ego_network": None,
        "sna_trend": None,
        "nlp_trend": None,
        "error": None,
    }

    # 1 — Create a session row for this upload
    _report("Creating analysis session…")
    session_id = create_session(user_id, platform, zip_path, subject_id, run_id)
    if not session_id:
        result["error"] = "Could not create a session (DB connection failed)."
        return result
    result["session_id"] = session_id
    result["run_id"] = run_id  # propagate so upload_section can collect it
    _report(f"Session created successfully (ID: {session_id})")

    # 2 — Extract raw text samples from the ZIP and store them
    _report("Extracting text samples from ZIP…")
    samples = extract_text_samples(zip_path, username)
    result["sample_count"] = len(samples)
    if not samples:
        result["error"] = "No valid text content found in the uploaded ZIP file. Please ensure you upload a supported export archive containing posts, comments, or messages."
        print(f"[LUMINA Pipeline] Current Upload ID: {session_id} - FAILED: No valid text samples parsed.")
        return result

    save_samples_to_db(samples, session_id)
    texts = [s["text"] for s in samples]

    posts_count = sum(1 for s in samples if s.get("source_type") in ("post", "threads_post"))
    comments_count = sum(1 for s in samples if "comment" in s.get("source_type", ""))
    dms_count = sum(1 for s in samples if "dm" in s.get("source_type", "") or "message" in s.get("source_type", ""))

    # 3 & 4 — Run NLP classification, SNA metrics, Ego network, SNA trends,
    # NLP trends, and Follower timeline all concurrently in parallel threads.
    _report("Running NLP & Social Network Analysis concurrently…")
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _run_nlp():
        nlp_res = classify_risk(texts)
        save_nlp_features(nlp_res, session_id)
        save_classification_to_db(nlp_res, session_id)
        return "nlp", nlp_res

    def _run_sna():
        sna_met = extract_sna_metrics(zip_path, username)
        save_sna_to_db(sna_met, session_id)
        return "sna", sna_met

    def _ego():
        try:
            return "ego_network", extract_ego_network_names(zip_path, username)
        except Exception as e:
            print(f"[LUMINA Pipeline] extract_ego_network_names error: {e}")
            return "ego_network", []

    def _sna_trends():
        try:
            return "sna_trend", extract_sna_trends(zip_path, username)
        except Exception as e:
            print(f"[LUMINA Pipeline] extract_sna_trends error: {e}")
            return "sna_trend", {}

    def _nlp_trends():
        try:
            from modules.nlp.classifier import classify_risk_by_period
            return "nlp_trend", classify_risk_by_period(samples)
        except Exception as e:
            print(f"[LUMINA Pipeline] classify_risk_by_period error: {e}")
            return "nlp_trend", {}

    def _follower():
        try:
            from modules.sna.parser import extract_follower_timeline
            return "follower_timeline", extract_follower_timeline(zip_path)
        except Exception as e:
            print(f"[LUMINA Pipeline] extract_follower_timeline error: {e}")
            return "follower_timeline", {"platform": "unknown", "series": {}, "empty": True}

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [
            pool.submit(_run_nlp),
            pool.submit(_run_sna),
            pool.submit(_ego),
            pool.submit(_sna_trends),
            pool.submit(_nlp_trends),
            pool.submit(_follower),
        ]
        for f in as_completed(futures):
            key, val = f.result()
            result[key] = val

    nlp_result = result["nlp"] or {}
    sna_metrics = result["sna"] or {}

    posting_freq = float(sna_metrics.get("posting_frequency", 0.0))
    net_size = int(sna_metrics.get("network_size", 0))
    dm_contacts = int(sna_metrics.get("dm_contact_count", 0))
    interaction_div = float(sna_metrics.get("interaction_diversity", 0.0))
    withdrawal = float(sna_metrics.get("withdrawal_score", 0.0))
    language_score = float(nlp_result.get("risk_score", 0.5))

    users_parsed = max(net_size, dm_contacts, 1)

    # 5 — Agent-Based Model simulation, seeded from all extracted metrics.
    _report("Running Agent-Based Model simulation…")
    from modules.config.thresholds import ABM_SEED_TTR_NORM_CAP, ABM_SEED_COMPLEXITY_NORM_CAP
    ttr = float(nlp_result.get("ttr", 0.5) or 0.5)
    complexity = float(nlp_result.get("complexity", 0.1) or 0.1)

    _report("Processing environmental and clinical intake...")
    from modules.environmental.scoring import calculate_environmental_score, save_environmental_scores
    if environmental_intake:
        env_factors = environmental_intake.get("factors", {})
        symptom_severity = environmental_intake.get("symptom_severity", 0.0)
    else:
        env_factors = {}
        symptom_severity = 0.0

    env_score = calculate_environmental_score(env_factors, symptom_severity)
    save_environmental_scores(session_id, env_factors, symptom_severity, env_score)
    result["environmental_score"] = env_score
    result["environmental_intake"] = {
        "factors": env_factors,
        "symptom_severity": symptom_severity,
        "environmental_score": env_score,
    }

    # Combine language score, social engagement, posting frequency, network size, interaction diversity, response behaviour
    freq_risk = 1.0 - min(posting_freq / 10.0, 1.0)
    diversity_risk = 1.0 - min(interaction_div, 1.0)
    social_engagement_risk = round((freq_risk + diversity_risk) / 2.0, 4)

    abm_seed_risk = round(
        language_score * 0.40 +
        withdrawal * 0.25 +
        social_engagement_risk * 0.20 +
        (1.0 - min(ttr * ABM_SEED_TTR_NORM_CAP, 1.0)) * 0.15,
        4,
    )
    result["abm_seed_risk"] = abm_seed_risk

    # Mandatory Diagnostic Logging
    print("\n" + "="*50)
    print(f"Current Upload ID: {session_id}")
    print(f"Posts Parsed: {posts_count}")
    print(f"Comments Parsed: {comments_count}")
    print(f"Messages Parsed: {dms_count}")
    print(f"Users Parsed: {users_parsed}")
    print(f"Calculated Posting Frequency: {posting_freq:.4f}")
    print(f"Calculated Network Size: {net_size}")
    print(f"Interaction Diversity: {interaction_div:.4f}")
    print(f"ABM Initial Risk: {abm_seed_risk:.4f}")
    print("="*50 + "\n")

    model = LuminaABM(
        n_people=ABM_DEFAULTS["n_people"],
        n_community_agents=ABM_DEFAULTS["n_community_agents"],
        initial_risk_score=abm_seed_risk,
        grid_size=ABM_DEFAULTS["grid_size"],
        seed=session_id,
    )
    abm_history = model.run(steps=ABM_DEFAULTS["steps"])
    summary = model.get_summary()
    save_abm_to_db(summary, session_id)
    result["abm"] = summary
    result["abm_history"] = abm_history

    try:
        from database.connection import get_connection, release_connection
        conn = get_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT final_score FROM risk_results WHERE session_id = %s", (session_id,))
            row = cur.fetchone()
            if row and row[0] is not None:
                result["composite_risk_score"] = float(row[0])
            release_connection(conn)
    except Exception as e:
        print(f"[LUMINA Pipeline] DB read error for final_score: {e}")

    _report("Simulating possible outcomes…")
    try:
        from modules.abm.model import run_outcome_scenarios
        seed_risk = result.get("composite_risk_score")
        if seed_risk is None or seed_risk <= 0:
            seed_risk = abm_seed_risk
        result["outcome_scenarios"] = run_outcome_scenarios(
            seed_risk,
            seed=session_id,
            environmental_intake=environmental_intake,
        )
    except Exception as e:
        print(f"[LUMINA Pipeline] run_outcome_scenarios error: {e}")
        result["outcome_scenarios"] = None

    _report("Analysis complete.")
    return result
