"""
LUMINA - Language Detection
Detects: English, Sinhala, Tamil, Mixed / Romanized Sinhala
"""

from functools import lru_cache
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0  # makes results consistent


import re


@lru_cache(maxsize=4096)
def detect_language(text: str) -> str:
    """
    Returns language code:
    'en'    = English
    'si'    = Sinhala (Unicode)
    'ta'    = Tamil (Unicode)
    'mixed' = Romanized Sinhala / code-switched
    'unk'   = unknown
    """
    if not text or len(text.strip()) < 3:
        return "unk"

    # 1. Direct Unicode script detection for Sinhala & Tamil
    if re.search(r'[\u0d80-\u0dff]', text):
        return "si"
    if re.search(r'[\u0b80-\u0bff]', text):
        return "ta"

    # 2. Check if it matches Romanized Sinhala markers or heuristics
    if _is_singlish(text):
        return "mixed"

    # Fast path for standard ASCII English text
    if text.isascii():
        return "en"

    try:
        lang = detect(text)
        if lang in ["en", "si", "ta"]:
            return lang
        return lang
    except Exception:
        return "unk"


def _is_singlish(text: str) -> bool:
    """Broad heuristic & vocabulary check for Romanized Sinhala."""
    text_clean = text.lower()
    words = re.findall(r'\b[a-z]+\b', text_clean)
    if not words:
        return False

    singlish_vocab = {
        "la", "aney", "machan", "aiyo", "da", "ne", "neda", "yako", "yakow",
        "mama", "oya", "api", "eyala", "eya", "mung", "umbat", "umba", "umbath",
        "kohomada", "mokakda", "monada", "moko", "mokada", "ai", "mamat", "mamath",
        "puluwan", "hodai", "hondai", "hoda", "honda", "ekak", "eka", "ekai",
        "nikan", "gihin", "gihilla", "ennam", "enna", "yanna", "yannam", "yang",
        "gaththa", "gaththaa", "hari", "harima", "oyata", "mata", "denna", "danna",
        "wela", "welaa", "keruwa", "karala", "karanna", "karannath", "karanawada",
        "hithanawada", "hithana", "thama", "thamai", "tama", "tamai", "vada",
        "wada", "wadak", "gedara", "giya", "giyaa", "subha", "aluth", "auruddak",
        "veva", "wewa", "chutty", "putha", "duwa", "baba", "kello", "kollo",
        "malli", "nangi", "aiyya", "akka", "loku", "podi", "boho", "bohoma",
        "sthuthi", "stuti", "obata", "mage", "mageda", "apita", "uney", "unada",
        "thiye", "thiyenawa", "thiyenne", "na", "nae", "naha", "nehe", "epa",
        "epaa", "kiwwe", "kiuwa", "kiwwa", "katha", "kathaa", "kiyala", "kiyanna",
        "mokada", "karanne", "inne", "giye", "ennako", "yannako", "meya", "araya"
    }

    matches = sum(1 for w in words if w in singlish_vocab)
    if matches >= 1:
        return True

    phonetic_patterns = [r'\b\w*th\w*\b', r'\b\w*dh\w*\b', r'\b\w*nd\w*\b', r'\b\w*mb\w*\b']
    pattern_matches = sum(1 for p in phonetic_patterns if re.search(p, text_clean))
    if len(words) <= 8 and pattern_matches >= 2:
        return True

    return False


if __name__ == "__main__":
    tests = [
        "I went to the shop yesterday",
        "මම ගෙදර ගියා",
        "நான் வீட்டிற்கு சென்றேன்",
        "aney machan I went shop la",
        "mama gedara giya",
        "You are really talented",
        "intrusive thought won",
        "The inheritance games",
    ]
    print("Language Detection Test\n" + "="*40)
    for t in tests:
        lang = detect_language(t)
        print(f"[{lang}] {t}")
