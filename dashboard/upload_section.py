from __future__ import annotations

import os
import html
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import streamlit as st

from pipeline import run_full_analysis, create_analysis_run, finalize_analysis_run
from utils import render_html

MEDIA_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp",
    ".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif",
    ".mp3", ".m4a", ".wav", ".aac", ".ogg",
    ".pdf", ".tar", ".gz"
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


def _sanitize_and_save_zip(uploaded_file, progress_callback=None) -> tuple[str, int, int]:
    """
    Embedded Ingestion Optimizer:
    Filters out heavy photos, videos, audio, and bloated logs from the uploaded ZIP
    and creates an optimized lightweight temporary ZIP for the analysis pipeline.
    """
    uploaded_file.seek(0)
    orig_bytes = uploaded_file.size if hasattr(uploaded_file, "size") else 0

    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp_path = tmp.name

    retained = 0
    skipped = 0

    try:
        with ZipFile(uploaded_file) as zin, ZipFile(tmp_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                fn_lower = item.filename.lower()
                ext = os.path.splitext(fn_lower)[1]

                if item.is_dir():
                    continue
                if ext in MEDIA_EXTENSIONS:
                    skipped += 1
                    continue
                if any(ign in fn_lower for ign in IGNORED_PATHS):
                    skipped += 1
                    continue
                if "/videos/" in fn_lower or "/photos/" in fn_lower or "/audio/" in fn_lower:
                    skipped += 1
                    continue
                if ext not in (".json", ".html", ".htm", ".txt", ".csv", ""):
                    skipped += 1
                    continue

                zout.writestr(item, zin.read(item.filename))
                retained += 1
    except Exception as e:
        print(f"[LUMINA Optimizer] Direct copy fallback: {e}")
        uploaded_file.seek(0)
        with open(tmp_path, "wb") as f:
            import shutil
            shutil.copyfileobj(uploaded_file, f)

    new_bytes = Path(tmp_path).stat().st_size if Path(tmp_path).exists() else orig_bytes
    return tmp_path, orig_bytes, new_bytes


def _guess_platform(file_name: str) -> str:
    """Cheap filename-based hint; the real detection happens inside the
    modules (parser.py / network.py) by inspecting the ZIP contents."""
    name = file_name.lower()
    if "instagram" in name:
        return "instagram"
    if "facebook" in name:
        return "facebook"
    if "tiktok" in name:
        return "tiktok"
    if "threads" in name:
        return "threads"
    if "takeout" in name or "youtube" in name:
        return "youtube"
    return "unknown"


def _format_file_size(size_bytes: int) -> str:
    size = float(size_bytes)

    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"

        size /= 1024

    return f"{size:.1f} GB"


def _validate_zip_file(uploaded_file) -> tuple[bool, int]:
    try:
        uploaded_file.seek(0)
        with ZipFile(uploaded_file) as archive:
            info_list = archive.infolist()
            uploaded_file.seek(0)
            if not info_list:
                return False, 0
            return True, len(info_list)
    except Exception:
        uploaded_file.seek(0)
        return False, 0


def render_zip_upload_section() -> None:
    active_subject = st.session_state.get("active_subject") or {}
    subj_name = active_subject.get("name", "active subject")

    with st.container(border=True):
        render_html(
            f"""
            <div class="upload-header">
                <div>
                    <div class="upload-title">
                        Upload Export Data
                    </div>
                    <div class="upload-subtitle">
                        For <b>{html.escape(subj_name)}</b> — Instagram, Facebook, Threads, TikTok, or YouTube exports.
                    </div>
                </div>
                <div class="upload-badge">ZIP ARCHIVE</div>
            </div>
            """
        )

        with st.expander("📋 Clinical & Environmental Intake (Lancet Risk Factors)", expanded=False):
            st.caption(
                "Optionally record subject clinical background and modifiable dementia risk factors (Lancet Commission) "
                "to incorporate into the 40% environmental risk score."
            )
            c1, c2, c3 = st.columns(3)

            with c1:
                st.markdown("**Cardiovascular & Metabolic**")
                hypertension = st.checkbox("Hypertension (High BP)")
                diabetes = st.checkbox("Diabetes Mellitus")
                obesity = st.checkbox("Obesity")
                high_ldl = st.checkbox("High LDL Cholesterol")
                smoking = st.checkbox("Active / History of Smoking")

            with c2:
                st.markdown("**Sensory & Neurological**")
                hearing_loss = st.checkbox("Hearing Loss / Impairment")
                vision_loss = st.checkbox("Uncorrected Vision Loss")
                tbi = st.checkbox("Traumatic Brain Injury (TBI)")
                depression = st.checkbox("History of Depression")
                ed_low = st.checkbox("Education < Secondary Level")

            with c3:
                st.markdown("**Lifestyle & Environment**")
                physical_inactivity = st.checkbox("Physical Inactivity")
                low_social_contact = st.checkbox("Low Social Contact / Isolation")
                excessive_alcohol = st.checkbox("Excessive Alcohol Consumption")
                air_pollution = st.checkbox("High Air Pollution Exposure")

            st.markdown("---")
            symptom_severity = st.slider(
                "Self-Reported Symptom Severity Index",
                min_value=0.0,
                max_value=1.0,
                value=0.0,
                step=0.05,
                help="Clinical rating of self-reported cognitive/memory impairment (0.0 = None, 1.0 = Severe).",
            )

            environmental_intake = {
                "factors": {
                    "education_less_than_secondary": ed_low,
                    "hearing_loss": hearing_loss,
                    "hypertension": hypertension,
                    "smoking": smoking,
                    "obesity": obesity,
                    "depression": depression,
                    "physical_inactivity": physical_inactivity,
                    "diabetes": diabetes,
                    "low_social_contact": low_social_contact,
                    "excessive_alcohol": excessive_alcohol,
                    "traumatic_brain_injury": tbi,
                    "air_pollution": air_pollution,
                    "vision_loss": vision_loss,
                    "high_ldl_cholesterol": high_ldl,
                },
                "symptom_severity": symptom_severity,
            }

        uploaded_files = st.file_uploader(
            "Upload ZIP files",
            type=["zip"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            help="You can upload multiple ZIP files at the same time.",
        )

        st.caption(
            "⚡ **Embedded Ingestion Engine**: LUMINA automatically filters out non-linguistic media (videos, photos, audio) and bloated logs during ingestion."
        )

        if not uploaded_files:
            # When file is removed or cleared, reset session analysis to None (Zero state)
            st.session_state["lumina_session_analysis"] = None
            return

        if uploaded_files:
            oversized = [f for f in uploaded_files if f.size > 50 * 1024 * 1024]
            if oversized:
                st.info(
                    "💡 **Tip for large archives (>50MB)**: If your browser upload is slow due to internet speed, "
                    "you can pre-strip photos/videos locally using `python scripts/prepare_export.py <folder>` for instant upload."
                )

            render_html(
                '<div class="selected-files-title">Selected files</div>'
            )


            file_rows = ""

            for uploaded_file in uploaded_files:
                file_rows += f"""
                    <div class="uploaded-file-row">
                        <div class="uploaded-file-icon">ZIP</div>
                        <div class="uploaded-file-info">
                            <div class="uploaded-file-name">
                                {html.escape(uploaded_file.name)}
                            </div>
                            <div class="uploaded-file-size">
                                {_format_file_size(uploaded_file.size)}
                            </div>
                        </div>
                        <div class="uploaded-file-status">Ready</div>
                    </div>
                """

            render_html(
                f'<div class="uploaded-files-list">{file_rows}</div>'
            )

        analyze_clicked = st.button(
            "Analyze Uploaded Files",
            type="primary",
            width="stretch",
            disabled=not uploaded_files,
        )

        if not analyze_clicked:
            return

        st.session_state["lumina_session_analysis"] = None

        valid_files: list[tuple[str, int]] = []
        invalid_files: list[str] = []

        with st.spinner("Checking uploaded ZIP files..."):
            for uploaded_file in uploaded_files:
                is_valid, entry_count = _validate_zip_file(uploaded_file)

                if is_valid:
                    valid_files.append(
                        (uploaded_file.name, entry_count)
                    )
                else:
                    invalid_files.append(uploaded_file.name)

        if invalid_files:
            st.error(
                "These files are not valid ZIP archives: "
                + ", ".join(invalid_files)
            )

        if not valid_files:
            return

        st.success(
            f"{len(valid_files)} ZIP file(s) validated successfully. "
            "Starting the LUMINA analysis pipeline..."
        )

        user = st.session_state.get("user") or {}
        user_id = user.get("user_id")
        username = user.get("username", "user")
        active_subject = st.session_state.get("active_subject")
        subject_id = active_subject["subject_id"] if active_subject else None

        if not user_id:
            st.error(
                "No logged-in user found in session -- cannot save "
                "results to the database."
            )
            return

        valid_names = {name for name, _ in valid_files}

        # ── Create one parent run row for this entire "Run Analysis" click ──
        run_id = create_analysis_run(user_id, subject_id)
        if not run_id:
            st.warning("Could not create analysis run record (DB issue). Results will still save per session.")

        completed_session_ids: list[int] = []
        completed_platforms: list[str] = []
        per_platform_outcomes: list[dict] = []  # one entry per file
        last_success_outcome: dict | None = None

        for uploaded_file in uploaded_files:
            if uploaded_file.name not in valid_names:
                continue

            platform = _guess_platform(uploaded_file.name)

            with st.status(
                f"Analyzing {uploaded_file.name}...", expanded=True
            ) as status:

                def _progress(msg, _status=status):
                    _status.write(msg)

                _progress("⚡ Running embedded ingestion optimizer (stripping media & bloat)...")
                tmp_path, orig_b, new_b = _sanitize_and_save_zip(uploaded_file, progress_callback=_progress)
                if orig_b > new_b and orig_b > 0:
                    orig_mb = orig_b / (1024 * 1024)
                    new_mb = new_b / (1024 * 1024)
                    pct = 100 - (new_mb / orig_mb * 100)
                    _progress(f"✨ Ingestion complete: reduced {orig_mb:.1f}MB ➔ {new_mb:.1f}MB ({pct:.1f}% reduction).")

                try:
                    outcome = run_full_analysis(
                        zip_path=tmp_path,
                        username=username,
                        user_id=user_id,
                        platform=platform,
                        subject_id=subject_id,
                        progress_callback=_progress,
                        environmental_intake=environmental_intake,
                        run_id=run_id,
                    )
                finally:
                    Path(tmp_path).unlink(missing_ok=True)


                if outcome.get("error"):
                    status.update(
                        label=f"Failed: {uploaded_file.name}",
                        state="error",
                    )
                    st.error(outcome["error"])
                    continue

                nlp = outcome.get("nlp") or {}
                sna = outcome.get("sna") or {}

                status.update(
                    label=f"Done: {uploaded_file.name} "
                    f"({outcome.get('sample_count', 0)} samples)",
                    state="complete",
                )

                st.write(
                    f"**Risk class:** {nlp.get('risk_class', '-')} | "
                    f"**Risk score:** {nlp.get('risk_score', '-')} | "
                    f"**Confidence:** {nlp.get('confidence', '-')}"
                )
                st.write(
                    f"**Network size:** {sna.get('network_size', '-')} | "
                    f"**Withdrawal score:** {sna.get('withdrawal_score', '-')}"
                )

                # Collect per-file metadata for the combined PDF
                sid = outcome.get("session_id")
                if sid:
                    completed_session_ids.append(sid)
                completed_platforms.append(platform)
                per_platform_outcomes.append({
                    "platform": platform.capitalize(),
                    "file_name": uploaded_file.name,
                    "session_id": sid,
                    "nlp": nlp,
                    "sna": sna,
                    "sample_count": outcome.get("sample_count", 0),
                    "composite_risk_score": outcome.get("composite_risk_score"),
                })
                last_success_outcome = outcome

        # ── Finalise the run: compute combined score and persist ──
        if run_id and completed_session_ids:
            finalize_analysis_run(run_id, completed_session_ids, completed_platforms)

        # ── Store combined result in session state ──
        if last_success_outcome is not None:
            combined = last_success_outcome.copy()
            combined["run_id"] = run_id
            combined["per_platform"] = per_platform_outcomes
            combined["platforms_used"] = completed_platforms
            st.session_state["lumina_session_analysis"] = combined

        st.info(
            "Analysis complete — see your calculated results below."
        )
        st.rerun()
