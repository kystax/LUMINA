"""
LUMINA - Database Table Creator
Run once to set up (or upgrade) the database:
    python -m database.models
"""

import os
from database.connection import get_connection


def create_tables():
    conn = get_connection()
    if not conn:
        print("[LUMINA] Could not connect to database — check your .env file.")
        return

    try:
        cur = conn.cursor()

        # ── Run schema.sql ──────────────────────────────────────
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r") as f:
            schema_sql = f.read()

        # Execute statement by statement (handles multi-line safely)
        statements = []
        current = []
        for line in schema_sql.split("\n"):
            stripped = line.strip()
            if stripped.startswith("--") or not stripped:
                continue
            current.append(line)
            if stripped.endswith(";"):
                stmt = "\n".join(current).strip()
                if stmt and stmt != ";":
                    statements.append(stmt)
                current = []

        for stmt in statements:
            if stmt.strip():
                cur.execute(stmt)

        conn.commit()
        print("[LUMINA] Schema applied successfully.")

        # ── Verify tables ───────────────────────────────────────
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]
        print("\nTables in lumina_db:")
        expected = [
            "abm_results", "nlp_scores", "rag_documents",
            "risk_results", "sessions", "sna_scores",
            "text_samples", "users"
        ]
        for t in expected:
            status = "OK" if t in tables else "MISSING"
            print(f"  [{status}] {t}")

        # ── Seed RAG knowledge base ─────────────────────────────
        try:
            from modules.rag.embeddings import load_knowledge_base_to_db
            load_knowledge_base_to_db()
            row = cur.fetchone()
            rag_count = row[0] if row else 0
            print(f"\n  RAG documents in DB: {rag_count}")
        except Exception as e:
            print(f"\n  [WARNING] Could not seed RAG knowledge base: {e}")
            print("  Run  python -m modules.rag.embeddings  separately.")

        cur.close()
        conn.close()
        print("\n[LUMINA] Database setup complete.")

    except Exception as e:
        print(f"[LUMINA] Error during table creation: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    create_tables()
