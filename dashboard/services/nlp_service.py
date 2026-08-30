from database.connection import get_connection, release_connection


def get_latest_nlp_score(user_id=None):
    """
    Latest NLP scores. If user_id is given, scoped to that user only —
    so a user who hasn't analyzed anything yet sees nothing instead of
    someone else's leftover results.
    """
    conn = get_connection()
    if not conn:
        return {}

    cur = None
    try:
        cur = conn.cursor()
        if user_id is not None:
            cur.execute("""
                SELECT
                    n.ttr_score,
                    n.complexity_score,
                    n.avg_word_length,
                    n.repetition_score,
                    n.confidence_score
                FROM nlp_scores n
                JOIN sessions s ON s.session_id = n.session_id
                WHERE s.user_id = %s
                ORDER BY n.id DESC
                LIMIT 1
            """, (user_id,))
        else:
            cur.execute("""
                SELECT
                    ttr_score,
                    complexity_score,
                    avg_word_length,
                    repetition_score,
                    confidence_score
                FROM nlp_scores
                ORDER BY id DESC
                LIMIT 1
            """)

        row = cur.fetchone()
        if not row:
            return {}

        return {
            "Vocabulary Richness": row[0],
            "Complexity Score": row[1],
            "Average Word Length": row[2],
            "Repeated Words": row[3],
            "Confidence": row[4],
        }
    except Exception as e:
        print(f"[LUMINA NLP Service] get_latest_nlp_score error: {e}")
        return {}
    finally:
        if cur:
            cur.close()
        release_connection(conn)
