from database.connection import get_connection, release_connection


def get_latest_sna_score(user_id=None):
    """
    Latest SNA scores. If user_id is given, scoped to that user only.
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
                    s.network_size,
                    s.interaction_diversity,
                    s.withdrawal_score,
                    s.posting_frequency,
                    s.dm_contact_count
                FROM sna_scores s
                JOIN sessions ss ON ss.session_id = s.session_id
                WHERE ss.user_id = %s
                ORDER BY s.id DESC
                LIMIT 1
            """, (user_id,))
        else:
            cur.execute("""
                SELECT
                    network_size,
                    interaction_diversity,
                    withdrawal_score,
                    posting_frequency,
                    dm_contact_count
                FROM sna_scores
                ORDER BY id DESC
                LIMIT 1
            """)

        row = cur.fetchone()
        if not row:
            return {}

        return {
            "Network Size": row[0],
            "Interaction Diversity": row[1],
            "Isolation Index": row[2],
            "Posting Frequency": row[3],
            "DM Contacts": row[4],
        }
    except Exception as e:
        print(f"[LUMINA SNA Service] get_latest_sna_score error: {e}")
        return {}
    finally:
        if cur:
            cur.close()
        release_connection(conn)
