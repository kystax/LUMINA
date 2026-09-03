"""
LUMINA - Risk Classifier
Combines NLP features + mBERT embeddings to produce HC/MCI/AD_Risk score
"""

import torch
import numpy as np
import datetime
from transformers import AutoTokenizer, AutoModel
from modules.nlp.extractor import extract_features, stratified_sample_by_time, stratified_sample_texts
from modules.config.thresholds import (
    MAX_NLP_SAMPLES_TOTAL,
    MAX_NLP_SAMPLES_PER_PERIOD,
)

_MBERT_CACHE = None


def get_mbert():
    """
    Returns (tokenizer, model).
    Uses Streamlit's @st.cache_resource when available so the model
    survives script reruns for the lifetime of the server process.
    """
    global _MBERT_CACHE
    if _MBERT_CACHE is not None:
        return _MBERT_CACHE

    try:
        import streamlit as st

        @st.cache_resource
        def _load_cached():
            ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{ts}] [LUMINA] Loading mBERT model into memory...")
            tok = AutoTokenizer.from_pretrained("bert-base-multilingual-cased")
            mod = AutoModel.from_pretrained("bert-base-multilingual-cased")  # type: ignore
            mod.eval()
            ts2 = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{ts2}] [LUMINA] mBERT ready in memory.")
            return tok, mod

        _MBERT_CACHE = _load_cached()
    except Exception as e:
        print(f"[LUMINA] Cached mBERT load notice: {e}")
        if _MBERT_CACHE is None:
            try:
                ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"[{ts}] [LUMINA] Loading mBERT model (non-Streamlit)...")
                tok = AutoTokenizer.from_pretrained("bert-base-multilingual-cased")
                mod = AutoModel.from_pretrained("bert-base-multilingual-cased")  # type: ignore
                mod.eval()
                ts2 = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"[{ts2}] [LUMINA] mBERT ready.")
                _MBERT_CACHE = (tok, mod)
            except Exception as e2:
                print(f"[LUMINA] mBERT fallback disabled (memory constrained): {e2}")
                _MBERT_CACHE = (None, None)

    return _MBERT_CACHE


# ─────────────────────────────────────────────
# MAIN CLASSIFIER
# ─────────────────────────────────────────────

def classify_risk(
    texts: list[str],
    max_samples: int = MAX_NLP_SAMPLES_TOTAL,
    warn_if_few: bool = True
) -> dict:
    """
    Takes a list of text samples from one session.
    Returns risk classification result.
    """
    if not texts:
        raise ValueError("No valid text samples extracted from ZIP file to analyze.")
    # Warn if too few samples for reliable analysis
    if warn_if_few and len(texts) < 50:
        print(
            f"[LUMINA] Warning: Only {len(texts)} samples — result may not be reliable")

    # Step 1 — Extract NLP features (with stratified sampling applied if needed)
    features = extract_features(texts, max_samples=max_samples)

    # Step 2 — Determine complexity score reliability based on language mix
    lang_dist = features.get("language_distribution", {})
    en_frac = float(lang_dist.get("en", 0.0))
    complexity_reliable = (en_frac >= 0.50)

    # Step 3 — Get mBERT coherence score (use top 20 representative texts)
    coherence = _compute_coherence(texts[:20])

    # Step 4 — Compute risk score (redistributes weights if complexity_reliable is False)
    risk_score = _compute_risk_score(features, coherence, complexity_reliable=complexity_reliable)

    # Step 5 — Map to class
    risk_class, confidence = _score_to_class(risk_score)

    return {
        "risk_class":            risk_class,       # HC, MCI, AD_Risk
        "risk_score":            risk_score,        # 0.0 to 1.0
        "confidence":            confidence,        # 0.0 to 1.0
        "ttr":                   features["ttr"],
        "complexity":            features["complexity_score"],
        "complexity_reliable":   complexity_reliable,
        "coherence":             coherence,
        "repetition":            features["repetition_score"],
        "avg_sent_length":       features["avg_sentence_length"],
        "avg_word_length":       features["avg_word_length"],
        "sample_count":          features["sample_count"],
        "language_distribution": lang_dist,
    }


def classify_risk_by_period(samples: list[dict]) -> dict:
    """
    Run classify_risk() separately for each time window instead of
    producing one risk score from all-time data combined.
    """
    from modules.nlp.extractor import bucket_samples_by_period

    buckets = bucket_samples_by_period(samples)

    results = {}
    for period, period_samples in buckets.items():
        if not period_samples:
            continue
        # Stratify sample each window to prevent bottlenecks on deep historical archives
        period_stratified, _ = stratified_sample_by_time(
            period_samples,
            max_samples=MAX_NLP_SAMPLES_PER_PERIOD
        )
        texts = [s["text"] for s in period_stratified if s.get("text")]
        if not texts:
            continue
        period_result = classify_risk(
            texts,
            max_samples=MAX_NLP_SAMPLES_PER_PERIOD,
            warn_if_few=False
        )
        period_result["sample_count_in_period"] = len(period_samples)
        results[period] = period_result

    return results


# ─────────────────────────────────────────────
# mBERT COHERENCE
# ─────────────────────────────────────────────

def _compute_word_coherence(texts: list[str]) -> float:
    """Fallback word-level Jaccard semantic coherence when mBERT is unavailable."""
    if len(texts) < 2:
        return 0.5
    sims = []
    for i in range(len(texts) - 1):
        w1 = set(texts[i].lower().split())
        w2 = set(texts[i + 1].lower().split())
        if not w1 or not w2:
            sims.append(0.5)
            continue
        jaccard = len(w1 & w2) / float(len(w1 | w2))
        sims.append(jaccard)
    return round(float(np.mean(sims)), 4)


_COHERENCE_CACHE: dict[tuple[str, ...], float] = {}

def _compute_coherence(texts: list[str]) -> float:
    """
    Measures semantic coherence using mBERT embeddings.
    Compares consecutive texts — higher similarity = more coherent.
    Uses batch processing & memoization for high throughput.
    """
    valid_texts = [t for t in texts[:15] if len(t.strip()) >= 3]  # 15 is sufficient for stable coherence
    if len(valid_texts) < 2:
        return 0.5

    cache_key = tuple(valid_texts)
    if cache_key in _COHERENCE_CACHE:
        return _COHERENCE_CACHE[cache_key]

    try:
        tok, mod = get_mbert()
        if tok is None or mod is None:
            res = _compute_word_coherence(valid_texts)
            _COHERENCE_CACHE[cache_key] = res
            return res

        inputs = tok(
            valid_texts,
            return_tensors="pt",
            truncation=True,
            max_length=128,
            padding=True
        )
        with torch.inference_mode():
            outputs = mod(**inputs)
        embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
    except Exception as e:
        print(f"[LUMINA] mBERT batch error: {e}")
        res = _compute_word_coherence(valid_texts)
        _COHERENCE_CACHE[cache_key] = res
        return res

    if len(embeddings) < 2:
        return 0.5

    # Compute cosine similarity between consecutive embeddings
    similarities = []
    for i in range(len(embeddings) - 1):
        a, b = embeddings[i], embeddings[i + 1]
        sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)
        similarities.append(float(sim))

    res = round(float(np.mean(similarities)), 4)
    _COHERENCE_CACHE[cache_key] = res
    return res


# ─────────────────────────────────────────────
# RISK SCORING
# ─────────────────────────────────────────────

def compute_ttr_risk(ttr: float) -> float:
    """
    Piece-wise linear TTR risk mapping calibrated to clinical boundaries:
    - TTR >= 0.72: Healthy (risk 0.0 - 0.10)
    - TTR 0.55 - 0.72: MCI range (risk 0.10 - 0.65)
    - TTR < 0.55: AD_Risk range (risk 0.65 - 1.00)
    """
    if ttr >= 0.72:
        return max(0.0, (0.75 - ttr) * 3.33)
    elif ttr >= 0.55:
        return 0.10 + (0.72 - ttr) / 0.17 * 0.55
    else:
        return min(1.0, 0.65 + (0.55 - ttr) / 0.25 * 0.35)


def _compute_risk_score(features: dict, coherence: float, complexity_reliable: bool = True) -> float:
    """
    Combines all features into a single 0-1 risk score.
    Higher score = higher risk.
    """
    ttr = features.get("ttr", 0.5)
    complexity = features.get("complexity_score", 0.0)
    repetition = features.get("repetition_score", 0.0)

    # 1. TTR Risk: piece-wise clinical calibration
    ttr_risk = compute_ttr_risk(ttr)

    # 2. Coherence Risk: perseveration penalty for verbatim phrase repetition
    effective_coherence = coherence * max(0.0, 1.0 - 2.0 * repetition)
    coherence_risk = min(1.0, max(0.0, (1.0 - effective_coherence) * 2.5))
    if repetition > 0.12:
        coherence_risk = max(coherence_risk, min(1.0, repetition * 3.0))

    # 3. Complexity Risk: lower complexity = higher risk (social media baseline ~0.12)
    complexity_risk = min(1.0, max(0.0, 1.0 - complexity / 0.12))

    # 4. N-gram Repetition Risk: higher repetition = higher risk
    repetition_risk = min(1.0, max(0.0, repetition * 4.0))

    if complexity_reliable:
        # Base weights for English-dominant text (sum = 1.0)
        w_ttr = 0.50
        w_coh = 0.20
        w_comp = 0.15
        w_rep = 0.15

        risk_score = (
            ttr_risk * w_ttr +
            coherence_risk * w_coh +
            complexity_risk * w_comp +
            repetition_risk * w_rep
        )
    else:
        # For non-English / Romanized Sinhala text, exclude unreliable complexity_risk
        w_sum = 0.50 + 0.20 + 0.15
        w_ttr = 0.50 / w_sum
        w_coh = 0.20 / w_sum
        w_rep = 0.15 / w_sum

        risk_score = (
            ttr_risk * w_ttr +
            coherence_risk * w_coh +
            repetition_risk * w_rep
        )

    return round(min(max(risk_score, 0.0), 1.0), 4)


def _score_to_class(score: float) -> tuple[str, float]:
    """
    Maps risk score to class. Thresholds live in
    modules/config/thresholds.py (RISK_CLASS_THRESHOLDS).
    """
    from modules.config.thresholds import RISK_CLASS_THRESHOLDS

    if score < RISK_CLASS_THRESHOLDS["HC_MAX"]:
        return "HC", round(1.0 - score, 3)        # Healthy Control
    elif score < RISK_CLASS_THRESHOLDS["MCI_MAX"]:
        # Mild Cognitive Impairment
        return "MCI", round(1.0 - abs(score - 0.5), 3)
    else:
        return "AD_Risk", round(score, 3)          # High Risk


def _empty_result() -> dict:
    return {
        "risk_class": "HC",
        "risk_score": 0.0,
        "confidence": 0.0,
        "ttr": 0.0,
        "complexity": 0.0,
        "coherence": 0.0,
        "repetition": 0.0,
        "avg_sent_length": 0.0,
        "avg_word_length": 0.0,
        "sample_count": 0,
    }


# ─────────────────────────────────────────────
# SAVE TO DB
# ─────────────────────────────────────────────

def save_classification_to_db(result: dict, session_id: int):
    """Save classification result to nlp_scores table."""
    from database.connection import get_connection, release_connection

    conn = get_connection()
    if not conn:
        return

    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE nlp_scores
            SET risk_class = %s,
                confidence_score = %s,
                coherence_score = %s
            WHERE session_id = %s
        """, (
            result["risk_class"],
            result["confidence"],
            result["coherence"],
            session_id
        ))
        conn.commit()
        print(f"[LUMINA] Classification saved: {result['risk_class']} "
              f"(score: {result['risk_score']}, confidence: {result['confidence']})")
    except Exception as e:
        print(f"[LUMINA] DB error: {e}")
        conn.rollback()
    finally:
        if cur:
            cur.close()
        release_connection(conn)


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    from database.connection import get_connection, release_connection

    print("Loading samples from database...")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT text_content FROM text_samples WHERE session_id = 1")
    texts = [r[0] for r in cur.fetchall()]
    cur.close()
    release_connection(conn)

    print(f"Classifying {len(texts)} samples...\n")
    result = classify_risk(texts)

    print("=" * 50)
    print("LUMINA RISK CLASSIFICATION RESULT")
    print("=" * 50)
    for key, value in result.items():
        print(f"  {key}: {value}")

    save_classification_to_db(result, session_id=1)
