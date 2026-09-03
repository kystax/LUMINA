"""
LUMINA - Social Export Optimizer Tool
Strips heavy media (images, videos, audio) and bloated URL logs (e.g. 400MB+ liked posts lists)
from social media ZIP exports (Instagram, Facebook, Threads, TikTok, YouTube).
Reduces multi-GB files down to ~1-5 MB for instantaneous upload.
"""

import os
import sys
import zipfile
from pathlib import Path

# Media extensions and non-linguistic bloat to omit
MEDIA_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp",
    ".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif",
    ".mp3", ".m4a", ".wav", ".aac", ".ogg",
    ".pdf", ".zip", ".tar", ".gz"
}

IGNORED_PATHS = (
    "/media/", "\\media\\",
    "/photos/", "\\photos\\",
    "/videos/", "\\videos\\",
    "/audio/", "\\audio\\",
    "/voice_notes/", "\\voice_notes\\",
    "/stickers/", "\\stickers\\",
    "likes/liked_posts",
    "story_interactions/story_likes",
    "story_interactions/stories_viewed",
    "ads_information/",
    "recently_viewed/",
    "recently_searched/",
    "login_and_account_creation/",
    "device_information/",
    "autofill_information/",
)

def optimize_zip(input_path: str, output_path: str | None = None) -> str:
    in_p = Path(input_path).resolve()
    if not in_p.is_file() or in_p.suffix.lower() != ".zip":
        raise ValueError(f"'{input_path}' is not a valid .zip file")

    if not output_path:
        out_p = in_p.parent / f"{in_p.stem}_text_only.zip"
    else:
        out_p = Path(output_path).resolve()

    orig_size = in_p.stat().st_size / (1024 * 1024)
    print(f"\n[LUMINA Optimizer] Processing: {in_p.name} ({orig_size:.1f} MB)...")

    retained_count = 0
    skipped_count = 0

    with zipfile.ZipFile(in_p, 'r') as zin, zipfile.ZipFile(out_p, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            fn_lower = item.filename.lower()
            ext = os.path.splitext(fn_lower)[1]

            # Skip directories
            if item.is_dir():
                continue

            # Skip media and binary files
            if ext in MEDIA_EXTENSIONS:
                skipped_count += 1
                continue

            # Skip non-linguistic bloat directories & giant URL logs
            if any(ign in fn_lower for ign in IGNORED_PATHS):
                skipped_count += 1
                continue

            # Skip files in message video/photo subfolders even if extensionless
            if "/videos/" in fn_lower or "/photos/" in fn_lower or "/audio/" in fn_lower:
                skipped_count += 1
                continue

            # Must be text, json, html, csv, txt
            if ext not in (".json", ".html", ".htm", ".txt", ".csv", ""):
                skipped_count += 1
                continue

            zout.writestr(item, zin.read(item.filename))
            retained_count += 1

    new_size = out_p.stat().st_size / (1024 * 1024)
    reduction = 100 - (new_size / orig_size * 100) if orig_size > 0 else 0
    print(f"  -> Created: {out_p.name}")
    print(f"  -> Size: {orig_size:.1f} MB -> {new_size:.2f} MB ({reduction:.1f}% reduction)")
    print(f"  -> Kept {retained_count} text/data files, stripped {skipped_count} media & non-text files.")
    return str(out_p)

def process_target(target_path: str):
    target = Path(target_path).resolve()
    if target.is_dir():
        zip_files = [f for f in target.glob("*.zip") if not f.name.endswith("_text_only.zip")]
        if not zip_files:
            print(f"No original .zip files found in {target}")
            return
        print(f"Found {len(zip_files)} ZIP file(s) in {target.name}. Optimizing all...")
        for zf in zip_files:
            optimize_zip(str(zf))
    elif target.is_file():
        optimize_zip(str(target))
    else:
        print(f"Path not found: {target_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/prepare_export.py <path_to_zip_or_directory>")
    else:
        process_target(sys.argv[1])
