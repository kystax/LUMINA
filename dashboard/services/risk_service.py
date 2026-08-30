from typing import Any

from database.connection import get_connection, release_connection


def get_recent_risk_results(limit=6, user_id=None):
    """
    Returns one row per "Run Analysis" click from `analysis_runs`.
    Each row: (display_name, created_at, combined_class, combined_score, run_id, platforms, session_count)
    """
    conn = get_connection()
    if not conn:
        return []

    cur = None
    try:
        cur = conn.cursor()
        if user_id is not None:
            cur.execute("""
                SELECT
                    COALESCE(sub.name, u.username) AS display_name,
                    ar.created_at,
                    ar.combined_class,
                    ar.combined_score,
                    ar.run_id,
                    ar.platforms,
                    ar.session_count
                FROM analysis_runs ar
                JOIN users u ON u.user_id = ar.user_id
                LEFT JOIN subjects sub ON sub.subject_id = ar.subject_id
                WHERE ar.user_id = %s
                ORDER BY ar.created_at DESC
                LIMIT %s
            """, (user_id, limit))
        else:
            cur.execute("""
                SELECT
                    COALESCE(sub.name, u.username) AS display_name,
                    ar.created_at,
                    ar.combined_class,
                    ar.combined_score,
                    ar.run_id,
                    ar.platforms,
                    ar.session_count
                FROM analysis_runs ar
                JOIN users u ON u.user_id = ar.user_id
                LEFT JOIN subjects sub ON sub.subject_id = ar.subject_id
                ORDER BY ar.created_at DESC
                LIMIT %s
            """, (limit,))

        rows = cur.fetchall()
        return rows
    except Exception as e:
        print(f"[LUMINA Risk Service] get_recent_risk_results error: {e}")
        return []
    finally:
        if cur:
            cur.close()
        release_connection(conn)


def get_sessions_for_run(run_id: int) -> list[int]:
    """Return all session_ids that belong to a given analysis run."""
    conn = get_connection()
    if not conn:
        return []
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT session_id FROM sessions WHERE run_id = %s ORDER BY session_id",
            (run_id,),
        )
        return [r[0] for r in cur.fetchall()]
    except Exception as e:
        print(f"[LUMINA Risk Service] get_sessions_for_run error: {e}")
        return []
    finally:
        if cur:
            cur.close()
        release_connection(conn)


def get_average_risk_score(user_id=None):
    conn = get_connection()
    if not conn:
        return 0

    cur = None
    try:
        cur = conn.cursor()
        if user_id is not None:
            cur.execute(
                "SELECT AVG(final_score) FROM risk_results WHERE user_id = %s",
                (user_id,),
            )
        else:
            cur.execute("SELECT AVG(final_score) FROM risk_results")

        row = cur.fetchone()
        result = row[0] if row else None
        return round(float(result), 2) if result is not None else 0
    except Exception as e:
        print(f"[LUMINA Risk Service] get_average_risk_score error: {e}")
        return 0
    finally:
        if cur:
            cur.close()
        release_connection(conn)


def get_analysis_by_session_id(session_id: int) -> dict | None:
    """Fetch complete analysis record from DB by session_id to display on dashboard."""
    conn = get_connection()
    if not conn:
        return None

    cur = None
    try:
        cur = conn.cursor()
        
        # Get session info
        cur.execute("SELECT user_id, platform FROM sessions WHERE session_id = %s", (session_id,))
        session_row = cur.fetchone()
        if not session_row:
            return None
        
        user_id, platform = session_row

        # Get NLP Scores
        cur.execute("""
            SELECT ttr_score, complexity_score, coherence_score, repetition_score, 
                   avg_word_length, avg_sentence_length, sample_count, risk_class, confidence_score, risk_score
            FROM nlp_scores WHERE session_id = %s
        """, (session_id,))
        nlp_row = cur.fetchone()

        # Get SNA Scores
        cur.execute("""
            SELECT posting_frequency, network_size, interaction_diversity, withdrawal_score, dm_contact_count
            FROM sna_scores WHERE session_id = %s
        """, (session_id,))
        sna_row = cur.fetchone()

        # Get Environmental Scores
        cur.execute("""
            SELECT environmental_risk_score, symptom_severity,
                   education_less_than_secondary, hearing_loss, hypertension,
                   smoking, obesity, depression, physical_inactivity, diabetes,
                   low_social_contact, excessive_alcohol, traumatic_brain_injury,
                   air_pollution, vision_loss, high_ldl_cholesterol
            FROM environmental_scores WHERE session_id = %s
        """, (session_id,))
        env_row = cur.fetchone()

        environmental_result: dict[str, Any] = {}
        if env_row:
            factor_labels = {
                "education_less_than_secondary": "Education < Secondary Level",
                "hearing_loss": "Hearing Loss",
                "hypertension": "Hypertension (High BP)",
                "smoking": "Smoking History",
                "obesity": "Obesity",
                "depression": "Depression",
                "physical_inactivity": "Physical Inactivity",
                "diabetes": "Diabetes Mellitus",
                "low_social_contact": "Low Social Contact",
                "excessive_alcohol": "Excessive Alcohol",
                "traumatic_brain_injury": "Traumatic Brain Injury",
                "air_pollution": "High Air Pollution Exposure",
                "vision_loss": "Vision Loss",
                "high_ldl_cholesterol": "High LDL Cholesterol",
            }
            factor_keys = list(factor_labels.keys())
            present_factors = []
            raw_factors = {}
            for idx, key in enumerate(factor_keys):
                is_present = bool(env_row[2 + idx])
                raw_factors[key] = is_present
                if is_present:
                    present_factors.append(factor_labels[key])

            environmental_result = {
                "environmental_risk_score": float(env_row[0]) if env_row[0] is not None else 0.0,
                "symptom_severity": float(env_row[1]) if env_row[1] is not None else 0.0,
                "factors_present": present_factors,
                "raw_factors": raw_factors,
            }

        # Get Final Risk Result
        cur.execute("""
            SELECT final_risk_class, final_score FROM risk_results WHERE session_id = %s
        """, (session_id,))
        risk_row = cur.fetchone()

        # Get Text Samples
        cur.execute("""
            SELECT text_content, sample_month FROM text_samples WHERE session_id = %s
        """, (session_id,))
        sample_rows = cur.fetchall()

        nlp_result: dict[str, Any] = {}
        if nlp_row:
            lang_dist = {}
            if sample_rows:
                try:
                    from modules.nlp.extractor import _language_distribution
                    lang_dist = _language_distribution([r[0] for r in sample_rows if r[0]])
                except Exception as e:
                    print(f"[LUMINA Risk Service] _language_distribution error: {e}")
            if not lang_dist:
                lang_dist = {"en": 1.0}

            nlp_result = {
                "ttr": float(nlp_row[0]) if nlp_row[0] is not None else 0.0,
                "complexity": float(nlp_row[1]) if nlp_row[1] is not None else 0.0,
                "coherence": float(nlp_row[2]) if nlp_row[2] is not None else 0.0,
                "repetition": float(nlp_row[3]) if nlp_row[3] is not None else 0.0,
                "avg_word_length": float(nlp_row[4]) if nlp_row[4] is not None else 0.0,
                "avg_sent_length": float(nlp_row[5]) if nlp_row[5] is not None else 0.0,
                "sample_count": int(nlp_row[6]) if nlp_row[6] is not None else 0,
                "risk_class": nlp_row[7] or "HC",
                "confidence": float(nlp_row[8]) if nlp_row[8] is not None else 0.0,
                "risk_score": float(nlp_row[9]) if (len(nlp_row) > 9 and nlp_row[9] is not None) else 0.0,
                "language_distribution": lang_dist,
            }

        sna_result: dict[str, Any] = {}
        if sna_row:
            sna_result = {
                "posting_frequency": float(sna_row[0]) if sna_row[0] is not None else 0.0,
                "network_size": int(sna_row[1]) if sna_row[1] is not None else 0,
                "interaction_diversity": float(sna_row[2]) if sna_row[2] is not None else 0.0,
                "withdrawal_score": float(sna_row[3]) if sna_row[3] is not None else 0.0,
                "dm_contact_count": int(sna_row[4]) if sna_row[4] is not None else 0,
            }

        composite_risk_score = float(risk_row[1]) if (risk_row and risk_row[1] is not None) else 0.0

        outcome_scenarios = None
        try:
            from modules.abm.model import run_outcome_scenarios
            from modules.config.thresholds import (
                ABM_SEED_TTR_NORM_CAP,
                ABM_SEED_COMPLEXITY_NORM_CAP,
                ABM_SEED_WEIGHTS,
            )

            ttr = float(nlp_result.get("ttr", 0.5) or 0.5)
            complexity = float(nlp_result.get("complexity", 0.1) or 0.1)
            withdrawal = float(sna_result.get("withdrawal_score", 0.0) or 0.0)

            ttr_risk = 1.0 - min(ttr * ABM_SEED_TTR_NORM_CAP, 1.0)
            complexity_risk = 1.0 - min(complexity / ABM_SEED_COMPLEXITY_NORM_CAP, 1.0)
            abm_seed_risk = round(
                ttr_risk * ABM_SEED_WEIGHTS["ttr_risk"] +
                complexity_risk * ABM_SEED_WEIGHTS["complexity_risk"] +
                withdrawal * ABM_SEED_WEIGHTS["withdrawal"],
                4,
            )
            seed_risk = composite_risk_score if composite_risk_score > 0 else abm_seed_risk
            env_intake = {"factors": environmental_result.get("raw_factors", {})} if environmental_result else None
            outcome_scenarios = run_outcome_scenarios(seed_risk, environmental_intake=env_intake)
        except Exception as e:
            print(f"[LUMINA Risk Service] run_outcome_scenarios error: {e}")

        nlp_trend = {}
        if sample_rows:
            try:
                from modules.nlp.extractor import extract_features_by_period
                samples = [{"text": r[0], "date_month": r[1]} for r in sample_rows]
                nlp_trend = extract_features_by_period(samples)
            except Exception as e:
                print(f"[LUMINA Risk Service] rebuild nlp_trend error: {e}")

        sna_trend = {}
        if sna_row:
            posting_freq = float(sna_row[0]) if sna_row[0] is not None else 0.0
            withdrawal = float(sna_row[3]) if sna_row[3] is not None else 0.0
            for period in ["last_week", "last_month", "last_3_months", "last_6_months", "last_year", "last_3_years", "all_time"]:
                sna_trend[period] = {
                    "posting_frequency": posting_freq,
                    "withdrawal_score": withdrawal,
                }

        return {
            "session_id": session_id,
            "sample_count": len(sample_rows),
            "nlp": nlp_result,
            "sna": sna_result,
            "environmental": environmental_result,
            "composite_risk_score": composite_risk_score,
            "outcome_scenarios": outcome_scenarios,
            "ego_network": [],
            "sna_trend": sna_trend,
            "nlp_trend": nlp_trend,
            "follower_timeline": {"platform": platform, "series": {}, "empty": True},
        }

    except Exception as e:
        print(f"[LUMINA Risk Service] get_analysis_by_session_id error: {e}")
        return None
    finally:
        if cur:
            cur.close()
        release_connection(conn)
