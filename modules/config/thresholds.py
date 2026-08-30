"""
LUMINA - Shared Model Parameters & Thresholds

All the tunable numbers that drive risk scoring and the ABM simulation,
in one place instead of scattered across classifier.py / agents.py /
model.py / pipeline.py. Change values here, not in the model logic.

Calibrated against ad_risk_enhanced_merged_500.csv (500 users, 5812 posts).
Class boundaries derived from binary_risk_status labels:
  Low  (HC)      risk_score < 0.40
  Med  (MCI)     0.40 <= risk_score < 0.70
  High (AD_Risk) risk_score >= 0.70
"""

# ─────────────────────────────────────────────
# NLP RISK SCORING (modules/nlp/classifier.py)
# ─────────────────────────────────────────────

# How much each signal contributes to the final 0.0-1.0 risk score.
# Must sum to 1.0. Weights tuned to synthetic dataset feature correlations.
#
# NOTE: "repetition" previously used 1-TTR (= algebraically identical to ttr)
# and was therefore NOT an independent signal. It has been replaced with a
# genuine bigram/trigram repetition score (fraction of repeated n-grams).
# The freed 0.15 weight has been redistributed: +0.08 to coherence, +0.07
# to complexity, since those two are the most clinically validated markers.
RISK_SCORE_WEIGHTS = {
    "ttr":        0.30,   # vocabulary richness (lower TTR = higher risk)
    "coherence":  0.33,   # mBERT coherence    (lower = higher risk)
    "complexity": 0.32,   # sentence complexity (lower = higher risk)
    "repetition": 0.05,   # n-gram phrase repetition (higher = higher risk)
}

# Score cutoffs that map the 0.0-1.0 risk score to a class.
RISK_CLASS_THRESHOLDS = {
    "HC_MAX": 0.40,   # score < this  -> Healthy Control  (Low in dataset)
    "MCI_MAX": 0.70,  # score < this  -> Mild Cognitive Impairment (Med)
    # score >= MCI_MAX -> AD_Risk (High)
}


# ─────────────────────────────────────────────
# NLP FEATURE REFERENCE THRESHOLDS
# Used by extractor reasoning text, insights cards, and dashboard bars.
# Derived from per-status feature means in the synthetic dataset.
# ─────────────────────────────────────────────

FEATURE_THRESHOLDS = {
    # TTR: Low mean=0.75, Med mean=0.60, High mean=0.43
    "ttr_low": 0.55,
    "ttr_ok": 0.65,
    "ttr_research": 0.55,
    # Complexity: Low mean=0.71, Med mean=0.56, High mean=0.43
    "complexity_low": 0.45,
    "complexity_research": 0.45,
    # N-gram Repetition: calibrated to bigram/trigram scale (not 1-TTR).
    # Higher values mean more recurring multi-word phrases.
    # Threshold ~0.20 flags elevated phrase repetition on social-media length texts.
    "repetition_hi": 0.20,
    "repetition_watch": 0.12,
    "repetition_research": 0.20,
    "coherence_low": 0.65,
    "withdrawal_hi": 0.55,
    "word_len_low": 3.2,
}


# ─────────────────────────────────────────────
# DASHBOARD GAUGE (dashboard/charts.py)
# Percent scale (0-100) matching RISK_CLASS_THRESHOLDS above.
# ─────────────────────────────────────────────

GAUGE_THRESHOLDS = {
    "low_max": 40,
    "med_max": 70,
}


# ─────────────────────────────────────────────
# INITIAL-RISK SEEDING FOR THE ABM (dashboard/pipeline.py)
# ─────────────────────────────────────────────

# How this session's NLP + SNA results are combined into the ABM's
# starting risk_score for the simulated "you" agent.
ABM_SEED_WEIGHTS = {
    "ttr_risk": 0.5,
    "complexity_risk": 0.3,
    "withdrawal": 0.2,
}

# Normalization caps used before applying the weights above.
# Calibrated to dataset ranges: TTR 0.30-0.95, complexity 0.20-0.90.
ABM_SEED_TTR_NORM_CAP = 1.0       # ttr_risk = 1 - min(ttr * this, 1)
ABM_SEED_COMPLEXITY_NORM_CAP = 0.80  # complexity_risk = 1 - min(complexity / this, 1)


# ─────────────────────────────────────────────
# FINAL COMBINED RISK (modules/abm/model.py)
# ─────────────────────────────────────────────

FINAL_RISK_WEIGHTS = {
    "nlp": 0.40,
    "environmental": 0.40,
    "withdrawal": 0.12,
    "abm_spread": 0.08,
}


# ─────────────────────────────────────────────
# ABM POPULATION DEFAULTS (modules/abm/model.py)
# ─────────────────────────────────────────────

ABM_DEFAULTS = {
    "n_people": 30,            # reduced from 50 — sufficient for stable statistics
    "n_community_agents": 5,
    "grid_size": 12,           # reduced from 15
    "steps": 12,               # reduced from 20
}

# Smaller/faster population used for the live "possible outcomes"
# scenario comparison (runs twice, in the UI, so it needs to be quick).
ABM_SCENARIO_DEFAULTS = {
    "n_people": 20,            # reduced from 30
    "grid_size": 10,           # reduced from 12
    "steps": 10,               # reduced from 15
}


# ─────────────────────────────────────────────
# ABM AGENT BEHAVIOUR (modules/abm/agents.py)
# ─────────────────────────────────────────────

# Risk-score cutoffs for an individual agent's state (same meaning as
# RISK_CLASS_THRESHOLDS above, kept separate since the ABM evolves risk
# over simulated time rather than scoring text once).
AGENT_STATE_THRESHOLDS = {
    "HC_MAX": 0.40,
    "MCI_MAX": 0.70,
}

# How fast an untreated agent's risk naturally rises per simulated step,
# and how isolation/support change that rate.
AGENT_PROGRESSION = {
    "base_rate": 0.01,
    "isolation_penalty": 0.02,     # added when social_activity < isolation_threshold
    "isolation_threshold": 0.3,
    "support_relief": 0.012,       # subtracted when support_received > support_threshold
                                   # NOTE: must exceed base_rate (0.01) to produce visible
                                   # trajectory divergence in the "with_support" scenario
    "support_threshold": 0.1,      # lowered from 0.5: one nearby CommunityAgent (0.2)
                                   # already qualifies; previously required 3+ agents
}

# How much visiting/being near a CommunityAgent reduces progression.
AGENT_SUPPORT = {
    "radius": 2,               # grid cells a CommunityAgent's support reaches
    "support_per_agent": 0.2,  # support_received added per nearby CommunityAgent
    "max_support": 1.0,
}

# Chance per step that an aware neighbor makes another agent aware too.
AWARENESS_SPREAD_CHANCE = 0.15


# ─────────────────────────────────────────────
# SNA WITHDRAWAL TIERS (modules/sna/network.py)
# Calibrated to dataset social_bridging_score by risk status:
#   Low mean=0.61, Med mean=0.45, High mean=0.24
# ─────────────────────────────────────────────

SNA_WITHDRAWAL_TIERS = {
    "diversity": {"active": 0.55, "normal": 0.40, "low": 0.30},
    "frequency": {"active": 8, "normal": 4, "low": 1},
    "dm_count": {"active": 15, "normal": 8, "low": 3},
}

SNA_WITHDRAWAL_WEIGHTS = {
    "diversity": 0.40,
    "frequency": 0.35,
    "dm_count": 0.25,
}
