"""
LUMINA — Pipeline Validation Script
=====================================
Usage:
    cd "d:/Campus/Semester 8/LUMINA"
    .\\lumina_env\\Scripts\\python.exe scripts\\validate_pipeline.py [--pilot N]

Expected CSV columns:
  posts.csv         : subject_id, text, interaction_type, date (YYYY-MM-DD), language
  ground_truth.csv  : subject_id, ground_truth_risk_class (HC|MCI|AD_Risk),
                      ground_truth_risk_score (0.0-1.0), language

The script:
  1. Loads posts.csv, groups by subject_id.
  2. Filters out passive interactions (like / view / react) before NLP.
  3. Feeds remaining text into the real NLP classifier.
  4. Feeds the full interaction set into the SNA network module.
  5. Runs the ABM using the same abm_seed_risk formula as pipeline.py.
  6. Compares predicted class / score vs ground truth.
  7. Prints overall accuracy, confusion matrix, per-class P/R/F1,
     per-language accuracy, and a list of misclassified subjects.
"""

import argparse
import sys
import os
from pathlib import Path
from collections import defaultdict

# ── Path setup ──────────────────────────────────────────────────────────────
LUMINA_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LUMINA_ROOT))
sys.path.insert(0, str(LUMINA_ROOT / "dashboard"))

import pandas as pd
import numpy as np


# ── CLI args ─────────────────────────────────────────────────────────────────
def _parse_args():
    p = argparse.ArgumentParser(description="LUMINA Pipeline Validation")
    p.add_argument(
        "--pilot", type=int, default=None,
        help="Run on only the first N subjects (default: all)"
    )
    p.add_argument(
        "--posts",   default=str(LUMINA_ROOT / "data" / "posts.csv"),
        help="Path to posts.csv"
    )
    p.add_argument(
        "--gt",      default=str(LUMINA_ROOT / "data" / "ground_truth.csv"),
        help="Path to ground_truth.csv"
    )
    p.add_argument(
        "--env",     default=str(LUMINA_ROOT / "data" / "environmental_intake.csv"),
        help="Path to environmental_intake.csv"
    )
    return p.parse_args()


# ── Constants ────────────────────────────────────────────────────────────────
PASSIVE_TYPES = {"like", "view", "react", "reaction", "seen"}

CLASSES = ["HC", "MCI", "AD_Risk"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def filter_active(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows where interaction_type is NOT passive."""
    if "interaction_type" not in df.columns:
        return df
    mask = ~df["interaction_type"].str.lower().isin(PASSIVE_TYPES)
    return pd.DataFrame(df[mask])


def build_sna_interactions(subject_df: pd.DataFrame) -> list:
    """
    Convert a subject's post rows into the interaction list that
    modules/sna/network.py's extract_sna_metrics() expects.
    """
    records = []
    for _, row in subject_df.iterrows():
        records.append({
            "interaction_type": row.get("interaction_type", "post"),
            "date":             str(row.get("date", "")),
            "platform":         row.get("platform", "unknown"),
        })
    return records


def run_subject(subject_id, subject_df: pd.DataFrame, verbose: bool = False, environmental_intake: dict | None = None) -> dict:
    """
    Run the full NLP -> SNA -> ABM pipeline on one subject and return a
    result dict compatible with what pipeline.py produces.
    """
    # ── 1. NLP (active posts only) ──────────────────────────────────────────
    active_df = filter_active(subject_df)
    texts = active_df["text"].dropna().tolist()

    from modules.nlp.classifier import classify_risk
    nlp_result = classify_risk(texts)

    # ── 2. SNA ──────────────────────────────────────────────────────────────
    interactions = build_sna_interactions(subject_df)
    try:
        from modules.sna.network import extract_sna_metrics
        sna_metrics = extract_sna_metrics(interactions)
    except Exception as e:
        print(f"\n    [SNA error] {e}")
        sna_metrics = {
            "withdrawal_score":      0.0,
            "network_size":          0,
            "interaction_diversity": 0.0,
            "dm_contact_count":      0,
            "posting_frequency":     0.0,
        }

    # ── 3. ABM seed ─────────────────────────────────────────────────────────
    from modules.config.thresholds import (
        ABM_SEED_WEIGHTS,
        ABM_SEED_TTR_NORM_CAP,
        ABM_SEED_COMPLEXITY_NORM_CAP,
        ABM_DEFAULTS,
        FINAL_RISK_WEIGHTS,
        RISK_CLASS_THRESHOLDS,
    )

    ttr        = nlp_result.get("ttr", 0.5)
    complexity = nlp_result.get("complexity", 0.1) or 0.1
    withdrawal = sna_metrics.get("withdrawal_score", 0.0) or 0.0

    ttr_risk        = 1.0 - min(ttr * ABM_SEED_TTR_NORM_CAP, 1.0)
    complexity_risk = 1.0 - min(complexity / ABM_SEED_COMPLEXITY_NORM_CAP, 1.0)
    abm_seed_risk   = round(
        ttr_risk * ABM_SEED_WEIGHTS["ttr_risk"] +
        complexity_risk * ABM_SEED_WEIGHTS["complexity_risk"] +
        withdrawal * ABM_SEED_WEIGHTS["withdrawal"],
        4
    )
    abm_seed_risk = max(0.1, min(abm_seed_risk, 0.9))

    # ── 4. ABM simulation ───────────────────────────────────────────────────
    from modules.abm.model import LuminaABM
    model = LuminaABM(
        n_people=ABM_DEFAULTS["n_people"],
        n_community_agents=ABM_DEFAULTS["n_community_agents"],
        initial_risk_score=abm_seed_risk,
        grid_size=ABM_DEFAULTS["grid_size"],
    )
    model.run(steps=ABM_DEFAULTS["steps"])
    summary = model.get_summary()

    # ── 5. Composite score (mirror of save_abm_to_db, no DB write) ──────────
    nlp_risk   = nlp_result.get("risk_score", 0.5)
    
    # FIX BUG 1: Calculate actual environmental risk score from scoring module
    from modules.environmental.scoring import calculate_environmental_score
    env_factors = environmental_intake.get("factors", {}) if environmental_intake else {}
    symptom_severity = environmental_intake.get("symptom_severity", 0.0) if environmental_intake else 0.0
    if not env_factors and subject_df is not None:
        LANCET_FACTORS = [
            "education_less_than_secondary", "hearing_loss", "hypertension", "smoking",
            "obesity", "depression", "physical_inactivity", "diabetes", "low_social_contact",
            "excessive_alcohol", "traumatic_brain_injury", "air_pollution", "vision_loss", "high_ldl_cholesterol"
        ]
        for f in LANCET_FACTORS:
            if f in subject_df.columns and bool(subject_df[f].iloc[0]):
                env_factors[f] = True
        if "symptom_severity" in subject_df.columns:
            symptom_severity = float(subject_df["symptom_severity"].iloc[0])

    env_risk = calculate_environmental_score(env_factors, symptom_severity)

    # Compute composite score using authoritative FINAL_RISK_WEIGHTS from thresholds.py
    blended = (
        nlp_risk       * FINAL_RISK_WEIGHTS["nlp"] +
        env_risk       * FINAL_RISK_WEIGHTS["environmental"] +
        withdrawal     * FINAL_RISK_WEIGHTS["withdrawal"] +
        abm_seed_risk  * FINAL_RISK_WEIGHTS["abm_spread"]
    )

    final_score = round(min(max(blended, 0.0), 1.0), 4)

    if final_score < RISK_CLASS_THRESHOLDS["HC_MAX"]:
        final_class = "HC"
    elif final_score < RISK_CLASS_THRESHOLDS["MCI_MAX"]:
        final_class = "MCI"
    else:
        final_class = "AD_Risk"

    abm_spread = min(summary.get("awareness_spread", 0) / 10.0, 1.0)

    return {
        "subject_id":    subject_id,
        "final_class":   final_class,
        "final_score":   final_score,
        "nlp_score":     nlp_risk,
        "withdrawal":    withdrawal,
        "abm_seed_risk": abm_seed_risk,
        "abm_spread":    abm_spread,
    }


# ── Metrics ───────────────────────────────────────────────────────────────────

def confusion_matrix(y_true, y_pred, classes):
    matrix = {c: {c2: 0 for c2 in classes} for c in classes}
    for t, p in zip(y_true, y_pred):
        if t in matrix and p in matrix:
            matrix[t][p] += 1
    return matrix


def per_class_metrics(matrix, classes):
    metrics = {}
    for c in classes:
        tp = matrix[c][c]
        fp = sum(matrix[r][c] for r in classes if r != c)
        fn = sum(matrix[c][r] for r in classes if r != c)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1        = (2 * precision * recall / (precision + recall)
                     if (precision + recall) > 0 else 0.0)
        metrics[c] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
    return metrics


# ── Report printer ────────────────────────────────────────────────────────────

def print_report(results, ground_truth: pd.DataFrame):
    # Merge
    gt_map = {}
    for _, row in ground_truth.iterrows():
        gt_map[row["subject_id"]] = {
            "gt_class": row["ground_truth_risk_class"],
            "gt_score": float(row["ground_truth_risk_score"]),
            "language": row.get("language", "unknown"),
        }

    rows = []
    for r in results:
        sid = r["subject_id"]
        if sid not in gt_map:
            continue
        rows.append({**r, **gt_map[sid]})

    df = pd.DataFrame(rows)
    if df.empty:
        print("\n[!] No matching subjects between results and ground_truth.csv")
        return

    y_true = df["gt_class"].tolist()
    y_pred = df["final_class"].tolist()

    correct = sum(t == p for t, p in zip(y_true, y_pred))
    total   = len(y_true)
    acc     = correct / total if total else 0.0

    # Score correlation
    mae  = float(np.mean(np.abs(np.array(df["final_score"]) - np.array(df["gt_score"]))))
    corr = float(pd.Series(df["final_score"]).corr(other=pd.Series(df["gt_score"]))) # type: ignore

    sep = "=" * 60

    print(f"\n{sep}")
    print("  LUMINA PIPELINE VALIDATION REPORT")
    print(sep)
    print(f"  Subjects evaluated : {total}")
    print(f"  Overall accuracy   : {acc*100:.1f}%  ({correct}/{total} correct)")
    print(f"  Score MAE          : {mae:.4f}")
    print(f"  Score correlation  : {corr:.4f}")

    # Confusion matrix
    print(f"\n{'  ' + '-'*56}")
    print("  CONFUSION MATRIX  (rows=actual, cols=predicted)")
    print(f"  {'':12s}" + "".join(f"{c:>12s}" for c in CLASSES))
    cm = confusion_matrix(y_true, y_pred, CLASSES)
    for actual in CLASSES:
        row_str = f"  {actual:<12s}" + "".join(
            f"{cm[actual][pred]:>12d}" for pred in CLASSES
        )
        print(row_str)

    # Per-class metrics
    print(f"\n  {'Class':<12s} {'Precision':>10s} {'Recall':>10s} {'F1':>10s} {'Support':>10s}")
    pcm = per_class_metrics(cm, CLASSES)
    for c in CLASSES:
        m = pcm[c]
        print(f"  {c:<12s} {m['precision']:>10.3f} {m['recall']:>10.3f} "
              f"{m['f1']:>10.3f} {m['support']:>10d}")

    # Per-language breakdown
    if "language" in df.columns:
        print(f"\n  PER-LANGUAGE ACCURACY")
        for lang, grp in df.groupby("language"):
            lang_correct = sum(grp["gt_class"] == grp["final_class"])
            lang_total   = len(grp)
            lang_acc     = lang_correct / lang_total if lang_total else 0.0
            print(f"  {lang:<15s}  {lang_acc*100:.1f}%  ({lang_correct}/{lang_total})")

    # Misclassified subjects
    misclassified = df[df["gt_class"] != df["final_class"]]
    print(f"\n  MISCLASSIFIED SUBJECTS  ({len(misclassified)} of {total})")
    if misclassified.empty:
        print("  None -- perfect class agreement!")
    else:
        print(f"  {'SubjectID':<14s} {'Actual':>10s} {'Predicted':>12s} "
              f"{'GT Score':>10s} {'Pred Score':>12s} {'Lang':>8s}")
        for _, row in misclassified.iterrows():
            print(
                f"  {str(row['subject_id']):<14s} {row['gt_class']:>10s} "
                f"{row['final_class']:>12s} {row['gt_score']:>10.3f} "
                f"{row['final_score']:>12.3f} {row.get('language','?'):>8s}"
            )

    print(f"\n{sep}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = _parse_args()

    print(f"[1/4] Loading posts from: {args.posts}")
    posts_df = pd.read_csv(args.posts, dtype={"subject_id": str})

    print(f"[2/4] Loading ground truth from: {args.gt}")
    gt_df = pd.read_csv(args.gt, dtype={"subject_id": str})

    env_df = None
    if os.path.exists(args.env):
        print(f"[2.5/4] Loading environmental intake from: {args.env}")
        env_df = pd.read_csv(args.env, dtype={"subject_id": str})

    subjects = posts_df["subject_id"].unique().tolist()
    if args.pilot:
        subjects = subjects[:args.pilot]
        print(f"[3/4] PILOT MODE: running on first {len(subjects)} subjects")
    else:
        print(f"[3/4] Running on all {len(subjects)} subjects")

    results = []
    for i, sid in enumerate(subjects, 1):
        subject_df = pd.DataFrame(posts_df[posts_df["subject_id"] == sid].copy())
        
        env_intake = None
        if env_df is not None:
            match = env_df[env_df["subject_id"] == sid]
            if not match.empty:
                row = match.iloc[0].to_dict()
                sym_sev = float(row.pop("symptom_severity", 0.0))
                row.pop("subject_id", None)
                env_intake = {
                    "factors": {k: bool(v) for k, v in row.items()},
                    "symptom_severity": sym_sev,
                }

        print(f"  [{i}/{len(subjects)}] Subject {sid} ...", end=" ", flush=True)
        try:
            r = run_subject(sid, subject_df, environmental_intake=env_intake)
            results.append(r)
            print(f"{r['final_class']}  score={r['final_score']:.3f}")
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback; traceback.print_exc()

    print(f"\n[4/4] Generating report...")
    print_report(results, gt_df)


if __name__ == "__main__":
    main()
