"""
Pattern Catalog — Defines chart patterns and their labeling rules.
"""

PATTERN_CATALOG = {
    "double_top": {
        "label": 0,
        "direction": "BEARISH",
        "description": "Two peaks at similar level with a valley between",
    },
    "double_bottom": {
        "label": 1,
        "direction": "BULLISH",
        "description": "Two troughs at similar level with a peak between",
    },
    "head_shoulders": {
        "label": 2,
        "direction": "BEARISH",
        "description": "Three peaks — middle (head) higher than two sides (shoulders)",
    },
    "inv_head_shoulders": {
        "label": 3,
        "direction": "BULLISH",
        "description": "Inverted head and shoulders — bullish reversal",
    },
    "ascending_triangle": {
        "label": 4,
        "direction": "BULLISH",
        "description": "Flat top with rising bottoms — bullish breakout likely",
    },
    "descending_triangle": {
        "label": 5,
        "direction": "BEARISH",
        "description": "Flat bottom with declining tops — bearish breakout likely",
    },
    "bull_flag": {
        "label": 6,
        "direction": "BULLISH",
        "description": "Sharp rise followed by slight downward consolidation",
    },
    "bear_flag": {
        "label": 7,
        "direction": "BEARISH",
        "description": "Sharp drop followed by slight upward consolidation",
    },
    "cup_handle": {
        "label": 8,
        "direction": "BULLISH",
        "description": "U-shaped cup followed by small handle pullback",
    },
    "wedge_rising": {
        "label": 9,
        "direction": "BEARISH",
        "description": "Converging trendlines both rising — bearish reversal",
    },
    "wedge_falling": {
        "label": 10,
        "direction": "BULLISH",
        "description": "Converging trendlines both falling — bullish reversal",
    },
    "no_pattern": {
        "label": 11,
        "direction": "NEUTRAL",
        "description": "No recognizable pattern",
    },
}

NUM_CLASSES = len(PATTERN_CATALOG)
LABEL_TO_PATTERN = {v["label"]: k for k, v in PATTERN_CATALOG.items()}
PATTERN_TO_LABEL = {k: v["label"] for k, v in PATTERN_CATALOG.items()}
