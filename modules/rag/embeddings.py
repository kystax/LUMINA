"""
LUMINA - RAG Knowledge Base
Stores research-backed facts about cognitive decline indicators.
"""

KNOWLEDGE_BASE = [
    {
        "id": "ttr_001",
        "topic": "ttr",
        "risk_level": "MCI",
        "title": "Vocabulary Richness and Cognitive Decline",
        "content": (
            "Type-Token Ratio (TTR) measures vocabulary richness. "
            "Research shows that individuals in early stages of cognitive decline "
            "show a measurable reduction in vocabulary diversity. "
            "A TTR below 0.30 in natural speech has been associated with "
            "early cognitive changes. Social media text naturally shows lower TTR "
            "than clinical speech, so longitudinal comparison is essential."
        ),
        "source": "Peled-Cohen & Reichart, TACL 2025"
    },
    {
        "id": "ttr_002",
        "topic": "ttr",
        "risk_level": "AD",
        "title": "Severe Vocabulary Decline in Alzheimer's",
        "content": (
            "Studies on the DementiaBank Pitt corpus show that individuals "
            "with Alzheimer's Disease produce significantly lower TTR scores "
            "compared to healthy controls during picture description tasks. "
            "Vocabulary simplification — using basic words instead of specific nouns — "
            "is one of the earliest detectable linguistic markers."
        ),
        "source": "Fraser et al., 2016; Luz et al., ADReSS 2020"
    },
    {
        "id": "complexity_001",
        "topic": "complexity",
        "risk_level": "MCI",
        "title": "Sentence Complexity in Early Cognitive Decline",
        "content": (
            "Syntactic complexity — measured by subordinating conjunctions and "
            "clause depth — tends to decline in individuals with MCI. "
            "Shorter, simpler sentences and reduced use of complex grammatical "
            "structures are associated with early cognitive changes. "
            "This pattern appears in both clinical speech and everyday online communication."
        ),
        "source": "Roark et al., 2011; Jarrold et al., 2014"
    },
    {
        "id": "coherence_001",
        "topic": "coherence",
        "risk_level": "MCI",
        "title": "Semantic Coherence as a Biomarker",
        "content": (
            "Semantic coherence — how logically connected consecutive utterances are — "
            "is a sensitive marker of early cognitive decline. "
            "mBERT-based coherence scoring can detect subtle disconnects in meaning "
            "across messages that may not be obvious to human readers. "
            "Research shows coherence scores below 0.60 in extended text samples "
            "correlate with early cognitive risk."
        ),
        "source": "Colla et al., AI in Medicine 2022"
    },
    {
        "id": "coherence_002",
        "topic": "coherence",
        "risk_level": "AD",
        "title": "Referential Specificity Loss",
        "content": (
            "A loss of referential specificity — using vague terms like 'that thing' "
            "or 'you know' instead of specific nouns — is a hallmark of Alzheimer's. "
            "This reflects difficulty in word retrieval and results in measurably "
            "lower semantic coherence scores in NLP analysis."
        ),
        "source": "Bucks et al., 2000; Forbes-McKay & Venneri, 2005"
    },
    {
        "id": "social_001",
        "topic": "withdrawal",
        "risk_level": "MCI",
        "title": "Social Withdrawal as Early Warning",
        "content": (
            "Social withdrawal — reduced interaction frequency and network size — "
            "is one of the first behavioral signs of early cognitive decline. "
            "Studies show that individuals in pre-clinical Alzheimer's stages "
            "reduce their social media activity and messaging frequency "
            "months to years before clinical diagnosis."
        ),
        "source": "Seabrook et al., 2016; Dodge et al., 2014"
    },
    {
        "id": "social_002",
        "topic": "withdrawal",
        "risk_level": "AD",
        "title": "Network Isolation in Alzheimer's",
        "content": (
            "As Alzheimer's progresses, individuals show marked reduction in "
            "active social contacts and interaction diversity. "
            "Word-finding difficulties cause embarrassment leading to "
            "avoidance of social communication — creating a measurable pattern "
            "in digital social behavior data."
        ),
        "source": "Pickett et al., JMIR Aging 2024"
    },
    {
        "id": "repetition_001",
        "topic": "repetition",
        "risk_level": "MCI",
        "title": "Word Repetition and Memory Decline",
        "content": (
            "Increased word repetition — using the same words frequently — "
            "reflects reduced working memory capacity and word retrieval difficulty. "
            "High repetition scores combined with low vocabulary diversity "
            "form a pattern associated with early cognitive changes in NLP research."
        ),
        "source": "Wankerl et al., Interspeech 2017"
    },
    {
        "id": "multilingual_001",
        "topic": "multilingual",
        "risk_level": "HC",
        "title": "Multilingual Context in Dementia Detection",
        "content": (
            "Most dementia detection research uses English clinical data. "
            "In multilingual contexts like Sri Lanka — where Sinhala, Tamil, "
            "and Romanized Sinhala code-switching are common — standard NLP models "
            "may underperform. mBERT provides multilingual support that "
            "enables analysis across these language varieties, though "
            "Romanized Sinhala code-switching remains an open research challenge."
        ),
        "source": "Luz et al., ICASSP 2023; MultiConAD 2025"
    },
    {
        "id": "longitudinal_001",
        "topic": "longitudinal",
        "risk_level": "HC",
        "title": "Importance of Longitudinal Tracking",
        "content": (
            "A single snapshot of language or social behavior has limited "
            "diagnostic value. The key signal is CHANGE over time — "
            "comparing the same individual across multiple sessions months apart. "
            "Research shows longitudinal language tracking can predict "
            "Alzheimer's onset up to 15 years before clinical diagnosis."
        ),
        "source": "Snowdon et al., 1996; Berrios, arXiv 2024"
    },
    {
        "id": "disclaimer_001",
        "topic": "disclaimer",
        "risk_level": "HC",
        "title": "Important Limitations",
        "content": (
            "LUMINA provides computational risk indicators only — not medical diagnosis. "
            "Social media language is influenced by many factors unrelated to cognition: "
            "mood, education level, language background, autocorrect, and communication style. "
            "Results should be interpreted by qualified healthcare professionals "
            "alongside clinical assessment. Digital biomarkers require validation "
            "against clinical standards before use in medical decision-making."
        ),
        "source": "Berrios, arXiv 2024; LUMINA Project Guidelines"
    },
    {
        "id": "exercise_001",
        "topic": "intervention",
        "risk_level": "MCI",
        "title": "Physical Exercise and Cognitive Protection",
        "content": (
            "Aerobic exercise is one of the most evidence-backed interventions for reducing "
            "Alzheimer's risk. Studies show that 150 minutes of moderate aerobic exercise per week "
            "— such as brisk walking, swimming, or cycling — reduces dementia risk by up to 45%. "
            "Exercise increases BDNF (brain-derived neurotrophic factor), which supports neuron "
            "growth and connectivity. Even a 30-minute daily walk significantly reduces risk."
        ),
        "source": "Livingston et al., Lancet 2020; Hamer & Chida, Psychological Medicine 2009"
    },
    {
        "id": "exercise_002",
        "topic": "intervention",
        "risk_level": "MCI",
        "title": "Cognitive Training and Mental Stimulation",
        "content": (
            "Cognitive reserve — built through education, mentally stimulating activities, and "
            "lifelong learning — significantly delays the onset of Alzheimer's symptoms. "
            "Activities such as reading, learning a new language, playing a musical instrument, "
            "chess, and puzzle-solving have all shown protective effects. "
            "The ACTIVE trial showed that cognitive training maintained thinking skills for up to 10 years."
        ),
        "source": "Willis et al., JAMA 2006; Stern, Lancet Neurology 2012"
    },
    {
        "id": "diet_001",
        "topic": "intervention",
        "risk_level": "MCI",
        "title": "Diet and Brain Health — MIND Diet",
        "content": (
            "The MIND diet (Mediterranean-DASH Intervention for Neurodegenerative Delay) "
            "combines elements of Mediterranean and DASH diets. It emphasises green leafy "
            "vegetables, berries, nuts, olive oil, whole grains, fish, and beans while limiting "
            "red meat, butter, cheese, pastries, and fried foods. "
            "Research shows it reduces Alzheimer's risk by up to 53% when followed strictly, "
            "and 35% when followed moderately."
        ),
        "source": "Morris et al., Alzheimer's & Dementia 2015"
    },
    {
        "id": "sleep_001",
        "topic": "intervention",
        "risk_level": "MCI",
        "title": "Sleep Quality and Alzheimer's Prevention",
        "content": (
            "During sleep, the brain's glymphatic system clears amyloid-beta and tau proteins — "
            "the key biomarkers of Alzheimer's disease. Chronic poor sleep (under 6 hours or "
            "fragmented sleep) significantly accelerates amyloid accumulation. "
            "Studies show that people with sleep disorders have a 68% higher risk of developing "
            "dementia. Targeting 7-9 hours of quality sleep per night is strongly recommended."
        ),
        "source": "Ju et al., JAMA Neurology 2014; Shi et al., Nature Communications 2017"
    },
    {
        "id": "social_003",
        "topic": "intervention",
        "risk_level": "MCI",
        "title": "Social Engagement as Cognitive Protection",
        "content": (
            "Strong social connections are consistently associated with lower dementia risk. "
            "Loneliness and social isolation increase dementia risk by up to 64%. "
            "Regular meaningful social interaction — family contact, community groups, "
            "volunteering, or religious participation — maintains cognitive function. "
            "In Sri Lanka, intergenerational family structures provide natural protection "
            "that should be maintained and encouraged."
        ),
        "source": "Livingston et al., Lancet 2020; Holwerda et al., Journal of Neurology 2014"
    },
    {
        "id": "stress_001",
        "topic": "intervention",
        "risk_level": "MCI",
        "title": "Stress Management and Cognitive Health",
        "content": (
            "Chronic psychological stress elevates cortisol levels, which damages the "
            "hippocampus — the brain region critical for memory. Mindfulness meditation, "
            "yoga, and breathing exercises have shown measurable reductions in cortisol "
            "and improvements in cognitive test scores. "
            "Even 10 minutes of daily mindfulness practice over 8 weeks shows measurable "
            "changes in brain structure in regions linked to memory and attention."
        ),
        "source": "Creswell et al., Psychological Science 2014; Hölzel et al., NeuroImage 2011"
    },
    {
        "id": "medical_001",
        "topic": "intervention",
        "risk_level": "AD",
        "title": "Medical Risk Factor Management",
        "content": (
            "Managing vascular risk factors is critical for reducing Alzheimer's risk. "
            "Hypertension in midlife increases dementia risk by 61%. Diabetes doubles the risk. "
            "Obesity, high cholesterol, and atrial fibrillation are also significant risk factors. "
            "Regular medical check-ups to monitor and control blood pressure, blood sugar, "
            "and cholesterol — combined with lifestyle interventions — substantially reduce risk. "
            "Hearing loss, if untreated, is the single largest modifiable risk factor."
        ),
        "source": "Livingston et al., Lancet 2020 (12 modifiable risk factors)"
    },

]


def load_knowledge_base_to_db():
    """Load all knowledge base entries into PostgreSQL."""
    from database.connection import get_connection, release_connection

    conn = get_connection()
    if not conn:
        return

    cur = None
    try:
        cur = conn.cursor()
        for doc in KNOWLEDGE_BASE:
            cur.execute("""
                INSERT INTO rag_documents (title, content, source, embedding_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                doc["title"],
                doc["content"],
                doc["source"],
                doc["id"]
            ))
        conn.commit()
        print(
            f"[LUMINA RAG] Loaded {len(KNOWLEDGE_BASE)} documents into knowledge base.")
    except Exception as e:
        print(f"[LUMINA RAG] DB error: {e}")
        conn.rollback()
    finally:
        if cur:
            cur.close()
        release_connection(conn)


if __name__ == "__main__":
    load_knowledge_base_to_db()
