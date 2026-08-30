"""
LUMINA - RAG Retriever
Retrieves relevant research documents based on risk result.
"""


def retrieve_relevant_docs(risk_result: dict) -> list[dict]:
    """
    Retrieve relevant knowledge base documents
    based on the risk classification result.
    """
    from database.connection import get_connection, release_connection

    conn = get_connection()
    if not conn:
        return []

    cur = None
    try:
        cur = conn.cursor()

        # Determine which topics are most relevant
        topics = _select_topics(risk_result)

        # Fetch matching documents
        placeholders = ','.join(['%s'] * len(topics))
        cur.execute(f"""
            SELECT title, content, source, embedding_id
            FROM rag_documents
            WHERE embedding_id = ANY(%s::text[])
            LIMIT 5
        """, (topics,))

        docs = []
        for row in cur.fetchall():
            docs.append({
                "title":   row[0],
                "content": row[1],
                "source":  row[2],
                "id":      row[3]
            })
        return docs

    except Exception as e:
        print(f"[LUMINA RAG] Retrieval error: {e}")
        return []
    finally:
        if cur:
            cur.close()
        release_connection(conn)


def _select_topics(risk_result: dict) -> list[str]:
    """Select which document IDs to retrieve based on scores."""
    topics = ["longitudinal_001", "disclaimer_001"]

    risk_class = risk_result.get("risk_class", "HC")
    ttr = risk_result.get("ttr", 0.5)
    coherence = risk_result.get("coherence", 0.5)
    repetition = risk_result.get("repetition", 0.5)
    withdrawal = risk_result.get("withdrawal_score", 0.0)
    complexity = risk_result.get("complexity", 0.1)

    # TTR based
    if ttr < 0.25:
        topics.append("ttr_002" if risk_class == "AD_Risk" else "ttr_001")

    # Coherence based
    if coherence < 0.65:
        topics.append("coherence_002" if risk_class ==
                      "AD_Risk" else "coherence_001")

    # Repetition based
    if repetition > 0.70:
        topics.append("repetition_001")

    # Withdrawal based
    if withdrawal > 0.40:
        topics.append("social_002" if risk_class ==
                      "AD_Risk" else "social_001")

    # Complexity based
    if complexity < 0.05:
        topics.append("complexity_001")

    # Always add multilingual note for Sri Lanka context
    topics.append("multilingual_001")

    return list(set(topics))  # remove duplicates
