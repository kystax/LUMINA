"""
LUMINA - NLP Feature Extractor
Extracts: TTR, sentence complexity, coherence, n-gram repetition
Works on: English, Sinhala, Tamil, Romanized Sinhala
"""

import re
from datetime import datetime
from modules.nlp.language_detect import detect_language
from modules.config.thresholds import FEATURE_THRESHOLDS


# ─────────────────────────────────────────────
# TIME-WINDOW BUCKETING
# ─────────────────────────────────────────────
# Samples come from modules/sna/parser.py, which already tags each sample
# with a "date_month" string (YYYY-MM). We use that to group samples into
# overlapping windows so recent activity can be compared against a
# person's own older activity, instead of producing one fixed score from
# all data lumped together.

PERIOD_MONTHS = {
    "last_week":     1,
    "last_month":    1,
    "last_3_months": 3,
    "last_6_months": 6,
    "last_year":     12,
    "last_3_years":  36,
    "all_time":      None,
}


def _month_key_to_index(date_month: str):
    """Convert 'YYYY-MM' into an absolute month index for comparison."""
    try:
        year, month = date_month.split("-")
        return int(year) * 12 + int(month)
    except Exception:
        return None


def bucket_samples_by_period(samples: list[dict]) -> dict:
    """
    Group samples (dicts with a 'text' and 'date_month' key, as produced by
    modules/sna/parser.py) into overlapping time windows.

    Anchors to the latest date in the dataset (or current date if undated)
    so historical uploads populate recent relative windows correctly.
    """
    valid_indices = []
    for s in samples:
        dm = s.get("date_month", "")
        idx = _month_key_to_index(dm) if dm else None
        if idx is not None:
            valid_indices.append(idx)

    now = datetime.now()
    now_index = now.year * 12 + now.month
    max_index = max(valid_indices) if valid_indices else now_index

    buckets = {name: [] for name in PERIOD_MONTHS}

    for s in samples:
        date_month = s.get("date_month", "")
        idx = _month_key_to_index(date_month) if date_month else None

        buckets["all_time"].append(s)

        if idx is None:
            continue  # undated sample — only counts toward all_time

        months_ago = max_index - idx
        for period, span in PERIOD_MONTHS.items():
            if span is None:
                continue
            if 0 <= months_ago < span:
                buckets[period].append(s)

    return buckets


def deduplicate_texts(texts: list[str]) -> tuple[list[str], int]:
    """
    Remove copy-pasted and near-duplicate texts before NLP analysis.
    Optimized for large datasets using set-based hashing.
    """
    if not texts:
        return texts, 0

    original_count = len(texts)

    # Step 1 — Remove exact duplicates (keep max 2 of each)
    seen = {}
    deduplicated = []
    for text in texts:
        key = text.lower().strip()
        seen[key] = seen.get(key, 0) + 1
        if seen[key] <= 2:
            deduplicated.append(text)

    # Step 2 — Fast near-duplicate removal using word-set fingerprints
    # Instead of comparing every pair, group by a fingerprint of sorted words
    fingerprint_seen = set()
    cleaned = []
    for text in deduplicated:
        words = frozenset(text.lower().split())
        if len(words) == 0:
            continue
        # Use a simplified fingerprint: sorted tuple of up to 5 most common words
        fingerprint = tuple(sorted(words))[:8]
        if fingerprint not in fingerprint_seen:
            fingerprint_seen.add(fingerprint)
            cleaned.append(text)
        elif len(cleaned) < 2:  # safety net for tiny datasets
            cleaned.append(text)

    removed = original_count - len(cleaned)
    return cleaned, removed


def extract_features(texts: list[str]) -> dict:
    """
    Takes a list of text samples from one session.
    Returns a feature dict ready for risk scoring, including a
    transparency log explaining how each score was derived.
    """
    if not texts:
        return _empty_features()

    original_count = len(texts)

    # Step 1 — Remove copy-pasted / duplicate content BEFORE analysis
    deduped_texts, duplicates_removed = deduplicate_texts(texts)

    # Step 2 — Clean remaining texts
    cleaned = [_clean_text(t) for t in deduped_texts if len(t.strip()) > 3]
    if not cleaned:
        result = _empty_features()
        result["duplicates_removed"] = duplicates_removed
        return result

    all_words = _get_all_words(cleaned)
    all_sentences = _get_all_sentences(cleaned)

    ttr = _type_token_ratio(all_words)
    avg_sent_len = _avg_sentence_length(all_sentences)
    avg_word_len = _avg_word_length(all_words)
    repetition = _repetition_score(all_words)
    complexity = _complexity_score(all_sentences)
    lang_dist = _language_distribution(cleaned)

    features = {
        "sample_count":          len(cleaned),
        "original_sample_count": original_count,
        "duplicates_removed":    duplicates_removed,
        "ttr":                   ttr,
        "avg_sentence_length":   avg_sent_len,
        "avg_word_length":       avg_word_len,
        "repetition_score":      repetition,
        "complexity_score":      complexity,
        "language_distribution": lang_dist,
        "reasoning_log":         _build_reasoning_log(
            original_count, duplicates_removed, len(cleaned),
            ttr, avg_sent_len, avg_word_len, repetition, complexity, lang_dist
        ),
    }

    return features


def extract_features_by_period(samples: list[dict]) -> dict:
    """
    Run extract_features() separately for each time window (last_month,
    last_3_months, last_6_months, last_year, last_3_years, all_time) instead
    of producing one score from all data combined.

    Takes the same 'samples' list produced by modules/sna/parser.py
    (dicts with 'text' and 'date_month'), NOT a plain list of strings.

    Returns: { period_name: { ...same keys as extract_features(), plus
                               'sample_count_in_period' } }

    A single snapshot can't tell a naturally quiet writer from someone
    whose activity is actually declining — this lets the dashboard compare
    a person's recent window against their own older windows instead of
    against one fixed universal threshold.
    """
    buckets = bucket_samples_by_period(samples)

    results = {}
    for period, period_samples in buckets.items():
        texts = [s["text"] for s in period_samples]
        period_features = extract_features(texts)
        period_features["sample_count_in_period"] = len(period_samples)
        results[period] = period_features

    return results


# ─────────────────────────────────────────────
# TRANSPARENCY / EXPLAINABILITY LOG
# ─────────────────────────────────────────────

def _build_reasoning_log(original_count, duplicates_removed, final_count,
                         ttr, avg_sent_len, avg_word_len, repetition,
                         complexity, lang_dist) -> list[str]:
    """
    Build a step-by-step, human-readable log of how the NLP module
    arrived at its feature scores. Used for transparency in the
    dashboard and the downloadable report.
    """
    log = []

    log.append(
        f"Started with {original_count} raw text samples extracted from the upload."
    )

    if duplicates_removed > 0:
        pct = round(duplicates_removed / original_count *
                    100, 1) if original_count else 0
        log.append(
            f"Removed {duplicates_removed} duplicate or near-duplicate texts "
            f"({pct}% of the original data) — likely copy-pasted content "
            f"such as voting comments or repeated captions. This prevents "
            f"artificial vocabulary-richness deflation."
        )
    else:
        log.append(
            "No significant duplicate or copy-pasted content was detected.")

    log.append(
        f"{final_count} unique samples were used for the actual analysis.")

    # TTR reasoning
    unique_words = round(ttr * (final_count if final_count else 1))
    log.append(
        f"Vocabulary Richness (TTR) = {ttr:.4f}. "
        f"Calculated as unique words ÷ total words across all samples. "
        f"{'This falls below the 0.30 research threshold associated with early cognitive changes.' if ttr < 0.30 else 'This is within the expected healthy range.'}"
    )

    # Complexity reasoning
    log.append(
        f"Sentence Complexity = {complexity:.4f}. "
        f"Calculated as the average count of complexity markers "
        f"(e.g. 'because', 'although', 'however') per sentence. "
        f"{'This is below the 0.05 threshold, suggesting simplified sentence structure — though this is also typical for casual social media text.' if complexity < 0.05 else 'This is within the expected range.'}"
    )

    # N-gram repetition reasoning
    log.append(
        f"N-gram Repetition Score = {repetition:.4f} "
        f"(fraction of 2–3 word sequences appearing more than once). "
        f"{'Above {:.2f} threshold — repeated multi-word phrases detected, which may signal circumlocution.'.format(FEATURE_THRESHOLDS['repetition_hi']) if repetition > FEATURE_THRESHOLDS.get('repetition_hi', 0.35) else 'Within normal range for social-media text.'}"
    )

    # Sentence length
    log.append(
        f"Average Sentence Length = {avg_sent_len:.2f} words per sentence — "
        f"used alongside mBERT to estimate coherence."
    )

    # Language distribution
    if lang_dist:
        top_lang = max(lang_dist.items(), key=lambda x: x[1])
        log.append(
            f"Detected language mix: {lang_dist} — dominant language: '{top_lang[0]}' "
            f"({top_lang[1]*100:.1f}% of samples). Multilingual text was processed "
            f"using mBERT, which supports cross-lingual analysis."
        )

    return log


# ─────────────────────────────────────────────
# FEATURE CALCULATIONS
# ─────────────────────────────────────────────

def _type_token_ratio(words: list[str]) -> float:
    if not words:
        return 0.0
    unique = set(w.lower() for w in words)
    return round(len(unique) / len(words), 4)


def _avg_sentence_length(sentences: list[str]) -> float:
    if not sentences:
        return 0.0
    lengths = [len(s.split()) for s in sentences if s.strip()]
    return round(sum(lengths) / len(lengths), 4) if lengths else 0.0


def _avg_word_length(words: list[str]) -> float:
    if not words:
        return 0.0
    return round(sum(len(w) for w in words) / len(words), 4)


def _repetition_score(words: list[str]) -> float:
    """
    N-gram repetition score: the fraction of bigrams (2-word sequences) and
    trigrams (3-word sequences) that appear more than once in the text.

    This is INDEPENDENT of TTR — TTR counts *unique unigrams*; this counts
    *recurring multi-word sequences*.  Repeated phrases ("I don't know what",
    "you know what I mean") are a clinically-noted marker of circumlocution
    in early cognitive decline literature, whereas a diverse vocabulary (high
    TTR) and phrase repetition can co-exist in the same text.

    Returns a value in [0.0, 1.0]: 0 = no repeated n-grams, 1 = every n-gram
    appears more than once.
    """
    if len(words) < 2:
        return 0.0

    # Collect bigrams and trigrams
    bigrams  = [tuple(words[i:i+2]) for i in range(len(words) - 1)]
    trigrams = [tuple(words[i:i+3]) for i in range(len(words) - 2)]
    ngrams   = bigrams + trigrams

    if not ngrams:
        return 0.0

    from collections import Counter
    counts  = Counter(ngrams)
    repeated = sum(1 for c in counts.values() if c > 1)
    return round(repeated / len(counts), 4)


def _complexity_score(sentences: list[str]) -> float:
    if not sentences:
        return 0.0

    complexity_markers = [
        "because", "although", "however", "therefore", "which",
        "that", "when", "while", "if", "unless", "since",
        "despite", "furthermore", "nevertheless", "consequently"
    ]

    total_markers = 0
    for sentence in sentences:
        words = sentence.lower().split()
        total_markers += sum(1 for w in words if w in complexity_markers)

    return round(total_markers / len(sentences), 4)


def _language_distribution(texts: list[str]) -> dict:
    from collections import Counter
    if not texts:
        return {}
    sample = texts[:150] if len(texts) > 150 else texts
    langs = [detect_language(t) for t in sample]
    counts = Counter(langs)
    total = len(langs) if langs else 1
    return {lang: round(count / total, 3) for lang, count in counts.items()}


# ─────────────────────────────────────────────
# TEXT PREPROCESSING
# ─────────────────────────────────────────────

def _clean_text(text: str) -> str:
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r'#(\w+)', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _get_all_words(texts: list[str]) -> list[str]:
    words = []
    for text in texts:
        words.extend(re.findall(r'[^\s\d\W_]{2,}', text.lower()))
    return words


def _get_all_sentences(texts: list[str]) -> list[str]:
    sentences = []
    for text in texts:
        parts = re.split(r'[.!?।]+', text)
        sentences.extend([p.strip() for p in parts if p.strip()])
    return sentences


def _empty_features() -> dict:
    return {
        "sample_count": 0,
        "original_sample_count": 0,
        "duplicates_removed": 0,
        "ttr": 0.0,
        "avg_sentence_length": 0.0,
        "avg_word_length": 0.0,
        "repetition_score": 0.0,
        "complexity_score": 0.0,
        "language_distribution": {},
        "reasoning_log": ["No text samples were available for analysis."]
    }


# ─────────────────────────────────────────────
# SAVE TO DB
# ─────────────────────────────────────────────

def save_features_to_db(features: dict, session_id: int):
    """Save NLP feature scores to PostgreSQL."""
    from database.connection import get_connection, release_connection

    conn = get_connection()
    if not conn:
        print("[LUMINA] Could not connect to database.")
        return

    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO nlp_scores 
                (session_id, ttr_score, complexity_score, coherence_score)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            session_id,
            features["ttr"],
            features["complexity_score"],
            features["avg_sentence_length"]
        ))
        conn.commit()
        print(f"[LUMINA] NLP scores saved for session {session_id}")
    except Exception as e:
        print(f"[LUMINA] DB error: {e}")
        conn.rollback()
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        release_connection(conn)



# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    from database.connection import get_connection, release_connection

    print("Fetching samples from database...")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT text_content FROM text_samples WHERE session_id = 1")
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)

    texts = [r[0] for r in rows]
    print(f"Loaded {len(texts)} samples\n")

    features = extract_features(texts)

    print("="*50)
    print("NLP FEATURE EXTRACTION RESULTS")
    print("="*50)
    for key, value in features.items():
        if key != "reasoning_log":
            print(f"  {key}: {value}")

    print("\nREASONING LOG:")
    for line in features.get("reasoning_log", []):
        print(f"  • {line}")

    save_features_to_db(features, session_id=1)
