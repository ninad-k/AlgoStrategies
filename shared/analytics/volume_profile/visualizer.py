"""
Volume Profile Visualizer — Generates horizontal volume histogram charts.
"""

import logging
from io import BytesIO

logger = logging.getLogger(__name__)


def generate_volume_profile_chart(profile: dict, symbol: str = "") -> bytes:
    """
    Generate a horizontal volume profile chart.

    Args:
        profile: Output from VolumeProfileCalculator.calculate()
        symbol: Symbol name for title

    Returns:
        PNG image as bytes.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        levels = profile.get("profile", [])
        if not levels:
            return b""

        fig, ax = plt.subplots(figsize=(8, 12))
        fig.patch.set_facecolor("#1a1a2e")
        ax.set_facecolor("#16213e")

        prices = [l["price"] for l in levels]
        volumes = [l["volume"] for l in levels]

        # Color bars by type
        colors = []
        for l in levels:
            if l.get("is_poc"):
                colors.append("#ffd700")  # gold
            elif l.get("in_value_area"):
                colors.append("#42a5f5")  # blue
            elif l.get("is_hvn"):
                colors.append("#26a69a")  # green
            elif l.get("is_lvn"):
                colors.append("#ef5350")  # red
            else:
                colors.append("#666666")  # grey

        ax.barh(prices, volumes, height=(prices[1] - prices[0]) * 0.8 if len(prices) > 1 else 1,
                color=colors, alpha=0.85)

        # Mark key levels
        poc = profile.get("poc", 0)
        vah = profile.get("vah", 0)
        val = profile.get("val", 0)

        if poc:
            ax.axhline(y=poc, color="#ffd700", linewidth=2, linestyle="--", label=f"POC: {poc}")
        if vah:
            ax.axhline(y=vah, color="#26a69a", linewidth=1.5, linestyle=":", label=f"VAH: {vah}")
        if val:
            ax.axhline(y=val, color="#ef5350", linewidth=1.5, linestyle=":", label=f"VAL: {val}")

        ax.set_xlabel("Volume", color="white")
        ax.set_ylabel("Price", color="white")
        ax.set_title(f"Volume Profile — {symbol}" if symbol else "Volume Profile",
                      color="white", fontsize=14)
        ax.tick_params(colors="white")
        ax.legend(facecolor="#1a1a2e", edgecolor="white", labelcolor="white", fontsize=9)

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    except ImportError:
        logger.warning("matplotlib not installed")
        return b""
