"""
Confidence Calibrator — Adjusts per-model confidence based on historical accuracy.

If a model consistently over-predicts (says 0.8 but wins only 50%),
the calibrator scales it down. If under-predicting, scales up.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Calibrator:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.calibration_path = self.log_dir / "calibration.json"
        self.bins = {}  # model -> {bin_label -> {predicted: float, actual_win_rate: float, count: int}}
        self._load()

    def _load(self):
        try:
            if self.calibration_path.exists():
                self.bins = json.loads(self.calibration_path.read_text())
        except Exception:
            self.bins = {}

    def _save(self):
        try:
            self.calibration_path.write_text(json.dumps(self.bins, indent=2))
        except Exception as e:
            logger.error(f"Failed to save calibration: {e}")

    def record(self, model_name: str, predicted_confidence: float, is_win: bool):
        """Record a prediction outcome for calibration."""
        if model_name not in self.bins:
            self.bins[model_name] = {}

        # Bucket into 0.1-wide bins
        bin_label = f"{int(predicted_confidence * 10) / 10:.1f}"
        if bin_label not in self.bins[model_name]:
            self.bins[model_name][bin_label] = {"wins": 0, "total": 0}

        bucket = self.bins[model_name][bin_label]
        bucket["total"] += 1
        if is_win:
            bucket["wins"] += 1

        self._save()

    def calibrate(self, model_name: str, raw_confidence: float) -> float:
        """
        Adjust a model's confidence based on its calibration history.

        If model predicts 0.8 confidence but historically wins only 50% at that level,
        the calibrated output is ~0.5.
        """
        if model_name not in self.bins:
            return raw_confidence

        bin_label = f"{int(raw_confidence * 10) / 10:.1f}"
        bucket = self.bins[model_name].get(bin_label)

        if not bucket or bucket["total"] < 5:
            return raw_confidence

        actual_win_rate = bucket["wins"] / bucket["total"]
        # Blend raw with calibrated (80% calibrated, 20% raw)
        calibrated = 0.8 * actual_win_rate + 0.2 * raw_confidence
        return round(max(0.0, min(1.0, calibrated)), 4)

    def get_calibration_report(self) -> dict:
        """Return calibration stats per model per bin."""
        report = {}
        for model, bins in self.bins.items():
            report[model] = {}
            for bin_label, data in sorted(bins.items()):
                total = data["total"]
                win_rate = data["wins"] / total if total > 0 else 0
                report[model][bin_label] = {
                    "predicted_conf": float(bin_label),
                    "actual_win_rate": round(win_rate, 3),
                    "count": total,
                    "gap": round(float(bin_label) - win_rate, 3),
                }
        return report
