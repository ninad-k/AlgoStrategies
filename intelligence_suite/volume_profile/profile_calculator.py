"""
Volume Profile Calculator — Computes POC, VAH, VAL, HVN, LVN from TPO data.
"""

import logging

logger = logging.getLogger(__name__)


class VolumeProfileCalculator:
    def __init__(self, config: dict):
        vp_cfg = config.get("volume_profile", {})
        self.value_area_pct = vp_cfg.get("value_area_pct", 70) / 100

    def calculate(self, tpo_data: dict) -> dict:
        """
        Calculate key volume profile levels from TPO data.

        Returns dict with:
            poc: Point of Control (price with highest volume)
            vah: Value Area High
            val: Value Area Low
            hvn: list of High Volume Nodes
            lvn: list of Low Volume Nodes
            profile: annotated levels list
        """
        levels = tpo_data.get("levels", [])
        if not levels:
            return {"poc": 0, "vah": 0, "val": 0, "hvn": [], "lvn": [], "profile": []}

        # POC: price level with highest volume
        poc_level = max(levels, key=lambda x: x["volume"])
        poc = poc_level["price"]

        # Value Area: 70% of total volume centered on POC
        total_volume = sum(l["volume"] for l in levels)
        target_volume = total_volume * self.value_area_pct

        # Start from POC and expand outward
        poc_idx = next(i for i, l in enumerate(levels) if l["price"] == poc)
        included = {poc_idx}
        accumulated = poc_level["volume"]

        low_idx, high_idx = poc_idx, poc_idx

        while accumulated < target_volume and (low_idx > 0 or high_idx < len(levels) - 1):
            # Compare volume of next level above vs below
            vol_above = levels[high_idx + 1]["volume"] if high_idx < len(levels) - 1 else 0
            vol_below = levels[low_idx - 1]["volume"] if low_idx > 0 else 0

            if vol_above >= vol_below and high_idx < len(levels) - 1:
                high_idx += 1
                accumulated += levels[high_idx]["volume"]
                included.add(high_idx)
            elif low_idx > 0:
                low_idx -= 1
                accumulated += levels[low_idx]["volume"]
                included.add(low_idx)
            else:
                break

        vah = levels[high_idx]["price"]
        val = levels[low_idx]["price"]

        # HVN and LVN detection
        avg_volume = total_volume / len(levels) if levels else 0
        hvn = [l["price"] for l in levels if l["volume"] > avg_volume * 1.5]
        lvn = [l["price"] for l in levels if 0 < l["volume"] < avg_volume * 0.5]

        # Annotate levels
        annotated = []
        for i, level in enumerate(levels):
            entry = {**level}
            entry["is_poc"] = level["price"] == poc
            entry["is_vah"] = level["price"] == vah
            entry["is_val"] = level["price"] == val
            entry["is_hvn"] = level["price"] in hvn
            entry["is_lvn"] = level["price"] in lvn
            entry["in_value_area"] = i in included
            annotated.append(entry)

        return {
            "poc": poc,
            "vah": vah,
            "val": val,
            "hvn": hvn[:5],
            "lvn": lvn[:5],
            "value_area_volume_pct": round(accumulated / total_volume * 100, 1) if total_volume > 0 else 0,
            "profile": annotated,
        }
