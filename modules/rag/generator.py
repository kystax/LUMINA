"""
LUMINA - RAG Generator
Generates human-readable explanations from retrieved documents.
"""

from modules.rag.retriever import retrieve_relevant_docs


def generate_explanation(risk_result: dict, sna_metrics: dict | None = None) -> str:
    """
    Generate a full explanation of the risk result
    using retrieved research context.
    """
    # Merge SNA into risk result if provided
    if sna_metrics:
        risk_result = {**risk_result, **sna_metrics}

    # Retrieve relevant documents
    docs = retrieve_relevant_docs(risk_result)

    # Build explanation
    explanation = _build_explanation(risk_result, docs)
    return explanation


def _build_explanation(result: dict, docs: list[dict]) -> str:
    risk_class = result.get("risk_class", "HC")
    risk_score = result.get("risk_score", 0.0)
    confidence = result.get("confidence", 0.0)
    ttr = result.get("ttr", 0.0)
    coherence = result.get("coherence", 0.0)
    complexity = result.get("complexity", 0.0)
    repetition = result.get("repetition", 0.0)
    withdrawal = result.get("withdrawal_score", 0.0)
    sample_count = result.get("sample_count", 0)

    # ── Header ──
    lines = []
    lines.append("=" * 60)
    lines.append("LUMINA RISK ASSESSMENT REPORT")
    lines.append("=" * 60)
    lines.append("")

    # ── Risk Class ──
    class_label = {
        "HC":       "LOW RISK — Healthy Control",
        "MCI":      "MODERATE RISK — Mild Cognitive Impairment Indicators",
        "AD_Risk":  "ELEVATED RISK — Further Assessment Recommended",
        "AD":       "ELEVATED RISK — Further Assessment Recommended"
    }.get(risk_class, risk_class)

    lines.append(f"RISK CLASSIFICATION: {class_label}")
    lines.append(f"Risk Score:          {risk_score:.2f} / 1.00")
    lines.append(f"Confidence:          {confidence * 100:.1f}%")
    lines.append(f"Samples Analysed:    {sample_count}")
    lines.append("")

    # ── Feature Scores ──
    lines.append("LANGUAGE INDICATORS:")
    lines.append(f"  Vocabulary Richness (TTR):    "
                 f"{ttr:.3f}  {_score_label(ttr, higher_is_better=True)}")
    lines.append(f"  Semantic Coherence:           "
                 f"{coherence:.3f}  {_score_label(coherence, higher_is_better=True)}")
    lines.append(f"  Sentence Complexity:          "
                 f"{complexity:.3f}  {_score_label(complexity, higher_is_better=True)}")
    lines.append(f"  Word Repetition:              "
                 f"{repetition:.3f}  {_score_label(repetition, higher_is_better=False)}")
    lines.append("")

    lines.append("SOCIAL BEHAVIOR INDICATORS:")
    lines.append(f"  Social Withdrawal Score:      "
                 f"{withdrawal:.3f}  {_score_label(withdrawal, higher_is_better=False)}")
    lines.append("")

    # ── Research Context ──
    if docs:
        lines.append("RESEARCH CONTEXT:")
        lines.append("-" * 60)
        for doc in docs[:4]:  # max 4 docs
            lines.append(f"\n[{doc['title']}]")
            lines.append(doc["content"])
            lines.append(f"Source: {doc['source']}")
        lines.append("")

    # ── Recommendation ──
    lines.append("-" * 60)
    lines.append("RECOMMENDATION:")
    if risk_class == "HC":
        lines.append(
            "Current indicators are within expected range. "
            "Continue regular monitoring. Upload new data in 3-6 months "
            "to track any changes over time."
        )
    elif risk_class in ["MCI", "AD_Risk", "AD"]:
        lines.append(
            "Some indicators suggest changes worth monitoring. "
            "We recommend discussing these results with a healthcare "
            "professional. This is NOT a medical diagnosis — "
            "only a qualified clinician can assess cognitive health."
        )
    lines.append("")

    # ── Disclaimer ──
    lines.append("=" * 60)
    lines.append("IMPORTANT: LUMINA provides computational risk indicators")
    lines.append("only. This is NOT a medical diagnosis. Results must be")
    lines.append("interpreted by qualified healthcare professionals.")
    lines.append("=" * 60)

    return "\n".join(lines)


def _score_label(score: float, higher_is_better: bool) -> str:
    """Return a simple label for a score."""
    if higher_is_better:
        if score >= 0.6:
            return "[ NORMAL ]"
        elif score >= 0.3:
            return "[ MONITOR ]"
        else:
            return "[ LOW     ]"
    else:
        if score <= 0.4:
            return "[ NORMAL ]"
        elif score <= 0.7:
            return "[ MONITOR ]"
        else:
            return "[ HIGH    ]"


if __name__ == "__main__":
    from database.connection import get_connection, release_connection

    # Load results from DB
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT ttr_score, complexity_score, coherence_score,
               risk_class, confidence_score
        FROM nlp_scores WHERE session_id = 1
    """)
    nlp = cur.fetchone()

    cur.execute("""
        SELECT posting_frequency, network_size,
               interaction_diversity, withdrawal_score
        FROM sna_scores WHERE session_id = 1
    """)
    sna = cur.fetchone()
    cur.close()
    release_connection(conn)

    nlp_tuple = nlp if nlp is not None else (0, 0, 0, "HC", 0)
    risk_result = {
        "risk_class":    nlp_tuple[3],
        "risk_score":    0.5782,
        "confidence":    float(nlp_tuple[4]) if nlp_tuple[4] else 0.0,
        "ttr":           float(nlp_tuple[0]) if nlp_tuple[0] else 0.0,
        "complexity":    float(nlp_tuple[1]) if nlp_tuple[1] else 0.0,
        "coherence":     float(nlp_tuple[2]) if nlp_tuple[2] else 0.0,
        "repetition":    1 - float(nlp_tuple[0]) if nlp_tuple[0] else 0.0,
        "sample_count":  3562,
    }

    sna_metrics = {
        "posting_frequency":    float(sna[0]) if sna else 0.0,
        "network_size":         int(sna[1]) if sna else 0,
        "interaction_diversity": float(sna[2]) if sna else 0.0,
        "withdrawal_score":     float(sna[3]) if sna else 0.0,
    }

    explanation = generate_explanation(risk_result, sna_metrics)
    print(explanation)


def generate_simple_summary(risk_result: dict, sna_metrics: dict | None = None) -> dict:
    """
    Generate plain-language summary and advice using RAG.
    Returns a dict with summary text and advice list.
    """
    if sna_metrics:
        risk_result = {**risk_result, **sna_metrics}

    docs = retrieve_relevant_docs(risk_result)
    risk_class = risk_result.get("risk_class", "HC")
    ttr = risk_result.get("ttr", 0.5)
    coherence = risk_result.get("coherence", 0.5)
    complexity = risk_result.get("complexity", 0.1)
    repetition = risk_result.get("repetition", 0.5)
    withdrawal = risk_result.get("withdrawal_score", 0.0)

    # Overall message from RAG context
    overall = {
        "HC": "Based on your language and social patterns, things look within the normal range right now.",
        "MCI": "Some patterns in your writing are slightly different from what research suggests is typical.",
        "AD_Risk": "Several patterns in your writing and social behaviour stand out compared to healthy baselines.",
        "AD": "Several patterns in your writing and social behaviour stand out compared to healthy baselines."
    }.get(risk_class, "")

    # Build points from actual scores + RAG docs
    points = []

    # TTR
    ttr_doc = next(
        (d for d in docs if "vocabulary" in d["title"].lower()), None)
    if ttr < 0.25:
        text = "You used a smaller variety of words than usual."
        if ttr_doc:
            text += f" Research notes: {ttr_doc['content'][:120]}..."
        points.append(("📚 Word variety", text, "watch"))
    else:
        points.append(
            ("📚 Word variety", "Your word variety looks normal.", "good"))

    # Coherence
    if coherence < 0.6:
        points.append(("🔗 Making sense",
                       "Some messages were harder to follow — semantic coherence was below the typical range.",
                       "watch"))
    else:
        points.append(("🔗 Making sense",
                       "Your messages flow and make logical sense.",
                       "good"))

    # Repetition
    rep_doc = next(
        (d for d in docs if "repetition" in d["title"].lower()), None)
    if repetition > 0.75:
        text = "You repeated the same words more than usual."
        if rep_doc:
            text += f" Research context: {rep_doc['content'][:100]}..."
        points.append(("🔁 Repeating words", text, "watch"))
    else:
        points.append(("🔁 Repeating words",
                       "No unusual word repetition found.",
                       "good"))

    # Complexity
    comp_doc = next(
        (d for d in docs if "complexity" in d["title"].lower()), None)
    if complexity < 0.02:
        text = "Your sentences were simpler and shorter than typically expected."
        if comp_doc:
            text += f" Note: {comp_doc['content'][:100]}..."
        points.append(("✏️ Sentence style", text, "watch"))
    else:
        points.append(("✏️ Sentence style",
                       "Your sentence structure looks normal.",
                       "good"))

    # Withdrawal
    with_doc = next(
        (d for d in docs if "withdrawal" in d["title"].lower()), None)
    if withdrawal > 0.5:
        text = "Social interaction appears reduced."
        if with_doc:
            text += f" Research: {with_doc['content'][:100]}..."
        points.append(("👥 Social activity", text, "watch"))
    elif withdrawal > 0.2:
        points.append(("👥 Social activity",
                       "Social activity is slightly lower than usual.",
                       "watch"))
    else:
        points.append(("👥 Social activity",
                       "Your social interaction levels look healthy and active.",
                       "good"))

    # RAG-backed advice
    advice = _generate_rag_advice(risk_class, docs)

    return {
        "overall": overall,
        "points": points,
        "advice": advice,
        "docs_used": [d["title"] for d in docs]
    }


def _generate_rag_advice(risk_class: str, docs: list[dict]) -> list[str]:
    """Generate advice list from RAG documents + risk class."""
    base_advice = {
        "HC": [
            "💬 Stay socially connected — research shows social engagement protects cognitive health",
            "🏃 Keep up physical activity — even a 30-minute daily walk has measurable benefits",
            "🧩 Keep challenging your mind — learning new skills builds cognitive reserve",
            "📅 Check back in 6 months — longitudinal tracking is what makes LUMINA most useful",
        ],
        "MCI": [
            "🩺 Mention these results to your doctor at your next visit",
            "👥 Stay connected — social withdrawal is one of the earliest risk signals",
            "😴 Prioritise sleep — poor sleep significantly accelerates cognitive decline",
            "🥗 Eat well — a Mediterranean-style diet has strong research support",
            "🔁 Re-upload your data in 3 months to track whether patterns are changing",
        ],
        "AD_Risk": [
            "🚨 Please see a doctor soon and share this report with them",
            "📞 Talk to a trusted family member or carer about these results today",
            "🚫 Avoid alcohol and smoking — both significantly worsen cognitive decline",
            "❤️ Reduce stress — anxiety and social isolation accelerate symptoms",
            "🛡️ Early medical intervention can substantially slow progression",
        ],
        "AD": [
            "🚨 Please see a doctor soon and share this report with them",
            "📞 Talk to a trusted family member or carer about these results today",
            "🚫 Avoid alcohol and smoking — both significantly worsen cognitive decline",
            "❤️ Reduce stress — anxiety and social isolation accelerate symptoms",
            "🛡️ Early medical intervention can substantially slow progression",
        ]
    }.get(risk_class, [])

    # Enrich with RAG source citations
    enriched = []
    for item in base_advice:
        enriched.append(item)

    # Add relevant research note from docs
    long_doc = next(
        (d for d in docs if "longitudinal" in d["title"].lower()), None)
    if long_doc:
        enriched.append(
            f"📖 Research note: {long_doc['content'][:150]}... "
            f"(Source: {long_doc['source']})"
        )

    disclaimer_doc = next(
        (d for d in docs if "limitation" in d["title"].lower()), None)
    if disclaimer_doc:
        enriched.append(
            f"⚠️ Important: {disclaimer_doc['content'][:150]}..."
        )

    return enriched
