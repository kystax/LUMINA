from datetime import datetime

from database.connection import get_connection, release_connection

# Canonical risk classes used across the dashboard. "AD" is tolerated as a
# legacy alias for "AD_Risk" in case older rows exist in the DB.
_RISK_CLASS_ALIASES = {"AD": "AD_Risk"}
_RISK_CLASSES = ("HC", "MCI", "AD_Risk")


def get_risk_distribution(user_id: int | None = None) -> dict:
    conn = get_connection()
    if not conn:
        return {k: 0 for k in _RISK_CLASSES}

    cur = None
    try:
        cur = conn.cursor()
        if user_id is not None:
            cur.execute("""
                SELECT
                    final_risk_class,
                    COUNT(*)
                FROM risk_results
                WHERE user_id = %s
                GROUP BY final_risk_class
            """, (user_id,))
        else:
            cur.execute("""
                SELECT
                    final_risk_class,
                    COUNT(*)
                FROM risk_results
                GROUP BY final_risk_class
            """)
        rows = cur.fetchall()
    except Exception as e:
        print(f"[LUMINA Dashboard] get_risk_distribution error: {e}")
        return {k: 0 for k in _RISK_CLASSES}
    finally:
        if cur:
            cur.close()
        release_connection(conn)

    data = {k: 0 for k in _RISK_CLASSES}
    for raw_risk, count in rows:
        risk_str = _RISK_CLASS_ALIASES.get(raw_risk, raw_risk) if raw_risk is not None else ""
        if risk_str in data:
            data[risk_str] += count

    return data


def get_total_analyzed_users() -> int:
    conn = get_connection()
    if not conn:
        return 0
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT user_id) FROM risk_results")
        result = cur.fetchone()
        return int(result[0]) if result and result[0] else 0
    except Exception as e:
        print(f"[LUMINA Dashboard] get_total_analyzed_users error: {e}")
        return 0
    finally:
        if cur:
            cur.close()
        release_connection(conn)


def get_total_analyses_count(user_id: int | None = None) -> int:
    conn = get_connection()
    if not conn:
        return 0
    cur = None
    try:
        cur = conn.cursor()
        if user_id is not None:
            cur.execute(
                "SELECT COUNT(*) FROM risk_results WHERE user_id = %s",
                (user_id,),
            )
        else:
            cur.execute("SELECT COUNT(*) FROM risk_results")
        result = cur.fetchone()
        return int(result[0]) if result and result[0] else 0
    except Exception as e:
        print(f"[LUMINA Dashboard] get_total_analyses_count error: {e}")
        return 0
    finally:
        if cur:
            cur.close()
        release_connection(conn)


def get_monthly_trend(months_back: int = 6, user_id: int | None = None) -> dict:
    """
    Count of HC / MCI / AD_Risk results per calendar month, for the last
    `months_back` months (including months with zero analyses).

    Returns the shape charts.make_trend() expects:
        {"months": [...], "high": [...], "medium": [...], "low": [...]}
    where high=AD_Risk, medium=MCI, low=HC.
    """
    now = datetime.now()
    year, month = now.year, now.month
    month_keys = []
    for _ in range(months_back):
        month_keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    month_keys.reverse()

    counts = {mk: {"HC": 0, "MCI": 0, "AD_Risk": 0} for mk in month_keys}

    # Compute the cutoff as a real date in Python and pass it as a plain
    # parameter — building "INTERVAL '%s months'" via psycopg2 substitution
    # breaks because %s lands inside the quoted interval literal.
    first_y, first_m = month_keys[0].split("-")
    cutoff_date = datetime(int(first_y), int(first_m), 1)

    conn = get_connection()
    if conn:
        cur = None
        try:
            cur = conn.cursor()
            if user_id is not None:
                cur.execute("""
                    SELECT
                        to_char(date_trunc('month', created_at), 'YYYY-MM') AS ym,
                        final_risk_class,
                        COUNT(*)
                    FROM risk_results
                    WHERE created_at >= %s AND user_id = %s
                    GROUP BY ym, final_risk_class
                """, (cutoff_date, user_id))
            else:
                cur.execute("""
                    SELECT
                        to_char(date_trunc('month', created_at), 'YYYY-MM') AS ym,
                        final_risk_class,
                        COUNT(*)
                    FROM risk_results
                    WHERE created_at >= %s
                    GROUP BY ym, final_risk_class
                """, (cutoff_date,))
            rows = cur.fetchall()
            for ym, risk_class, count in rows:
                risk_class = _RISK_CLASS_ALIASES.get(risk_class, risk_class)
                if ym in counts and risk_class in counts[ym]:
                    counts[ym][risk_class] += count
        except Exception as e:
            print(f"[LUMINA Dashboard] get_monthly_trend error: {e}")
        finally:
            if cur:
                cur.close()
            release_connection(conn)

    labels = []
    for mk in month_keys:
        y, m = mk.split("-")
        labels.append(datetime(int(y), int(m), 1).strftime("%b"))

    return {
        "months": labels,
        "high": [counts[mk]["AD_Risk"] for mk in month_keys],
        "medium": [counts[mk]["MCI"] for mk in month_keys],
        "low": [counts[mk]["HC"] for mk in month_keys],
    }
