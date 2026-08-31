# dashboard/config.py

"""
LUMINA – Color tokens for charts, indicators, and UI components.
Palette: Deep Teal sidebar + Clean Mint/Teal card surfaces matching reference UI.
"""

COLORS = {
    # ── LUMINA TEAL PALETTE (matches reference image) ────────────────
    "teal":              "#166E67",   # Primary brand accent
    "teal_dark":         "#0E4D48",   # Deep teal
    "teal_deep":         "#062826",   # Sidebar deep background
    "teal_mid":          "#208B82",   # Mid teal for chart fills
    "teal_soft":         "#C2EAE5",   # Soft/muted teal
    "teal_light":        "#E8F6F4",   # Soft badge tint

    "background":        "#F4F8F7",   # Clean light canvas
    "paper":             "#F4F8F7",   # Alias
    "surface":           "#FFFFFF",   # White card surfaces
    "card":              "#FFFFFF",   # Card bg

    "text":              "#152422",   # Deep primary text
    "ink":               "#152422",
    "text_secondary":    "#556B68",   # Secondary text
    "muted":             "#556B68",
    "text_muted":        "#889E9B",   # Footnote text

    "line":              "#E0ECE9",   # Divider / border
    "border":            "#E0ECE9",

    # ── Status Signals ──────────────────────────────────────────────
    "lower_var":         "#166E67",   # Lower variation / Stable
    "green":             "#166E67",
    "green_soft":        "#E8F6F4",

    "moderate_var":      "#D97706",   # Warm amber / moderate
    "orange":            "#D97706",
    "amber":             "#D97706",
    "amber_soft":        "#FEF3C7",

    "elevated_var":      "#DC2626",   # Rust / elevated
    "red":               "#DC2626",
    "rust":              "#DC2626",
    "rust_soft":         "#FEE2E2",

    # ── Aliases ─────────────────────────────────────────────────────
    "purple":            "#166E67",
    "purple_dark":       "#0E4D48",
    "purple_mid":        "#208B82",
    "lavender":          "#C2EAE5",
    "lavender_soft":     "#E8F6F4",
    "lavender_100":      "#F4F8F7",
    "white":             "#FFFFFF",
    "page":              "#F4F8F7",
    "soft_neutral":      "#E8F6F4",
}
