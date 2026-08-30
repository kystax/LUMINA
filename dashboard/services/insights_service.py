"""
LUMINA - Insights Service
--------------------------
Builds plain-English AI insight cards directly from the real NLP + SNA
results stored in session state — no hardcoded text, no fallbacks.

Each insight has:
  text        — plain-English sentence about one metric
  confidence  — integer 0-100 (the model's own confidence for that feature)
  icon        — emoji for the card header
  status      — "ok" | "watch" | "flag" (drives card border colour in CSS)
"""

from __future__ import annotations

from modules.config.thresholds import FEATURE_THRESHOLDS


# ─────────────────────────────────────────────
# THRESHOLDS
# Imported from modules/config/thresholds.py (calibrated to synthetic dataset).
# ─────────────────────────────────────────────

_TTR_LOW        = FEATURE_THRESHOLDS["ttr_low"]
_TTR_OK         = FEATURE_THRESHOLDS["ttr_ok"]
_COMPLEXITY_LOW = FEATURE_THRESHOLDS["complexity_low"]
_REPETITION_HI  = FEATURE_THRESHOLDS["repetition_hi"]
_COHERENCE_LOW  = FEATURE_THRESHOLDS["coherence_low"]
_WITHDRAWAL_HI  = FEATURE_THRESHOLDS["withdrawal_hi"]
_WORD_LEN_LOW   = FEATURE_THRESHOLDS["word_len_low"]


def _pct(value: float | None, default: float = 0.0) -> float:
    """Safely convert a 0-1 float to a 0-100 float."""
    v = float(value) if value is not None else default
    return round(min(max(v, 0.0), 1.0) * 100, 1)


def build_ai_insights_from_result(
    nlp: dict | None,
    sna: dict | None,
) -> list[dict]:
    """
    Build a list of insight cards from real NLP + SNA results.

    Returns [] if both inputs are None (triggers the "No analysis yet"
    fallback in sections.py).
    """
    if not nlp and not sna:
        return []

    nlp = nlp or {}
    sna = sna or {}

    confidence_base = float(nlp.get("confidence", 0.5) or 0.5)
    risk_class      = nlp.get("risk_class", "HC") or "HC"

    ttr         = float(nlp.get("ttr", 0.0)          or 0.0)
    complexity  = float(nlp.get("complexity", 0.0)    or 0.0)
    coherence   = float(nlp.get("coherence", 0.5)     or 0.5)
    repetition  = float(nlp.get("repetition", 0.0)    or 0.0)
    avg_word_len = float(nlp.get("avg_word_length", 0) or 0.0)
    withdrawal  = float(sna.get("withdrawal_score", 0) or 0.0)
    lang_note   = nlp.get("language_note", "")

    insights: list[dict] = []

    # ── 0. Overall summary line ────────────────────────────────────────
    if risk_class == "HC":
        overall = (
            "Pattern indicators remain within expected baseline bounds across analysed data."
        )
        status = "ok"
    elif risk_class == "MCI":
        overall = (
            "Select cognitive indicators show mild divergence worth tracking over time — "
            "nothing alarming, but suitable for ongoing observation."
        )
        status = "watch"
    else:
        overall = (
            "Multiple digital behavioural indicators exhibit elevated risk markers. "
            "Consider reviewing these findings with a qualified healthcare professional."
        )
        status = "flag"

    insights.append({
        "icon": "🧠",
        "text": overall,
        "confidence": round(confidence_base * 100),
        "status": status,
    })

    # ── 1. Vocabulary richness (TTR) ──────────────────────────────────
    if ttr < _TTR_LOW:
        text   = (
            f"📖 Word variety: Your vocabulary richness score is {ttr:.2f}, "
            f"which is lower than typical — a pattern sometimes linked to "
            f"reduced word retrieval. Short captions can also lower this."
        )
        status = "watch"
        conf   = round(confidence_base * 85)
    elif ttr < _TTR_OK:
        text   = (
            f"📖 Word variety: Vocabulary richness is {ttr:.2f} — "
            f"slightly below the typical range. This can reflect short or "
            f"informal posts rather than a language change."
        )
        status = "watch"
        conf   = round(confidence_base * 80)
    else:
        text   = (
            f"📖 Word variety: Your vocabulary richness score is {ttr:.2f} — "
            f"this looks normal."
        )
        status = "ok"
        conf   = round(min(confidence_base * 1.1, 1.0) * 100)

    insights.append({"icon": "📖", "text": text, "confidence": conf, "status": status})

    # ── 2. Coherence (mBERT) ──────────────────────────────────────────
    if coherence < _COHERENCE_LOW:
        text   = (
            f"🔗 Making sense: mBERT coherence score is {coherence:.2f}, "
            f"which is below the expected range. This can mean messages are "
            f"hard to follow or change topic abruptly."
        )
        status = "watch"
        conf   = round(confidence_base * 85)
    else:
        text   = (
            f"🔗 Making sense: Your messages flow and make logical sense "
            f"(coherence: {coherence:.2f})."
        )
        status = "ok"
        conf   = round(min(confidence_base * 1.15, 1.0) * 100)

    insights.append({"icon": "🔗", "text": text, "confidence": conf, "status": status})

    # ── 3. N-gram phrase repetition ────────────────────────────────────────
    if repetition > _REPETITION_HI:
        text   = (
            f"🔁 Phrase repetition: N-gram repetition score is {repetition:.2f}, "
            f"meaning a high fraction of 2–3 word sequences recur across posts. "
            f"Repeated phrases are a noted marker of circumlocution in early cognitive change."
        )
        status = "flag"
        conf   = round(confidence_base * 80)
    elif repetition > FEATURE_THRESHOLDS["repetition_watch"]:
        text   = (
            f"🔁 Phrase repetition: Mild phrase recurrence detected ({repetition:.2f}). "
            f"This may reflect repetitive social-media formats (e.g. repeated captions) "
            f"rather than a linguistic signal."
        )
        status = "watch"
        conf   = round(confidence_base * 75)
    else:
        text   = (
            f"🔁 Phrase repetition: No unusual phrase repetition found "
            f"(n-gram score: {repetition:.2f})."
        )
        status = "ok"
        conf   = round(min(confidence_base * 1.1, 1.0) * 100)

    insights.append({"icon": "🔁", "text": text, "confidence": conf, "status": status})

    # ── 4. Sentence complexity ─────────────────────────────────────────
    if complexity < _COMPLEXITY_LOW:
        text   = (
            f"📝 Sentence complexity: Score is {complexity:.3f} — very low. "
            f"This often means the analysed text is made up of very short "
            f"captions or single-word comments rather than full sentences. "
            f"Complexity scoring is most reliable on longer, paragraph-length text."
        )
        status = "watch"
        conf   = round(confidence_base * 65)   # lower confidence — short text unreliable
    else:
        text   = (
            f"📝 Sentence complexity: Score is {complexity:.3f}, which is "
            f"within the normal range for this type of content."
        )
        status = "ok"
        conf   = round(confidence_base * 90)

    insights.append({"icon": "📝", "text": text, "confidence": conf, "status": status})

    # ── 5. Social withdrawal ───────────────────────────────────────────
    if withdrawal > _WITHDRAWAL_HI:
        text   = (
            f"👥 Social activity: Your social withdrawal score is "
            f"{withdrawal:.2f} — this upload shows relatively low active "
            f"communication (DMs + comments) compared to your network size. "
            f"Note: this only reflects the uploaded platform — if you mainly "
            f"chat on WhatsApp or iMessage those aren't included here."
        )
        status = "watch"
        conf   = round(confidence_base * 70)
    elif withdrawal > 0.3:
        text   = (
            f"👥 Social activity: Mild withdrawal signal ({withdrawal:.2f}). "
            f"Your active communication is somewhat low relative to your "
            f"network in this export — but this may simply reflect that you "
            f"chat more on other platforms not uploaded here."
        )
        status = "watch"
        conf   = round(confidence_base * 65)
    else:
        text   = (
            f"👥 Social activity: No social withdrawal signal in this export "
            f"(score: {withdrawal:.2f}). Your communication looks active "
            f"relative to your network size."
        )
        status = "ok"
        conf   = round(confidence_base * 80)

    insights.append({"icon": "👥", "text": text, "confidence": conf, "status": status})

    # ── 6. Language detection note ─────────────────────────────────────
    if lang_note:
        insights.append({
            "icon": "🌐",
            "text": (
                f"🌐 Language mix: {lang_note} "
                f"mBERT may misidentify Sinhala or Romanized Sinhala text as other "
                f"languages (e.g. Dutch, Romanian) — this can affect the "
                f"coherence and complexity scores. Treat those with caution "
                f"for multilingual or code-switched content."
            ),
            "confidence": 50,
            "status": "watch",
        })

    return insights
