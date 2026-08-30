"""
LUMINA - Universal Social Media Data Extractor
Supports: Instagram, Facebook, YouTube, TikTok, Threads, CSV, TXT
With date extraction for longitudinal analysis
"""

import zipfile
import os
import csv
import io
import re
import sys
import html
from datetime import datetime

def _fast_html_to_text(html_bytes: bytes) -> list[str]:
    text_content = html_bytes.decode("utf-8", errors="ignore")
    cleaned = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', text_content, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<[^>]+>', '\n', cleaned)
    cleaned = html.unescape(cleaned)
    return [l.strip() for l in cleaned.splitlines() if l.strip()]

if sys.platform == "win32":
    try:
        if isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if isinstance(sys.stderr, io.TextIOWrapper):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


_SCHEMA_CHECKED = False


def extract_follower_timeline(zip_path: str) -> dict:
    """Extract follower/following timeline metadata from export ZIP."""
    try:
        if not zip_path or not os.path.exists(zip_path):
            return {"platform": "unknown", "series": {}, "empty": True}
        with zipfile.ZipFile(zip_path, 'r') as z:
            all_files = z.namelist()
            platform = _detect_platform(all_files)
            return {"platform": platform, "series": {}, "empty": True}
    except Exception:
        return {"platform": "unknown", "series": {}, "empty": True}


# ─────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────

def extract_text_samples(file_path: str, username: str = "user") -> list[dict]:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".zip":
        return _extract_from_zip(file_path, username)
    elif ext == ".csv":
        return _extract_from_csv(file_path, username)
    elif ext in [".txt", ".text"]:
        return _extract_from_txt(file_path, username)
    else:
        print(f"[LUMINA] Unsupported file type: {ext}")
        return []


def merge_text_samples(sample_groups: list[list[dict]]) -> list[dict]:
    """Flatten text samples from several exports into one analysis input.

    Ordering is preserved by upload and then by the source parser. Duplicate
    and near-duplicate text is intentionally left here because the NLP feature
    extractor already performs its own transparent de-duplication step.
    """
    merged: list[dict] = []
    for group in sample_groups or []:
        for sample in group or []:
            if isinstance(sample, dict) and sample.get("text"):
                merged.append(sample)
    return merged


# ─────────────────────────────────────────────
# ZIP FILE HANDLER
# ─────────────────────────────────────────────

def _extract_from_zip(file_path: str, username: str) -> list[dict]:
    samples = []
    with zipfile.ZipFile(file_path, 'r') as z:
        all_files = z.namelist()
        # Fast filter: skip photos, videos, and media files immediately
        TEXT_EXTENSIONS = ('.json', '.html', '.htm', '.txt', '.csv')
        text_files = [f for f in all_files if f.lower().endswith(TEXT_EXTENSIONS)]
        
        platform = _detect_platform(text_files or all_files)
        print(f"[LUMINA] Detected platform: {platform}")

        target_files = text_files if text_files else all_files

        if platform == "instagram":
            samples = _parse_instagram(z, target_files, username)
        elif platform == "facebook":
            samples = _parse_facebook(z, target_files, username)
        elif platform == "youtube":
            samples = _parse_youtube(z, target_files, username)
        elif platform == "tiktok":
            samples = _parse_tiktok(z, target_files, username)
        elif platform == "threads":
            samples = _parse_threads(z, target_files, username)

        if not samples:
            print("[LUMINA] Platform parser returned 0 samples. Trying generic zip parser...")
            samples = _parse_generic_zip(z, target_files, username)

    print(f"[LUMINA] Extracted {len(samples)} text samples.")

    SAMPLE_CAP = 2000
    if len(samples) > SAMPLE_CAP:
        high_priority = [s for s in samples if s.get("source_type") in ("dm_sent", "comment", "post", "threads_post")]
        low_priority = [s for s in samples if s.get("source_type") not in ("dm_sent", "comment", "post", "threads_post")]
        print(f"[LUMINA] High-priority text samples (DMs, comments, posts): {len(high_priority)}")

        if len(high_priority) >= SAMPLE_CAP:
            samples = high_priority[-SAMPLE_CAP:]
        else:
            rem = SAMPLE_CAP - len(high_priority)
            samples = high_priority + low_priority[:rem]

        print(f"[LUMINA] Capped to {len(samples)} samples (prioritizing DMs and comments).")

    return samples


def _detect_platform(file_list: list[str]) -> str:
    joined = " ".join(file_list).lower()
    if "your_instagram_activity" in joined or "instagram" in joined or "messages/inbox/" in joined or "autofill_information.json" in joined or "comments/post_comments" in joined:
        return "instagram"
    elif "your_facebook_activity" in joined or "facebook" in joined or "posts/your_posts" in joined:
        return "facebook"
    elif "youtube and youtube music" in joined or "takeout" in joined or "myactivity" in joined:
        return "youtube"
    elif "tiktok" in joined or ("direct_messages" in joined and "user_data" in joined):
        return "tiktok"
    elif "threads" in joined:
        return "threads"
    return "unknown"

# ─────────────────────────────────────────────
# DATE PARSER — shared across all platforms
# ─────────────────────────────────────────────


def _parse_date(date_str: str) -> str:
    """
    Try to parse various date formats into YYYY-MM format for grouping.
    Returns 'YYYY-MM' or empty string if unparseable.
    """
    if not date_str:
        return ""

    date_str = date_str.strip()
    formats = [
        "%b %d, %Y %I:%M %p",   # Jul 12, 2025 11:14 pm  (Instagram)
        "%b %d, %Y",             # Jul 12, 2025
        "%Y-%m-%dT%H:%M:%S",    # 2025-07-12T11:14:00    (YouTube/Facebook)
        "%Y-%m-%d %H:%M:%S",    # 2025-07-12 11:14:00
        "%Y-%m-%d",              # 2025-07-12
        "%d/%m/%Y",              # 12/07/2025             (TikTok)
        "%B %d, %Y",             # July 12, 2025
    ]

    # Normalise AM/PM
    date_str_norm = date_str.replace(" am", " AM").replace(" pm", " PM")

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str_norm, fmt)
            return dt.strftime("%Y-%m")
        except ValueError:
            continue

    # Try extracting year-month with regex as fallback
    match = re.search(r'(\d{4})[^\d](\d{2})', date_str)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    return ""


# ─────────────────────────────────────────────
# INSTAGRAM PARSER
# ─────────────────────────────────────────────

def _parse_instagram(z, all_files, username):
    samples = []

    # Pre-extract Instagram DM HTML files
    dm_html_files = [
        f for f in all_files
        if ("messages/inbox" in f.lower() or "messages/e2ee" in f.lower()) and f.lower().endswith(".html")
    ]
    if dm_html_files:
        samples += _parse_instagram_dm_all(z, dm_html_files, username)

    for f in all_files:
        lf = f.lower()
        if "comments" in lf and lf.endswith(".html"):
            samples += _parse_instagram_comments(z, f, username, "comment")
        elif "comments" in lf and lf.endswith(".json"):
            samples += _parse_json_comments(z, f, username, "instagram")
        elif ("messages/inbox" in lf or "messages/e2ee" in lf) and lf.endswith(".json"):
            samples += _parse_json_messages(z, f, username, "instagram")
        elif "story_interactions" in lf and lf.endswith(".html"):
            samples += _parse_simple_html_text(z, f, username, "story_question", "instagram")
        elif "threads" in lf and lf.endswith(".html"):
            samples += _parse_simple_html_text(z, f, username, "threads_post", "threads")
        elif "posts" in lf and lf.endswith(".json"):
            samples += _parse_json_comments(z, f, username, "instagram")

    if not samples:
        samples = _parse_generic_zip(z, all_files, username)
    return samples


def _parse_json_comments(z, filepath, username, platform="instagram"):
    import json
    samples = []
    try:
        with z.open(filepath) as f:
            content = f.read().decode("utf-8", errors="ignore")
            data = json.loads(content)
            items = data if isinstance(data, list) else [data]
            if len(items) > 5000:
                items = items[-5000:]
            for item in items:
                if not isinstance(item, dict):
                    continue
                s_list = item.get("string_list_data") or []
                if isinstance(s_list, list) and s_list:
                    for entry in s_list:
                        if isinstance(entry, dict):
                            txt = entry.get("comment") or entry.get("value") or entry.get("text") or ""
                            ts = entry.get("timestamp") or entry.get("creation_timestamp") or ""
                            date_str, date_month = "", ""
                            if ts:
                                try:
                                    ts_num = float(ts)
                                    if ts_num > 1e11:
                                        ts_num /= 1000.0
                                    dt = datetime.fromtimestamp(ts_num)
                                    date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                                    date_month = dt.strftime("%Y-%m")
                                except Exception:
                                    pass
                            if _is_valid_user_text(txt):
                                samples.append({
                                    "text": txt,
                                    "source_type": "comment",
                                    "platform": platform,
                                    "date": date_str,
                                    "date_month": date_month,
                                    "username": username
                                })
                else:
                    txt = item.get("comment") or item.get("text") or item.get("value") or ""
                    ts = item.get("timestamp") or item.get("creation_timestamp") or ""
                    date_str, date_month = "", ""
                    if ts:
                        try:
                            ts_num = float(ts)
                            if ts_num > 1e11:
                                ts_num /= 1000.0
                            dt = datetime.fromtimestamp(ts_num)
                            date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                            date_month = dt.strftime("%Y-%m")
                        except Exception:
                            pass
                    if _is_valid_user_text(txt):
                        samples.append({
                            "text": txt,
                            "source_type": "comment",
                            "platform": platform,
                            "date": date_str,
                            "date_month": date_month,
                            "username": username
                        })
    except Exception as e:
        print(f"[LUMINA] Could not parse JSON comments {filepath}: {e}")
    return samples


def _parse_json_messages_all(z, json_files: list[str], username: str, platform: str = "instagram") -> list[dict]:
    """
    Extracts user-sent DM messages from Meta (Instagram/Facebook) JSON export files.
    Detects the account owner's display name across conversation subfolders so ONLY
    messages sent by the user are extracted (excluding recipient messages).
    """
    import json
    from collections import Counter

    samples = []
    file_senders = {}

    # Step 1: Detect account owner across distinct conversation folders
    for filepath in json_files:
        file_senders[filepath] = set()
        try:
            content = z.open(filepath).read().decode('utf-8', errors='ignore')
            data = json.loads(content)
            messages = data.get("messages", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for msg in messages:
                if isinstance(msg, dict):
                    sender = msg.get("sender_name") or msg.get("sender")
                    if sender:
                        file_senders[filepath].add(sender)
        except Exception:
            pass

    all_senders_flat = {s for s_set in file_senders.values() for s in s_set}

    owner_name = None
    if username and username.lower() not in ["user", "unknown"]:
        for s in all_senders_flat:
            if username.lower() in s.lower() or s.lower() in username.lower():
                owner_name = s
                break

    if not owner_name:
        sender_folders = {}
        for f, s_set in file_senders.items():
            parts = f.split('/')
            folder = f
            for i, p in enumerate(parts):
                if p.lower() in ("inbox", "archived_threads", "message_requests", "direct_messages") and i + 1 < len(parts):
                    folder = parts[i + 1]
                    break
            for s in s_set:
                sender_folders.setdefault(s, set()).add(folder)
        if sender_folders:
            owner_name = max(sender_folders.keys(), key=lambda s: len(sender_folders[s]))

    if not owner_name:
        owner_name = "user"

    print(f"[LUMINA] Identified {platform} JSON account owner: '{owner_name}' across {len(json_files)} chats")

    # Step 2: Extract ONLY messages sent by the account owner
    for filepath in json_files:
        try:
            content = z.open(filepath).read().decode('utf-8', errors='ignore')
            data = json.loads(content)
            messages = data.get("messages", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                sender = msg.get("sender_name") or msg.get("sender") or ""

                if sender.lower() == owner_name.lower() or (username and username.lower() in sender.lower() and username.lower() not in ["user", "unknown"]):
                    txt = msg.get("content") or msg.get("text") or msg.get("message") or ""
                    if not txt:
                        continue
                    try:
                        txt = txt.encode('latin-1').decode('utf-8')
                    except Exception:
                        pass

                    if _is_valid_user_text(txt) and not _is_system_message(txt):
                        ts = msg.get("timestamp_ms") or msg.get("timestamp") or ""
                        date_str, date_month = "", ""
                        if ts:
                            try:
                                ts_num = float(ts)
                                if ts_num > 1e11:
                                    ts_num /= 1000.0
                                dt = datetime.fromtimestamp(ts_num)
                                date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                                date_month = dt.strftime("%Y-%m")
                            except Exception:
                                pass
                        samples.append({
                            "text":        txt,
                            "source_type": "dm_sent",
                            "platform":    platform,
                            "date":        date_str,
                            "date_month":  date_month,
                            "username":    owner_name
                        })
        except Exception as e:
            print(f"[LUMINA] Could not parse JSON messages {filepath}: {e}")

    return samples


def _parse_json_messages(z, filepath, username, platform="instagram"):
    return _parse_json_messages_all(z, [filepath], username, platform)


def _parse_instagram_comments(z, filepath, username, source_type):
    """
    Instagram HTML pattern:
    Time → Jul 12, 2025 11:14 pm → Comment → <text> → Media Owner → <owner>
    """
    samples = []
    try:
        with z.open(filepath) as f:
            lines = _fast_html_to_text(f.read())

        i = 0
        while i < len(lines):
            if lines[i] == "Time" and i + 1 < len(lines):
                date_raw = lines[i + 1]
                if i + 2 < len(lines) and lines[i + 2] == "Comment":
                    comment_text = lines[i + 3] if i + 3 < len(lines) else ""
                    if _is_valid_user_text(comment_text):
                        samples.append({
                            "text":        comment_text,
                            "source_type": source_type,
                            "platform":    "instagram",
                            "date":        date_raw,
                            "date_month":  _parse_date(date_raw),
                            "username":    username
                        })
                    i += 4
                    continue
            i += 1
    except Exception as e:
        print(f"[LUMINA] Could not parse Instagram comments {filepath}: {e}")
    return samples


def _parse_instagram_dm_all(z, html_files: list[str], username: str) -> list[dict]:
    """
    Extracts user-sent DM messages from Instagram export HTML files.
    Automatically detects the account owner's display name across chat folders
    so ONLY messages sent by the user are extracted (excluding recipient messages).
    """
    from collections import Counter
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    samples = []
    file_senders = {}
    all_senders = Counter()
    parsed_files = {}

    # Step 1: Parse all HTML files ONCE into memory
    for filepath in html_files:
        file_senders[filepath] = set()
        file_msgs = []
        try:
            content = z.open(filepath).read().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(content, 'html.parser')
            blocks = soup.find_all('div', class_=lambda c: c and 'pam' in c)
            for b in blocks:
                h2 = b.find('h2')
                if not h2:
                    continue
                sender = h2.get_text().strip()
                file_senders[filepath].add(sender)
                all_senders[sender] += 1

                text_div = b.find('div', class_=lambda c: c and '_a6-p' in c)
                date_div = b.find('div', class_=lambda c: c and '_a6-o' in c)
                msg_text = text_div.get_text().strip() if text_div else ""
                date_raw = date_div.get_text().strip() if date_div else ""

                if _is_valid_user_text(msg_text) and not _is_system_message(msg_text):
                    file_msgs.append((sender, msg_text, date_raw))
        except Exception as e:
            print(f"[LUMINA] Could not parse Instagram DM HTML {filepath}: {e}")
        parsed_files[filepath] = file_msgs

    all_senders_flat = {s for s_set in file_senders.values() for s in s_set}

    owner_name = None
    if username and username.lower() not in ["user", "unknown"]:
        for s in all_senders_flat:
            if username.lower() in s.lower() or s.lower() in username.lower():
                owner_name = s
                break

    if not owner_name:
        sender_folders = {}
        for f, s_set in file_senders.items():
            parts = f.split('/')
            folder = f
            for i, p in enumerate(parts):
                if p.lower() in ("inbox", "archived_threads", "message_requests", "direct_messages") and i + 1 < len(parts):
                    folder = parts[i + 1]
                    break
            for s in s_set:
                sender_folders.setdefault(s, set()).add(folder)
        if sender_folders:
            owner_name = max(sender_folders.keys(), key=lambda s: len(sender_folders[s]))

    if not owner_name:
        owner_name = "user"

    print(f"[LUMINA] Identified Instagram account owner: '{owner_name}' across {len(html_files)} inbox chats")

    # Step 2: Filter messages sent ONLY by the account owner (in memory)
    for filepath, file_msgs in parsed_files.items():
        for sender, msg_text, date_raw in file_msgs:
            if sender.lower() == owner_name.lower() or (username and username.lower() in sender.lower() and username.lower() not in ["user", "unknown"]):
                samples.append({
                    "text":        msg_text,
                    "source_type": "dm_sent",
                    "platform":    "instagram",
                    "date":        date_raw,
                    "date_month":  _parse_date(date_raw),
                    "username":    owner_name
                })

    return samples


def _parse_instagram_dm(z, filepath, username):
    """
    Instagram DM HTML — extract messages sent by the user.
    """
    return _parse_instagram_dm_all(z, [filepath], username)


# ─────────────────────────────────────────────
# FACEBOOK PARSER
# ─────────────────────────────────────────────

def _parse_facebook(z, all_files, username):
    samples = []

    # Pre-extract Facebook DM JSON & HTML files across messages/inbox, archived_threads, and message_requests
    fb_json_messages = [
        f for f in all_files
        if ("messages/inbox" in f.lower() or "messages/archived" in f.lower() or "messages/message_requests" in f.lower()) and f.lower().endswith(".json")
    ]
    if fb_json_messages:
        samples += _parse_json_messages_all(z, fb_json_messages, username, "facebook")

    fb_html_messages = [
        f for f in all_files
        if ("messages/inbox" in f.lower() or "messages/archived" in f.lower() or "messages/message_requests" in f.lower()) and f.lower().endswith(".html")
    ]
    if fb_html_messages:
        samples += _parse_instagram_dm_all(z, fb_html_messages, username)

    for f in all_files:
        lf = f.lower()
        if "comments" in lf and lf.endswith(".html"):
            samples += _parse_facebook_comments(z, f, username)
        elif "comments" in lf and lf.endswith(".json"):
            samples += _parse_json_comments(z, f, username, "facebook")
        elif "posts" in lf and (lf.endswith(".html") or lf.endswith(".json")):
            if f.endswith(".html"):
                samples += _parse_simple_html_text(z, f, username, "post", "facebook")
            else:
                samples += _parse_json_comments(z, f, username, "facebook")

    if not samples:
        samples = _parse_generic_zip(z, all_files, username)
    return samples


def _parse_facebook_comments(z, filepath, username):
    """
    Facebook HTML pattern:
    <username> · <date> → <comment text>
    Date formats: "July 12, 2025" or "12 Jul 2025"
    """
    samples = []
    try:
        with z.open(filepath) as f:
            lines = _fast_html_to_text(f.read())

        current_date = ""
        for i, line in enumerate(lines):
            # Facebook date pattern: "Month DD, YYYY at HH:MM AM/PM"
            date_match = re.search(
                r'(January|February|March|April|May|June|July|August|'
                r'September|October|November|December)\s+\d{1,2},\s+\d{4}', line)
            if date_match:
                current_date = date_match.group(0)
                continue

            if _is_valid_user_text(line) and not _is_system_message(line):
                samples.append({
                    "text":        line,
                    "source_type": "comment",
                    "platform":    "facebook",
                    "date":        current_date,
                    "date_month":  _parse_date(current_date),
                    "username":    username
                })
    except Exception as e:
        print(f"[LUMINA] Could not parse Facebook comments {filepath}: {e}")
    return samples


def _parse_facebook_dm(z, filepath, username):
    samples = []
    try:
        with z.open(filepath) as f:
            lines = _fast_html_to_text(f.read())

        current_date = ""
        capture_next = False
        for line in lines:
            date_match = re.search(
                r'(January|February|March|April|May|June|July|August|'
                r'September|October|November|December)\s+\d{1,2},\s+\d{4}', line)
            if date_match:
                current_date = date_match.group(0)
                continue

            if username.lower() in line.lower():
                capture_next = True
                continue

            if capture_next:
                if _is_valid_user_text(line) and not _is_system_message(line):
                    samples.append({
                        "text":        line,
                        "source_type": "dm_sent",
                        "platform":    "facebook",
                        "date":        current_date,
                        "date_month":  _parse_date(current_date),
                        "username":    username
                    })
                capture_next = False
    except Exception as e:
        print(f"[LUMINA] Could not parse Facebook DM {filepath}: {e}")
    return samples


# ─────────────────────────────────────────────
# YOUTUBE PARSER
# ─────────────────────────────────────────────

def _parse_youtube(z, all_files, username):
    samples = []
    for f in all_files:
        if "/comments/" in f.lower() and f.endswith(".csv"):
            samples += _parse_youtube_comments_csv(z, f, username)
        elif "/comments/" in f.lower() and f.endswith(".html"):
            samples += _parse_simple_html_text(z,
                                               f, username, "comment", "youtube")
        elif "/posts/" in f.lower() and f.endswith(".html"):
            samples += _parse_simple_html_text(z,
                                               f, username, "post", "youtube")
    return samples


def _parse_youtube_comments_csv(z, filepath, username):
    """
    YouTube CSV format:
    Comment ID, Comment Text, Comment Create Timestamp, ...
    Timestamp format: 2025-07-12T11:14:00.000Z
    """
    samples = []
    try:
        with z.open(filepath) as f:
            content = f.read().decode("utf-8", errors="ignore")
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                text = ""
                date_raw = ""
                for key in row:
                    if "comment" in key.lower() and "text" in key.lower():
                        text = row[key].strip()
                    if "timestamp" in key.lower() or "date" in key.lower():
                        date_raw = row[key].strip()

                if _is_valid_user_text(text):
                    samples.append({
                        "text":        text,
                        "source_type": "comment",
                        "platform":    "youtube",
                        "date":        date_raw,
                        "date_month":  _parse_date(date_raw),
                        "username":    username
                    })
    except Exception as e:
        print(f"[LUMINA] Could not parse YouTube CSV {filepath}: {e}")
    return samples


# ─────────────────────────────────────────────
# TIKTOK PARSER
# ─────────────────────────────────────────────

def _parse_tiktok(z, all_files, username):
    """
    TikTok export format:
    Date: 2025-07-12 11:14:00
    Comment: <text>
    """
    samples = []
    for f in all_files:
        if "comment" in f.lower() and f.endswith(".txt"):
            try:
                with z.open(f) as file:
                    content = file.read().decode("utf-8", errors="ignore")
                    lines = content.split("\n")
                    current_date = ""
                    i = 0
                    while i < len(lines):
                        line = lines[i].strip()
                        if line.lower().startswith("date:"):
                            current_date = line.replace(
                                "Date:", "").replace("date:", "").strip()
                        elif line.lower().startswith("comment:"):
                            text = line.replace("Comment:", "").replace(
                                "comment:", "").strip()
                            if _is_valid_user_text(text):
                                samples.append({
                                    "text":        text,
                                    "source_type": "comment",
                                    "platform":    "tiktok",
                                    "date":        current_date,
                                    "date_month":  _parse_date(current_date),
                                    "username":    username
                                })
                        elif _is_valid_user_text(line):
                            # Fallback: no structured format
                            samples.append({
                                "text":        line,
                                "source_type": "comment",
                                "platform":    "tiktok",
                                "date":        current_date,
                                "date_month":  _parse_date(current_date),
                                "username":    username
                            })
                        i += 1
            except Exception as e:
                print(f"[LUMINA] Could not parse TikTok {f}: {e}")

        elif "direct_message" in f.lower() and f.endswith(".txt"):
            try:
                with z.open(f) as file:
                    content = file.read().decode("utf-8", errors="ignore")
                    current_date = ""
                    for line in content.split("\n"):
                        line = line.strip()
                        if line.lower().startswith("date:"):
                            current_date = line.replace(
                                "Date:", "").replace("date:", "").strip()
                        elif _is_valid_user_text(line) and not _is_system_message(line):
                            samples.append({
                                "text":        line,
                                "source_type": "dm_sent",
                                "platform":    "tiktok",
                                "date":        current_date,
                                "date_month":  _parse_date(current_date),
                                "username":    username
                            })
            except Exception as e:
                print(f"[LUMINA] Could not parse TikTok DM {f}: {e}")

    return samples


# ─────────────────────────────────────────────
# THREADS PARSER
# ─────────────────────────────────────────────


def _parse_threads(z, all_files, username):
    """
    Extract only text the user actually wrote on Threads:
    - Posts they created
    - Comments they made
    - Messages they sent
    """
    import json
    samples = []

    for f in all_files:
        # User's own posts
        if "threads/posts" in f.lower() and f.endswith(".json"):
            try:
                with z.open(f) as file:
                    data = json.load(file)
                    if isinstance(data, list):
                        for item in data:
                            text = item.get("post", {}).get("text", "")
                            if _is_valid_user_text(text):
                                samples.append({
                                    "text": text,
                                    "source_type": "post",
                                    "platform": "threads",
                                    "date": item.get("post", {}).get("creation_timestamp", ""),
                                    "username": username
                                })
            except Exception as e:
                print(f"[LUMINA] Could not parse {f}: {e}")

        # Messages sent by user
        elif "messages" in f.lower() and f.endswith(".json"):
            try:
                with z.open(f) as file:
                    data = json.load(file)
                    messages = data.get("messages", [])
                    for msg in messages:
                        if msg.get("sender_name", "").lower() == username.lower():
                            text = msg.get("content", "")
                            if _is_valid_user_text(text) and not _is_system_message(text):
                                samples.append({
                                    "text": text,
                                    "source_type": "dm_sent",
                                    "platform": "threads",
                                    "date": "",
                                    "username": username
                                })
            except Exception:
                pass

    return samples
# ─────────────────────────────────────────────
# GENERIC ZIP PARSER (fallback)
# ─────────────────────────────────────────────


def _parse_generic_zip(z, all_files, username):
    samples = []
    for f in all_files:
        if f.endswith(".html"):
            samples += _parse_simple_html_text(z, f, username, "post", "unknown")
        elif f.endswith(".txt"):
            try:
                with z.open(f) as file:
                    content = file.read().decode("utf-8", errors="ignore")
                    for line in content.split("\n"):
                        line = line.strip()
                        if _is_valid_user_text(line):
                            samples.append({
                                "text":        line,
                                "source_type": "text",
                                "platform":    "unknown",
                                "date":        "",
                                "date_month":  "",
                                "username":    username
                            })
            except Exception as e:
                print(f"[LUMINA] Could not parse {f}: {e}")
        elif f.endswith(".json"):
            try:
                import json
                with z.open(f) as file:
                    content = file.read().decode("utf-8", errors="ignore")
                    data = json.loads(content)

                    msg_list = []
                    if isinstance(data, dict):
                        if "messages" in data and isinstance(data["messages"], list):
                            msg_list = data["messages"]
                        elif "comments" in data and isinstance(data["comments"], list):
                            msg_list = data["comments"]
                    elif isinstance(data, list):
                        msg_list = data

                    if len(msg_list) > 5000:
                        msg_list = msg_list[-5000:]

                    for item in msg_list:
                        if not isinstance(item, dict):
                            continue
                        text = item.get("content") or item.get("text") or item.get("message") or item.get("comment") or ""
                        if not isinstance(text, str):
                            continue

                        # Clean up Instagram / FB Latin-1 unicode escape encoding (e.g. \u00e0)
                        try:
                            text = text.encode('latin-1').decode('utf-8')
                        except Exception:
                            pass

                        sender = item.get("sender_name", "") or item.get("sender", "") or ""
                        if not sender or username.lower() in sender.lower() or "user" in username.lower():
                            if _is_valid_user_text(text) and not _is_system_message(text):
                                ts = item.get("timestamp_ms") or item.get("timestamp") or item.get("creation_timestamp") or ""
                                date_str = ""
                                date_month = ""
                                if ts:
                                    try:
                                        if isinstance(ts, (int, float)) and ts > 1e11:
                                            ts = ts / 1000.0
                                        dt = datetime.fromtimestamp(float(ts))
                                        date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                                        date_month = dt.strftime("%Y-%m")
                                    except Exception:
                                        pass
                                samples.append({
                                    "text":        text,
                                    "source_type": "message",
                                    "platform":    "generic_json",
                                    "date":        date_str,
                                    "date_month":  date_month,
                                    "username":    username
                                })
            except Exception as e:
                print(f"[LUMINA] Could not parse generic JSON {f}: {e}")
    return samples


# ─────────────────────────────────────────────
# CSV PARSER
# ─────────────────────────────────────────────

def _extract_from_csv(file_path: str, username: str) -> list[dict]:
    samples = []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        headers = [h.lower().strip() for h in reader.fieldnames or []]

        text_col = None
        for candidate in ["text", "content", "message", "post", "comment", "transcript"]:
            if candidate in headers:
                text_col = candidate
                break

        if not text_col:
            print(
                f"[LUMINA] CSV has no recognizable text column. Found: {headers}")
            return []

        for row in reader:
            text = row.get(text_col, "").strip()
            if not _is_valid_user_text(text):
                continue
            date_raw = row.get("date", row.get("timestamp", ""))
            samples.append({
                "text":        text,
                "source_type": row.get("source_type", "csv_upload"),
                "platform":    row.get("platform", "csv"),
                "date":        date_raw,
                "date_month":  _parse_date(date_raw),
                "username":    row.get("user_id", username)
            })

    print(f"[LUMINA] Extracted {len(samples)} samples from CSV.")
    return samples


# ─────────────────────────────────────────────
# PLAIN TEXT PARSER
# ─────────────────────────────────────────────

def _extract_from_txt(file_path: str, username: str) -> list[dict]:
    samples = []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    for line in content.split("\n"):
        line = line.strip()
        if _is_valid_user_text(line):
            samples.append({
                "text":        line,
                "source_type": "text_upload",
                "platform":    "text",
                "date":        "",
                "date_month":  "",
                "username":    username
            })
    print(f"[LUMINA] Extracted {len(samples)} samples from text file.")
    return samples


# ─────────────────────────────────────────────
# HELPER — parse simple HTML
# ─────────────────────────────────────────────

def _parse_simple_html_text(z, filepath, username, source_type, platform):
    samples = []
    try:
        with z.open(filepath) as f:
            lines = _fast_html_to_text(f.read())
            for line in lines:
                if _is_valid_user_text(line) and not _is_system_message(line):
                    samples.append({
                        "text":        line,
                        "source_type": source_type,
                        "platform":    platform,
                        "date":        "",
                        "date_month":  "",
                        "username":    username
                    })
    except Exception as e:
        print(f"[LUMINA] Could not parse {filepath}: {e}")
    return samples


# ─────────────────────────────────────────────
# FILTERS
# ─────────────────────────────────────────────

_DATE_TIME_LINE_PATTERN = re.compile(
    r'^(?:'
    r'(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)?,?\s*'
    r'\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4}'
    r'|(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2},?\s+\d{4}'
    r'|\d{1,2}/\d{1,2}/\d{2,4}'
    r'|\d{4}-\d{2}-\d{2}'
    r')'
    r'(?:\s+(?:at\s+)?\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm|utc[+-]?\d{1,2}(?::\d{2})?)?)?$',
    re.IGNORECASE
)

_META_ACTION_HEADER_PATTERN = re.compile(
    r'.+?\s+commented\s+on\s+.*?(post|photo|video|comment|story)',
    re.IGNORECASE
)


def _is_valid_user_text(text: str) -> bool:
    if not text or not isinstance(text, str):
        return False
    text = text.strip()
    if len(text) < 3 or len(text) > 4000:
        return False
    if text.isdigit():
        return False
    if text.startswith("http://") or text.startswith("https://"):
        return False
    if not any(c.isalnum() for c in text):
        return False

    # Filter standalone metadata table labels, field titles, and account IDs
    text_lower = text.lower().strip()
    METADATA_LABELS = {
        "username", "url", "owner", "name", "email", "phone", "website",
        "media owner", "first name", "last name", "account", "profile",
        "title", "action", "type", "timestamp", "ip address", "browser",
        "user agent", "device", "location", "uarmyhope", "thv", "jhope",
    }
    if text_lower in METADATA_LABELS:
        return False

    # Filter standalone timestamps/date lines
    if _DATE_TIME_LINE_PATTERN.match(text):
        return False
    # Filter action titles like "User commented on a post."
    if _META_ACTION_HEADER_PATTERN.match(text):
        return False
    return True


def _is_system_message(text: str) -> bool:
    system_phrases = [
        "you sent an attachment", "liked a message", "you liked",
        "reacted to", "sent a photo", "sent a video", "sent an audio",
        "started a video chat", "missed video chat", "you unsent a message",
        "media owner", "no-data", "post comments", "login activity",
        "logout activity", "follow for more", "follow @",
        "for more information", "#comedy", "#funny", "src//",
        "https://www.instagram.com/reel",
        # Meta HTML & JSON Export Headers / Metadata
        "generated by ", "contains data that you requested",
        "your comments in", "comments in groups", "comments in groups you belong to",
        "your posts", "your comments", "your_facebook_activity", "your_instagram_activity",
        "information you requested", "data you requested", "download your information",
        "group:", "page:", "album:", "category:", "event:",
        "commented on a post", "commented on their post", "commented on your post",
        "commented on a photo", "commented on a video", "commented on a link",
        "shared a post", "shared a link", "shared a photo", "shared a video",
        "updated their status", "updated his status", "updated her status",
        "added a new photo", "added a new video",
    ]
    text_lower = text.lower().strip()
    return any(phrase in text_lower for phrase in system_phrases)


# ─────────────────────────────────────────────
# SAVE TO DB
# ─────────────────────────────────────────────

def save_samples_to_db(samples: list[dict], session_id: int):
    """Save extracted text samples, dates, and source platform to PostgreSQL."""
    from database.connection import get_connection, release_connection

    conn = get_connection()
    if not conn:
        print("[LUMINA] Could not connect to database.")
        return 0

    saved = 0
    cur = None
    global _SCHEMA_CHECKED
    try:
        cur = conn.cursor()

        if not _SCHEMA_CHECKED:
            try:
                cur.execute("ALTER TABLE text_samples ADD COLUMN IF NOT EXISTS sample_date VARCHAR(50)")
                cur.execute("ALTER TABLE text_samples ADD COLUMN IF NOT EXISTS sample_month VARCHAR(7)")
                cur.execute("ALTER TABLE text_samples ADD COLUMN IF NOT EXISTS platform VARCHAR(50)")
                conn.commit()
            except Exception:
                conn.rollback()
            _SCHEMA_CHECKED = True

        from modules.nlp.language_detect import detect_language

        # Batch insert all samples in one executemany call instead of
        # individual inserts — 10-20x faster for large exports.
        rows = []
        for sample in samples:
            lang = sample.get("language")
            if not lang:
                lang = detect_language(sample["text"])
                sample["language"] = lang
            rows.append((
                session_id,
                sample["text"],
                lang,
                sample.get("source_type", "unknown"),
                sample.get("platform", "unknown"),
                sample.get("date", ""),
                sample.get("date_month", ""),
            ))

        cur.executemany("""
            INSERT INTO text_samples
                (session_id, text_content, language_detected, source_type,
                 platform, sample_date, sample_month)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, rows)
        saved = len(rows)

        conn.commit()
        print(f"[LUMINA] Saved {saved} samples to database.")

    except Exception as e:
        print(f"[LUMINA] DB error: {e}")
        conn.rollback()
    finally:
        if cur is not None:
            cur.close()
        release_connection(conn)

    return saved


# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from collections import Counter

    test_file = sys.argv[1] if len(sys.argv) > 1 else "data/raw/instagram.zip"
    username = sys.argv[2] if len(sys.argv) > 2 else "user"

    print(f"\n[LUMINA] Testing extractor on: {test_file}\n")
    results = extract_text_samples(test_file, username)

    print(f"\n{'='*50}")
    print(f"RESULTS: {len(results)} text samples extracted")
    print(f"{'='*50}\n")

    breakdown = Counter(r["source_type"] for r in results)
    for source, count in breakdown.items():
        print(f"  {source}: {count} samples")

    # Show date distribution
    dated = [r for r in results if r.get("date_month")]
    print(f"\nSamples with dates: {len(dated)}")
    month_counts = Counter(r["date_month"] for r in dated)
    print("\nBy month:")
    for month in sorted(month_counts.keys()):
        print(f"  {month}: {month_counts[month]} samples")

    print("\nSample texts:")
    for r in results[:5]:
        print(
            f"\n  [{r['platform']}] [{r['source_type']}] [{r.get('date_month', '')}]")
        print(f"  {r['text'][:80]}")
