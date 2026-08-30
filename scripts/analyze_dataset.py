"""One-off script to derive risk thresholds from synthetic dataset."""
import pandas as pd
import numpy as np

df = pd.read_csv(r"d:\Campus\Semester 8\LUMINA\data\uploads\ad_risk_enhanced_merged_500.csv")

print("=== SHAPE ===")
print(df.shape)
print("\n=== UNIQUE USERS ===", df["user_id"].nunique())

user_df = df.groupby("user_id").first().reset_index()

print("\n=== RISK SCORE (user level) ===")
print(user_df["risk_score"].describe())
print("Percentiles:", user_df["risk_score"].quantile([0.25, 0.33, 0.5, 0.65, 0.7, 0.75]).to_dict())

print("\n=== BINARY RISK STATUS ===")
print(user_df["binary_risk_status"].value_counts())

print("\n=== RISK SCORE BY STATUS ===")
for s in sorted(user_df["binary_risk_status"].unique()):
    sub = user_df[user_df["binary_risk_status"] == s]["risk_score"]
    med_val = float(sub.median()) # type: ignore
    print(f"{s}: min={sub.min():.3f}, max={sub.max():.3f}, mean={sub.mean():.3f}, median={med_val:.3f}, n={len(sub)}")

print("\n=== FEATURE STATS (user level) ===")
features = [
    "lexical_diversity_ttr", "syntactic_complexity", "content_density",
    "pronoun_usage_ratio", "repetitiveness_ngram", "agraphia_error_rate",
    "social_bridging_score", "social_bonding_score", "posting_frequency_delta",
    "sentiment", "lexical_ttr", "network_size",
]
for f in features:
    if f in user_df.columns:
        print(f"{f}: mean={user_df[f].mean():.3f}, std={user_df[f].std():.3f}, min={user_df[f].min():.3f}, max={user_df[f].max():.3f}")

print("\n=== CORRELATIONS WITH risk_score ===")
num_cols = [
    "lexical_diversity_ttr", "syntactic_complexity", "content_density",
    "pronoun_usage_ratio", "repetitiveness_ngram", "agraphia_error_rate",
    "social_bridging_score", "social_bonding_score", "posting_frequency_delta",
    "sentiment", "age", "moca_score", "gds_stage", "network_size",
]
corrs = {}
for c in num_cols:
    if c in user_df.columns:
        corr = float(pd.Series(user_df[c]).corr(other=pd.Series(user_df["risk_score"]))) # type: ignore
        corrs[c] = corr
        print(f"{c}: {corr:.3f}")

# Derive class thresholds from binary_risk_status
low = user_df[user_df["binary_risk_status"] == "Low"]["risk_score"]
med = user_df[user_df["binary_risk_status"] == "Med"]["risk_score"]
high = user_df[user_df["binary_risk_status"] == "High"]["risk_score"]
print("\n=== SUGGESTED THRESHOLDS ===")
if len(low) > 0 and len(med) > 0:
    hc_max = (low.max() + med.min()) / 2
    print(f"HC_MAX (Low/Med boundary): {hc_max:.3f}")
if len(med) > 0 and len(high) > 0:
    mci_max = (med.max() + high.min()) / 2
    print(f"MCI_MAX (Med/High boundary): {mci_max:.3f}")

print("\n=== TTR by risk status ===")
for s in ["Low", "Med", "High"]:
    sub = user_df[user_df["binary_risk_status"] == s]
    if len(sub) > 0:
        print(
            f"{s}: ttr mean={sub['lexical_diversity_ttr'].mean():.3f}, "
            f"repetition mean={sub['repetitiveness_ngram'].mean():.3f}, "
            f"complexity mean={sub['syntactic_complexity'].mean():.3f}, "
            f"content_density mean={sub['content_density'].mean():.3f}"
        )

print("\n=== posting_frequency_delta by status ===")
for s in ["Low", "Med", "High"]:
    sub = user_df[user_df["binary_risk_status"] == s]
    if len(sub) > 0:
        pf_med = float(sub['posting_frequency_delta'].median()) # type: ignore
        print(f"{s}: mean={sub['posting_frequency_delta'].mean():.1f}, median={pf_med:.1f}")

print("\n=== social scores by status ===")
for s in ["Low", "Med", "High"]:
    sub = user_df[user_df["binary_risk_status"] == s]
    if len(sub) > 0:
        print(
            f"{s}: bridging={sub['social_bridging_score'].mean():.3f}, "
            f"bonding={sub['social_bonding_score'].mean():.3f}, "
            f"network={sub['network_size'].mean():.1f}"
        )

# Weight derivation from absolute correlations
print("\n=== SUGGESTED WEIGHTS (normalized abs corr) ===")
feature_map = {
    "ttr": "lexical_diversity_ttr",
    "complexity": "syntactic_complexity",
    "repetition": "repetitiveness_ngram",
    "content_density": "content_density",
}
abs_corrs = {k: abs(float(pd.Series(user_df[v]).corr(other=pd.Series(user_df["risk_score"])))) for k, v in feature_map.items() if v in user_df.columns} # type: ignore
total = sum(abs_corrs.values())
for k, v in abs_corrs.items():
    print(f"{k}: {v/total:.3f}")

# Simulate risk score using dataset features (proxy for coherence with content_density inverted)
print("\n=== SIMULATED SCORE vs DATASET ===")
user_df = user_df.copy()
user_df["ttr_risk"] = 1.0 - user_df["lexical_diversity_ttr"]
user_df["complexity_risk"] = 1.0 - user_df["syntactic_complexity"]
user_df["repetition_risk"] = user_df["repetitiveness_ngram"]
user_df["coherence_risk"] = 1.0 - user_df["content_density"]

# Test different weight combos
for w_ttr, w_coh, w_comp, w_rep in [
    (0.35, 0.30, 0.20, 0.15),
    (0.30, 0.25, 0.25, 0.20),
    (0.25, 0.25, 0.25, 0.25),
]:
    sim = (
        user_df["ttr_risk"] * w_ttr
        + user_df["coherence_risk"] * w_coh
        + user_df["complexity_risk"] * w_comp
        + user_df["repetition_risk"] * w_rep
    )
    corr = float(pd.Series(sim).corr(other=pd.Series(user_df["risk_score"]))) # type: ignore
    print(f"Weights ({w_ttr},{w_coh},{w_comp},{w_rep}): corr={corr:.3f}")

# Best weights from correlation
w = {k: abs_corrs[k] / total for k in abs_corrs}
# Add coherence proxy weight
coh_corr = abs(float(pd.Series(user_df["content_density"]).corr(other=pd.Series(user_df["risk_score"])))) # type: ignore
all_w = {**w, "coherence": coh_corr}
t2 = sum(all_w.values())
norm_w = {k: v / t2 for k, v in all_w.items()}
print("\nCorrelation-based weights:", {k: round(v, 3) for k, v in norm_w.items()})

sim_best = (
    user_df["ttr_risk"] * norm_w.get("ttr", 0.25)
    + user_df["coherence_risk"] * norm_w.get("coherence", 0.25)
    + user_df["complexity_risk"] * norm_w.get("complexity", 0.25)
    + user_df["repetition_risk"] * norm_w.get("repetition", 0.25)
)
print(f"Best sim corr: {sim_best.corr(user_df['risk_score']):.3f}")

# Complexity norm cap - what cap makes complexity_risk align?
for cap in [0.5, 0.6, 0.7, 0.8, 1.0]:
    cr = 1.0 - (user_df["syntactic_complexity"] / cap).clip(0, 1)
    print(f"Complexity cap {cap}: mean risk={cr.mean():.3f}, corr with dataset={cr.corr(user_df['risk_score']):.3f}")

# TTR norm cap
for cap in [1.0, 1.5, 2.0, 2.5]:
    tr = 1.0 - (user_df["lexical_diversity_ttr"] * cap).clip(0, 1)
    print(f"TTR cap {cap}: mean risk={tr.mean():.3f}, corr={tr.corr(user_df['risk_score']):.3f}")
