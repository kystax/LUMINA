"""
LUMINA - Social Network Analysis Module
Extracts: network size, posting frequency, interaction diversity, withdrawal score
"""

import zipfile
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime
from collections import Counter


# ─────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────

def extract_ego_network_names(zip_path: str, username: str = "user", limit: int = 20) -> list[str]:
    """
    Real DM-contact names for this person, for an ego-network visual only.

    extract_sna_metrics() deliberately strips raw contact names before
    returning (so nothing with real usernames gets persisted to the DB) —
    this is a separate, explicit path for the one place we actually want
    to show real names: an in-session visual, never written to the DB.

    Currently supports Instagram, Facebook (same inbox/<contact>/ export
    layout) and TikTok. Other platforms return an empty list rather than
    fabricating names.
    """
    with zipfile.ZipFile(zip_path, 'r') as z:
        all_files = z.namelist()
        platform = _detect_platform(all_files)

        if platform in ("instagram", "facebook"):
            names = _extract_dm_contacts(all_files)
        elif platform == "tiktok":
            data = _load_tiktok_json(z, all_files)
            names = _tiktok_get_dm_contacts(data)
        else:
            names = []

    return names[:limit]


from typing import Any

def extract_sna_metrics(zip_path: str | list | Any, username: str = "user") -> dict:
    if isinstance(zip_path, list):
        return _empty_metrics()
    with zipfile.ZipFile(zip_path, 'r') as z:
        all_files = z.namelist()
        platform = _detect_platform(all_files)
        print(f"[LUMINA SNA] Platform: {platform}")

        if platform == "instagram":
            m = _extract_instagram_sna(z, all_files, username)
        elif platform == "facebook":
            m = _extract_facebook_sna(z, all_files, username)
        elif platform == "tiktok":
            m = _extract_tiktok_sna(z, all_files, username)
        elif platform == "youtube":
            m = _extract_youtube_sna(z, all_files, username)
        elif platform == "threads":
            m = _extract_threads_sna(z, all_files, username)
        else:
            m = _extract_generic_sna(z, all_files, username)

        if m.get("network_size", 0) == 0 and m.get("dm_contact_count", 0) == 0 and m.get("comment_count", 0) == 0:
            print("[LUMINA SNA] Specific platform metrics 0; running generic SNA fallback.")
            m = _extract_generic_sna(z, all_files, username)
        return m


def _extract_youtube_sna(z, all_files, username):
    """
    YouTube doesn't expose posting/comment dates easily,
    so we use subscriptions as network size and comment count
    as a proxy for activity.
    """
    metrics = {}

    # Subscriptions = network size
    subs_count = 0
    for f in all_files:
        if "subscriptions.csv" in f.lower():
            with z.open(f) as file:
                content = file.read().decode("utf-8", errors="ignore")
                lines = [l for l in content.split("\n") if l.strip()]
                subs_count = max(len(lines) - 1, 0)  # minus header

    metrics["network_size"] = subs_count

    # Comments = activity signal
    comment_count = 0
    for f in all_files:
        if "/comments/" in f.lower() and (f.endswith(".csv") or f.endswith(".html")):
            if f.endswith(".csv"):
                with z.open(f) as file:
                    content = file.read().decode("utf-8", errors="ignore")
                    lines = [l for l in content.split("\n") if l.strip()]
                    comment_count += max(len(lines) - 1, 0)

    metrics["comment_count"] = comment_count
    metrics["dm_contact_count"] = 0  # YouTube has no DMs in export
    metrics["posting_frequency"] = comment_count / \
        12.0  # rough monthly estimate

    # Interaction diversity: comments relative to subscriptions
    metrics["interaction_diversity"] = round(
        min(comment_count / max(subs_count, 1), 1.0), 4
    )

    # Withdrawal: high if comment_count is 0 (passive consumption only)
    if comment_count == 0:
        metrics["withdrawal_score"] = 0.6  # passive viewer — moderate signal
    else:
        diversity_risk = 1.0 - min(metrics["interaction_diversity"] * 10, 1.0)
        metrics["withdrawal_score"] = round(diversity_risk * 0.7, 4)

    return metrics

# ─────────────────────────────────────────────
# INSTAGRAM SNA
# ─────────────────────────────────────────────


def _extract_instagram_sna(z, all_files, username):
    metrics = {}

    # 1 — Network size (following count)
    following = _extract_following(z, all_files)
    metrics["network_size"] = len(following)
    metrics["following_dates"] = following

    # 2 — DM network (unique people they message)
    dm_contacts = _extract_dm_contacts(all_files)
    metrics["dm_contact_count"] = len(dm_contacts)
    metrics["dm_contacts"] = dm_contacts

    # 3 — Comment activity over time
    comment_dates = _extract_comment_dates(z, all_files)
    metrics["comment_count"] = len(comment_dates)
    metrics["comment_dates"] = comment_dates

    # 4 — Posting frequency score (comments + DMs per month)
    metrics["posting_frequency"] = _compute_posting_frequency(comment_dates)

    # 5 — Interaction diversity (how many different people they interact with)
    metrics["interaction_diversity"] = _compute_interaction_diversity(
        metrics["dm_contact_count"],
        metrics["network_size"]
    )

    # 6 — Social withdrawal score
    metrics["withdrawal_score"] = _compute_withdrawal_score(metrics)

    # Clean up raw date lists before returning
    metrics.pop("following_dates", None)
    metrics.pop("comment_dates", None)
    metrics.pop("dm_contacts", None)

    return metrics


# ─────────────────────────────────────────────
# FACEBOOK SNA
# ─────────────────────────────────────────────

def _extract_facebook_sna(z, all_files, username):
    """
    Extract SNA metrics from a Facebook 'Download Your Information' export (HTML format).
    Mirrors the Instagram extractor: friends list = network size,
    DM threads = dm contacts, comments = activity signal.

    NOTE: Facebook usage norms (friend counts, active DM threads) differ a lot
    from Instagram's. _compute_withdrawal_score's thresholds were tuned on
    Instagram-shaped data and have NOT been validated against real Facebook
    exports yet. Treat withdrawal_score from this function as provisional
    until it's recalibrated against a sample of known-normal Facebook users.
    """
    metrics = {}

    # 1 — Network size (friends list)
    friends = _extract_facebook_friends(z, all_files)
    metrics["network_size"] = len(friends)

    # 2 — DM network (unique people they message)
    # same inbox/<contact>/ layout as IG
    dm_contacts = _extract_dm_contacts(all_files)
    metrics["dm_contact_count"] = len(dm_contacts)

    # 3 — Comment activity over time
    comment_dates = _extract_facebook_comment_dates(z, all_files)
    metrics["comment_count"] = len(comment_dates)

    # 4 — Posting frequency score
    metrics["posting_frequency"] = _compute_posting_frequency(comment_dates)

    # 5 — Interaction diversity
    metrics["interaction_diversity"] = _compute_interaction_diversity(
        metrics["dm_contact_count"],
        metrics["network_size"]
    )

    # 6 — Social withdrawal score (reuse Instagram weighting — see caveat above)
    metrics["withdrawal_score"] = _compute_withdrawal_score(metrics)

    return metrics


def _extract_facebook_friends(z, all_files):
    """Extract friend list from friends_and_followers/friends.html (or .json)."""
    friends = []

    for f in all_files:
        lf = f.lower()
        if "friends_and_followers/friends" in lf and lf.endswith(".html"):
            with z.open(f) as file:
                content = file.read().decode("utf-8", errors="ignore")
                dates = re.findall(
                    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+,\s+\d{4}',
                    content
                )
                friends.extend(dates)
        elif "friends_and_followers/friends" in lf and lf.endswith(".json"):
            try:
                with z.open(f) as file:
                    data = json.load(file)
                    friends_list = data.get(
                        "friends_v2", []) if isinstance(data, dict) else []
                    friends.extend(friends_list)
            except Exception:
                pass

    return friends


def _extract_facebook_comment_dates(z, all_files):
    """Extract dates of comments from comments_and_reactions/comments.html."""
    dates = []

    for f in all_files:
        lf = f.lower()
        if "comments_and_reactions" in lf and lf.endswith(".html"):
            with z.open(f) as file:
                content = file.read().decode("utf-8", errors="ignore")
                found = re.findall(
                    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d+),\s+(\d{4})',
                    content
                )
                for month, day, year in found:
                    try:
                        date = datetime.strptime(
                            f"{month} {day} {year}", "%b %d %Y")
                        dates.append(date)
                    except Exception:
                        continue

    return sorted(dates)


# ─────────────────────────────────────────────
# TIKTOK SNA
# ─────────────────────────────────────────────

def _extract_tiktok_sna(z, all_files, username):
    """
    Extract SNA metrics from a TikTok 'Download your data' export.
    TikTok's JSON export (recent format) nests everything under top-level
    keys like "Activity", "Profile", etc. Older exports vary, so we search
    by key name wherever the file lives rather than assuming one fixed path.

    NOTE: Like Facebook, TikTok's withdrawal_score reuses Instagram-tuned
    thresholds (e.g. "15+ DM contacts = healthy") which haven't been
    validated for TikTok's usage patterns (TikTok is comment/like heavy and
    DM-light compared to Instagram). Treat as provisional pending recalibration.
    """
    metrics = {}

    data = _load_tiktok_json(z, all_files)

    # 1 — Network size: following list
    following = _tiktok_get_list(data, ["Following List", "Following"])
    metrics["network_size"] = len(following)

    # 2 — DM contacts: unique chat threads/usernames
    dm_contacts = _tiktok_get_dm_contacts(data)
    metrics["dm_contact_count"] = len(dm_contacts)

    # 3 — Comment activity over time
    comment_dates = _tiktok_get_comment_dates(data)
    metrics["comment_count"] = len(comment_dates)

    # 4 — Posting frequency score
    metrics["posting_frequency"] = _compute_posting_frequency(comment_dates)

    # 5 — Interaction diversity
    metrics["interaction_diversity"] = _compute_interaction_diversity(
        metrics["dm_contact_count"],
        metrics["network_size"]
    )

    # 6 — Social withdrawal score (reuse Instagram weighting — see caveat above)
    metrics["withdrawal_score"] = _compute_withdrawal_score(metrics)

    return metrics


def _load_tiktok_json(z, all_files):
    """TikTok exports as a single user_data.json (or .txt) at the zip root, usually."""
    for f in all_files:
        lf = f.lower()
        if lf.endswith(".json") and ("user_data" in lf or "user data" in lf):
            try:
                with z.open(f) as file:
                    return json.load(file)
            except Exception:
                continue
    # Fallback: try any top-level json file
    for f in all_files:
        if f.lower().endswith(".json") and "/" not in f.strip("/"):
            try:
                with z.open(f) as file:
                    return json.load(file)
            except Exception:
                continue
    return {}


def _tiktok_find_key(d, target_keys):
    """Recursively search a nested dict/list for the first matching key (case-insensitive)."""
    if isinstance(d, dict):
        for k, v in d.items():
            if any(k.lower() == tk.lower() for tk in target_keys):
                return v
            found = _tiktok_find_key(v, target_keys)
            if found is not None:
                return found
    elif isinstance(d, list):
        for item in d:
            found = _tiktok_find_key(item, target_keys)
            if found is not None:
                return found
    return None


def _tiktok_get_list(data, target_keys):
    result = _tiktok_find_key(data, target_keys)
    if result is None:
        return []
    if isinstance(result, dict):
        # commonly nested under e.g. {"Following": {"FollowingList": [...]}}
        for v in result.values():
            if isinstance(v, list):
                return v
        return []
    if isinstance(result, list):
        return result
    return []


def _tiktok_get_dm_contacts(data):
    """Unique chat partners from Direct Messages / Chat History."""
    contacts = set()
    chat_data = _tiktok_find_key(
        data, ["Chat History", "Direct Messages", "ChatHistory"])

    if isinstance(chat_data, dict):
        for v in chat_data.values():
            if isinstance(v, dict):
                for thread_name in v.keys():
                    contacts.add(thread_name)
            elif isinstance(v, list):
                for entry in v:
                    if isinstance(entry, dict):
                        name = entry.get("From") or entry.get("from")
                        if name:
                            contacts.add(name)

    return list(contacts)


def _tiktok_get_comment_dates(data):
    """Extract dates from comment history."""
    dates = []
    comments = _tiktok_find_key(data, ["Comment", "Comments", "CommentsList"])

    raw_entries = []
    if isinstance(comments, dict):
        for v in comments.values():
            if isinstance(v, list):
                raw_entries.extend(v)
    elif isinstance(comments, list):
        raw_entries = comments

    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        date_str = entry.get("date") or entry.get(
            "Date") or entry.get("comment_time")
        if not date_str:
            continue
        parsed = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%b %d, %Y"):
            try:
                parsed = datetime.strptime(date_str, fmt)
                break
            except Exception:
                continue
        if parsed:
            dates.append(parsed)

    return sorted(dates)


def _extract_threads_sna(z, all_files, username):
    """
    Extract SNA metrics from Threads export.
    Threads has followers, following, and posts data.
    """
    metrics = {}

    # Count followers/following as network size
    network_size = 0
    for f in all_files:
        if "followers" in f.lower() and f.endswith(".json"):
            try:
                with z.open(f) as file:
                    data = json.load(file)
                    if isinstance(data, list):
                        network_size += len(data)
                    elif isinstance(data, dict):
                        for key in data:
                            if isinstance(data[key], list):
                                network_size += len(data[key])
            except Exception:
                pass

    metrics["network_size"] = network_size

    # Count posts as activity signal
    post_count = 0
    for f in all_files:
        if "post" in f.lower() and f.endswith(".json"):
            try:
                with z.open(f) as file:
                    data = json.load(file)
                    if isinstance(data, list):
                        post_count += len(data)
            except Exception:
                pass

    metrics["comment_count"] = post_count
    metrics["dm_contact_count"] = 0
    metrics["posting_frequency"] = round(post_count / 12.0, 4)
    metrics["interaction_diversity"] = round(
        min(post_count / max(network_size, 1), 1.0), 4
    )

    # Withdrawal: only flag if they USED to be active but stopped
    # A new/passive account with 0 posts is not withdrawal
    if network_size == 0 and post_count == 0:
        metrics["withdrawal_score"] = 0.1  # new/passive — not withdrawn
    elif post_count == 0:
        metrics["withdrawal_score"] = 0.3  # has network but never posts
    else:
        diversity_risk = 1.0 - min(metrics["interaction_diversity"] * 5, 1.0)
        freq_risk = 1.0 - min(post_count / 20.0, 1.0)
        metrics["withdrawal_score"] = round(
            diversity_risk * 0.6 + freq_risk * 0.4, 4
        )

    return metrics
# ─────────────────────────────────────────────
# EXTRACTORS
# ─────────────────────────────────────────────


def _extract_following(z, all_files):
    """Extract list of accounts being followed with dates (supports HTML & JSON)."""
    following = []
    for f in all_files:
        lf = f.lower()
        if ("following" in lf or "friends" in lf or "subscriptions" in lf):
            if lf.endswith(".html"):
                try:
                    with z.open(f) as file:
                        content = file.read().decode("utf-8", errors="ignore")
                        dates = re.findall(
                            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+,\s+\d{4}',
                            content
                        )
                        following.extend(dates if dates else ["item"] * max(len(content.splitlines()) // 3, 1))
                except Exception:
                    pass
            elif lf.endswith(".json"):
                try:
                    with z.open(f) as file:
                        data = json.load(file)
                        if isinstance(data, list):
                            following.extend(data)
                        elif isinstance(data, dict):
                            for v in data.values():
                                if isinstance(v, list):
                                    following.extend(v)
                except Exception:
                    pass
    return following


def _extract_dm_contacts(all_files):
    """Count unique DM conversations across HTML and JSON files."""
    contacts = set()
    for f in all_files:
        lf = f.lower()
        if "messages/inbox/" in lf or "direct_messages" in lf:
            parts = f.split("/")
            for i, part in enumerate(parts):
                if part.lower() in ("inbox", "direct_messages") and i + 1 < len(parts):
                    contact_folder = parts[i + 1]
                    contact_name = re.sub(r'_\d+$', '', contact_folder)
                    if contact_name and contact_name.lower() not in ("message_1.json", "message_1.html"):
                        contacts.add(contact_name)
    return list(contacts)


def _extract_comment_dates(z, all_files):
    """Extract dates of actual comments/posts made by user across HTML and JSON files."""
    dates = []
    seen_dates = set()

    for f in all_files:
        lf = f.lower()
        if "comments" in lf or "posts" in lf:
            if lf.endswith(".html"):
                try:
                    content = z.open(f).read().decode("utf-8", errors="ignore")
                    found = re.findall(
                        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d+),\s+(\d{4})',
                        content
                    )
                    for month, day, year in found:
                        key = f"{month} {day} {year}"
                        if key not in seen_dates:
                            seen_dates.add(key)
                            try:
                                date = datetime.strptime(key, "%b %d %Y")
                                dates.append(date)
                            except Exception:
                                pass
                except Exception:
                    pass
            elif lf.endswith(".json"):
                try:
                    with z.open(f) as file:
                        data = json.load(file)
                        items = data if isinstance(data, list) else [data]
                        if len(items) > 5000:
                            items = items[-5000:]
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            ts = item.get("timestamp") or item.get("creation_timestamp") or item.get("timestamp_ms")
                            if ts:
                                try:
                                    ts_num = float(ts)
                                    if ts_num > 1e11:
                                        ts_num /= 1000.0
                                    dt = datetime.fromtimestamp(ts_num)
                                    key = dt.strftime("%Y-%m-%d %H")
                                    if key not in seen_dates:
                                        seen_dates.add(key)
                                        dates.append(dt)
                                except Exception:
                                    pass
                except Exception:
                    pass
    return sorted(dates)


def _extract_generic_sna(z, all_files, username):
    """Fallback SNA extractor scanning all archive contents."""
    following = _extract_following(z, all_files)
    dm_contacts = _extract_dm_contacts(all_files)
    comment_dates = _extract_comment_dates(z, all_files)

    net_size = len(following) if following else max(len(dm_contacts) * 2, len(comment_dates) // 2)
    dm_count = len(dm_contacts)
    comment_count = len(comment_dates)
    posting_freq = _compute_posting_frequency(comment_dates)
    if posting_freq == 0.0 and comment_count > 0:
        posting_freq = round(comment_count / 12.0, 4)

    diversity = _compute_interaction_diversity(dm_count, net_size)

    metrics = {
        "network_size": net_size,
        "dm_contact_count": dm_count,
        "comment_count": comment_count,
        "posting_frequency": posting_freq,
        "interaction_diversity": diversity,
    }
    metrics["withdrawal_score"] = _compute_withdrawal_score(metrics)
    return metrics


# ─────────────────────────────────────────────
# METRIC CALCULATIONS
# ─────────────────────────────────────────────

def _compute_posting_frequency(comment_dates: list) -> float:
    """
    Average comments per month.
    Declining frequency = social withdrawal signal.
    """
    if not comment_dates:
        return 0.0

    if len(comment_dates) == 1:
        return 1.0

    # Group by month
    month_counts = Counter(
        (d.year, d.month) for d in comment_dates
    )
    avg = sum(month_counts.values()) / len(month_counts)
    return round(avg, 4)


def _compute_interaction_diversity(dm_contacts: int, network_size: int) -> float:
    """
    How diverse is the social interaction?
    DM contacts / following count.
    Higher = more active social engagement.
    Lower = more passive, possible withdrawal.
    """
    if network_size == 0:
        return 0.0
    diversity = dm_contacts / max(network_size, 1)
    return round(min(diversity, 1.0), 4)


def _compute_withdrawal_score(metrics: dict) -> float:
    """
    Social withdrawal score (0-1).
    Higher = more withdrawn = higher risk signal.
    Tier breakpoints live in modules/config/thresholds.py and were
    calibrated against ad_risk_enhanced_merged_500.csv social scores.
    """
    from modules.config.thresholds import SNA_WITHDRAWAL_TIERS, SNA_WITHDRAWAL_WEIGHTS

    div_tiers = SNA_WITHDRAWAL_TIERS["diversity"]
    freq_tiers = SNA_WITHDRAWAL_TIERS["frequency"]
    dm_tiers = SNA_WITHDRAWAL_TIERS["dm_count"]

    diversity = metrics.get("interaction_diversity", 0)
    if diversity >= div_tiers["active"]:
        diversity_risk = 0.0
    elif diversity >= div_tiers["normal"]:
        diversity_risk = 0.2
    elif diversity >= div_tiers["low"]:
        diversity_risk = 0.5
    else:
        diversity_risk = 0.9

    freq = metrics.get("posting_frequency", 0)
    if freq >= freq_tiers["active"]:
        freq_risk = 0.0
    elif freq >= freq_tiers["normal"]:
        freq_risk = 0.2
    elif freq >= freq_tiers["low"]:
        freq_risk = 0.5
    else:
        freq_risk = 0.9

    dm_count = metrics.get("dm_contact_count", 0)
    if dm_count >= dm_tiers["active"]:
        dm_risk = 0.0
    elif dm_count >= dm_tiers["normal"]:
        dm_risk = 0.2
    elif dm_count >= dm_tiers["low"]:
        dm_risk = 0.5
    else:
        dm_risk = 0.9

    withdrawal = (
        diversity_risk * SNA_WITHDRAWAL_WEIGHTS["diversity"] +
        freq_risk * SNA_WITHDRAWAL_WEIGHTS["frequency"] +
        dm_risk * SNA_WITHDRAWAL_WEIGHTS["dm_count"]
    )
    return round(min(max(withdrawal, 0.0), 1.0), 4)

# ─────────────────────────────────────────────
# SAVE TO DB
# ─────────────────────────────────────────────


def save_sna_to_db(metrics: dict, session_id: int):
    """Save SNA metrics to PostgreSQL."""
    from database.connection import get_connection, release_connection

    conn = get_connection()
    if not conn:
        return

    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sna_scores
                (session_id, posting_frequency, network_size,
                 interaction_diversity, withdrawal_score, dm_contact_count)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_id) DO UPDATE SET
                posting_frequency = EXCLUDED.posting_frequency,
                network_size = EXCLUDED.network_size,
                interaction_diversity = EXCLUDED.interaction_diversity,
                withdrawal_score = EXCLUDED.withdrawal_score,
                dm_contact_count = EXCLUDED.dm_contact_count
        """, (
            session_id,
            metrics.get("posting_frequency", 0),
            metrics.get("network_size", 0),
            metrics.get("interaction_diversity", 0),
            metrics.get("withdrawal_score", 0),
            metrics.get("dm_contact_count", 0)
        ))
        conn.commit()
        print(f"[LUMINA SNA] Scores saved for session {session_id}")
    except Exception as e:
        print(f"[LUMINA SNA] DB error: {e}")
        conn.rollback()
    finally:
        if cur:
            cur.close()
        release_connection(conn)


# ─────────────────────────────────────────────
# TIME-WINDOW TRENDS
# ─────────────────────────────────────────────
# Unlike the NLP samples (which only carry a month-level date_month), the
# comment_dates extracted here are full datetime objects — so we can bucket
# by day for finer windows like "last_week". This lets us compare a
# person's recent posting/comment activity against their own older
# activity, instead of judging one all-time number against a fixed cutoff.

PERIOD_DAYS = {
    "last_week":     7,
    "last_month":    30,
    "last_3_months": 90,
    "last_6_months": 182,
    "last_year":     365,
    "last_3_years":  1095,
    "all_time":      None,
}


def _bucket_dates_by_period(dates: list) -> dict:
    """Group a list of datetime objects into overlapping time windows.
    Anchors to max date in dates list if available so historical exports bucket correctly."""
    max_d = max(dates) if dates else datetime.now()
    buckets = {name: [] for name in PERIOD_DAYS}

    for d in dates:
        buckets["all_time"].append(d)
        days_ago = (max_d - d).days
        for period, span in PERIOD_DAYS.items():
            if span is None:
                continue
            if 0 <= days_ago < span:
                buckets[period].append(d)

    return buckets


def extract_sna_trends(zip_path: str, username: str = "user") -> dict:
    """
    Like extract_sna_metrics(), but returns scores broken down by time
    window (last_week / last_month / last_6_months / last_year /
    last_3_years / all_time) instead of one fixed-snapshot score.

    Currently supports Instagram, Facebook, and TikTok — the three
    platforms where we extract dated comment/post activity. For other
    platforms, falls back to a single all_time bucket using
    extract_sna_metrics().

    IMPORTANT LIMITATION: network_size and dm_contact_count are NOT
    time-bucketed in this version. The underlying exports don't carry a
    per-contact join/message date we can reliably bucket (e.g. Instagram's
    DM folder names don't expose when a conversation started). So those
    two stay constant across every period — only comment/post activity
    (comment_count, posting_frequency, withdrawal_score) actually reflects
    the time window. Treat withdrawal_score trend as the meaningful signal
    here, not the network_size/dm_contact_count numbers repeating.
    """
    with zipfile.ZipFile(zip_path, 'r') as z:
        all_files = z.namelist()
        platform = _detect_platform(all_files)
        print(f"[LUMINA SNA] Trend analysis — platform: {platform}")

        if platform == "instagram":
            following = _extract_following(z, all_files)
            dm_contacts = _extract_dm_contacts(all_files)
            comment_dates = _extract_comment_dates(z, all_files)
            network_size = len(following)
            dm_contact_count = len(dm_contacts)
        elif platform == "facebook":
            friends = _extract_facebook_friends(z, all_files)
            dm_contacts = _extract_dm_contacts(all_files)
            comment_dates = _extract_facebook_comment_dates(z, all_files)
            network_size = len(friends)
            dm_contact_count = len(dm_contacts)
        elif platform == "tiktok":
            data = _load_tiktok_json(z, all_files)
            following = _tiktok_get_list(data, ["Following List", "Following"])
            dm_contacts = _tiktok_get_dm_contacts(data)
            comment_dates = _tiktok_get_comment_dates(data)
            network_size = len(following)
            dm_contact_count = len(dm_contacts)
        else:
            print(f"[LUMINA SNA] Trend analysis not yet supported for "
                  f"platform '{platform}' — returning single all_time bucket.")
            return {"all_time": extract_sna_metrics(zip_path, username)}

    buckets = _bucket_dates_by_period(comment_dates)

    results = {}
    for period, dates_in_period in buckets.items():
        m = {}
        m["network_size"] = network_size
        m["dm_contact_count"] = dm_contact_count
        m["comment_count"] = len(dates_in_period)
        m["posting_frequency"] = _compute_posting_frequency(dates_in_period)
        m["interaction_diversity"] = _compute_interaction_diversity(
            dm_contact_count, network_size
        )
        m["withdrawal_score"] = _compute_withdrawal_score(m)
        results[period] = m

    return results


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _detect_platform(file_list):
    joined = " ".join(file_list).lower()
    if "your_instagram_activity" in joined:
        return "instagram"
    elif "your_facebook_activity" in joined or "facebook_information" in joined:
        return "facebook"
    elif "tiktok" in joined:
        return "tiktok"
    elif "youtube and youtube music" in joined or "takeout" in joined:
        return "youtube"
    elif "threads" in joined:
        return "threads"
    return "unknown"


def _empty_metrics():
    return {
        "network_size": 0,
        "dm_contact_count": 0,
        "comment_count": 0,
        "posting_frequency": 0.0,
        "interaction_diversity": 0.0,
        "withdrawal_score": 0.0
    }


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    zip_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/insta.zip"
    username = sys.argv[2] if len(sys.argv) > 2 else "user"

    print(f"[LUMINA SNA] Analysing: {zip_path}\n")
    metrics = extract_sna_metrics(zip_path, username)

    print("\n" + "="*50)
    print("SNA METRICS RESULT")
    print("="*50)
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    save_sna_to_db(metrics, session_id=1)
