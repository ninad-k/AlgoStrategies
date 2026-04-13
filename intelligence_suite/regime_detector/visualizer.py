"""
Regime Visualizer — Generates color-coded regime overlays on price charts.
"""

import logging
from io import BytesIO

logger = logging.getLogger(__name__)

REGIME_COLORS = {
    "TRENDING_UP": "#26a69a",      # green
    "TRENDING_DOWN": "#ef5350",    # red
    "RANGING": "#42a5f5",          # blue
    "VOLATILE": "#ffa726",         # orange
    "BREAKOUT": "#ab47bc",         # purple
}


def generate_regime_chart(price_data: list, regime_history: list) -> bytes:
    """
    Generate a price chart with regime-colored background.

    Args:
        price_data: List of dicts with {time, close}
        regime_history: List of dicts with {timestamp, regime}

    Returns:
        PNG image as bytes.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime

        fig, ax = plt.subplots(figsize=(14, 6))
        fig.patch.set_facecolor("#1a1a2e")
        ax.set_facecolor("#16213e")

        # Plot price
        times = [datetime.fromisoformat(p["timestamp"]) if isinstance(p.get("timestamp"), str)
                 else p.get("time", datetime.now()) for p in price_data]
        closes = [float(p["close"]) for p in price_data]
        ax.plot(times, closes, color="white", linewidth=1.2, alpha=0.9)

        # Color background by regime
        if regime_history and len(regime_history) > 1:
            for i in range(len(regime_history) - 1):
                r = regime_history[i]
                r_next = regime_history[i + 1]
                t_start = datetime.fromisoformat(r["timestamp"]) if isinstance(r["timestamp"], str) else r["timestamp"]
                t_end = datetime.fromisoformat(r_next["timestamp"]) if isinstance(r_next["timestamp"], str) else r_next["timestamp"]
                color = REGIME_COLORS.get(r["regime"], "#333333")
                ax.axvspan(t_start, t_end, alpha=0.15, color=color)

        ax.set_title("Price with Market Regime Overlay", color="white", fontsize=14)
        ax.tick_params(colors="white")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

        # Legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=c, alpha=0.4, label=r)
            for r, c in REGIME_COLORS.items()
        ]
        ax.legend(handles=legend_elements, loc="upper left",
                  facecolor="#1a1a2e", edgecolor="white", labelcolor="white", fontsize=8)

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    except ImportError:
        logger.warning("matplotlib not installed, cannot generate chart")
        return b""
