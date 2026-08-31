# dashboard/config.py

"""
LUMINA – Color tokens for charts, indicators, and UI components.
Palette: Deep purple sidebar + Soft lavender card surfaces.
"""

COLORS = {
    # ── LUMINA PURPLE PALETTE ──────────────────────────────────────
    "purple":            "#6F5A8E",   # Primary brand accent
    "purple_dark":       "#4A3567",   # Deep Purple
    "purple_deep":       "#2E1F50",   # Sidebar deep
    "purple_mid":        "#8B72AC",   # Mid purple for chart fills
    "purple_soft":       "#BBA8D4",   # Soft/muted purple

    "lavender":          "#DDD3EE",   # Lavender card border
    "lavender_soft":     "#EDE6F7",   # Card surface tint
    "lavender_100":      "#F5F1FB",   # Page background
    "lavender_gray":     "#C9BDDF",   # Border / divider

    "background":        "#F5F1FB",   # Warm lavender canvas
    "paper":             "#F5F1FB",   # Alias
    "surface":           "#FFFFFF",   # White card surfaces
    "card":              "#EDE6F7",   # Tinted card bg

    "text":              "#1A1626",   # Deep primary text
    "ink":               "#1A1626",
    "text_secondary":    "#5A5472",   # Secondary text
    "muted":             "#5A5472",
    "text_muted":        "#9490A8",   # Footnote text

    "line":              "#D8D0E9",   # Divider / border
    "border":            "#D8D0E9",

    # ── Non-alarming Status Signals ─────────────────────────────────
    "lower_var":         "#6B9E78",   # Sage / lower variation
    "green":             "#6B9E78",
    "green_soft":        "#EAF2EC",

    "moderate_var":      "#B49860",   # Warm amber / moderate
    "orange":            "#B49860",
    "amber":             "#B49860",
    "amber_soft":        "#F7F2E8",

    "elevated_var":      "#A96A64",   # Clay-rust / elevated
    "red":               "#A96A64",
    "rust":              "#A96A64",
    "rust_soft":         "#F7EDED",

    # ── Legacy & Chart Compatibility Aliases ────────────────────────
    "teal":              "#6F5A8E",   # maps to primary purple
    "teal_soft":         "#EDE6F7",
    "sage":              "#6B9E78",
    "blue":              "#6F5A8E",
    "cyan":              "#BBA8D4",
    "navy":              "#1A1626",
    "navy_2":            "#4A3567",
    "white":             "#FFFFFF",
    "page":              "#F5F1FB",
    "soft_neutral":      "#E8E4F0",
    "sidebar":           "#3D2870",   # Deep purple sidebar
}
