# ML Model Trainer
# Author: Ninad
#
# Trains an XGBoost classifier on SuperTrend features across all timeframes
# with walk-forward validation. Supports training on decades of history
# (1997-present) and saves models per timeframe for live use.

import os
import json
import logging
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    logger.warning("xgboost not installed, falling back to sklearn GradientBoosting")

from sklearn.ensemble import GradientBoostingClassifier


@dataclass
class TrainConfig:
    symbol: str = "EURUSD"
    timeframes: list = field(default_factory=lambda: ["M15", "M30", "H1", "H4", "D1", "W1"])
    # Higher TFs used as context features for each target TF
    context_timeframes: dict = field(default_factory=lambda: {
        "M15": ["H1", "H4", "D1"],
        "M30": ["H1", "H4", "D1"],
        "H1":  ["H4", "D1", "W1"],
        "H4":  ["D1", "W1"],
        "D1":  ["W1", "MN1"],
        "W1":  ["MN1"],
    })
    forward_bars: int = 10         # look-ahead window for labeling
    min_move_atr: float = 1.0      # minimum move in ATR multiples for a valid label
    n_splits: int = 5              # walk-forward splits
    test_ratio: float = 0.2        # held-out final test set
    model_dir: str = "models"
    data_dir: str = "data/raw"
    # XGBoost hyperparameters
    n_estimators: int = 500
    max_depth: int = 6
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    min_child_weight: int = 5
    scale_pos_weight: float = 1.0


@dataclass
class TimeframeResult:
    timeframe: str
    total_bars: int
    train_bars: int
    test_bars: int
    label_distribution: dict
    walk_forward_scores: list
    final_test_accuracy: float
    final_test_f1_macro: float
    classification_report: str
    feature_importance_top20: dict
    model_path: str


class MLTrainer:
    def __init__(self, config: TrainConfig):
        self.config = config
        self.results: Dict[str, TimeframeResult] = {}
        self.models: Dict[str, object] = {}
        self.scalers: Dict[str, StandardScaler] = {}

    def _build_model(self, n_classes: int):
        """Create the classifier. Uses XGBoost if available, else sklearn fallback."""
        if HAS_XGB:
            if n_classes == 3:
                return xgb.XGBClassifier(
                    n_estimators=self.config.n_estimators,
                    max_depth=self.config.max_depth,
                    learning_rate=self.config.learning_rate,
                    subsample=self.config.subsample,
                    colsample_bytree=self.config.colsample_bytree,
                    min_child_weight=self.config.min_child_weight,
                    objective='multi:softmax',
                    num_class=3,
                    eval_metric='mlogloss',
                    use_label_encoder=False,
                    random_state=42,
                    n_jobs=-1,
                    verbosity=0,
                )
            else:
                return xgb.XGBClassifier(
                    n_estimators=self.config.n_estimators,
                    max_depth=self.config.max_depth,
                    learning_rate=self.config.learning_rate,
                    subsample=self.config.subsample,
                    colsample_bytree=self.config.colsample_bytree,
                    min_child_weight=self.config.min_child_weight,
                    eval_metric='logloss',
                    use_label_encoder=False,
                    random_state=42,
                    n_jobs=-1,
                    verbosity=0,
                )
        else:
            return GradientBoostingClassifier(
                n_estimators=min(self.config.n_estimators, 200),
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                subsample=self.config.subsample,
                random_state=42,
            )

    def train_timeframe(
        self,
        tf_name: str,
        X: pd.DataFrame,
        y: pd.Series,
    ) -> TimeframeResult:
        """Train and evaluate model for a single timeframe using walk-forward validation."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Training {self.config.symbol} {tf_name}: {len(X)} samples")
        logger.info(f"{'='*60}")

        # Label distribution
        label_counts = y.value_counts().to_dict()
        label_dist = {str(k): int(v) for k, v in label_counts.items()}
        logger.info(f"Label distribution: {label_dist}")

        # Filter out rows where label == 0 for the classifier (only trade when there's a signal)
        # But keep 0s as a third class so the model learns "no trade" situations
        n_classes = len(y.unique())

        # Remap labels: -1 -> 0, 0 -> 1, 1 -> 2 for XGBoost compatibility
        label_map = {-1: 0, 0: 1, 1: 2}
        y_mapped = y.map(label_map)

        # Train/test split (chronological)
        split_idx = int(len(X) * (1 - self.config.test_ratio))
        X_train_full, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train_full, y_test = y_mapped.iloc[:split_idx], y_mapped.iloc[split_idx:]

        # Standardize features
        scaler = StandardScaler()
        X_train_scaled = pd.DataFrame(
            scaler.fit_transform(X_train_full),
            columns=X_train_full.columns,
            index=X_train_full.index,
        )
        X_test_scaled = pd.DataFrame(
            scaler.transform(X_test),
            columns=X_test.columns,
            index=X_test.index,
        )

        # Walk-forward cross-validation on the training portion
        tscv = TimeSeriesSplit(n_splits=self.config.n_splits)
        wf_scores = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X_train_scaled)):
            X_tr = X_train_scaled.iloc[train_idx]
            y_tr = y_train_full.iloc[train_idx]
            X_val = X_train_scaled.iloc[val_idx]
            y_val = y_train_full.iloc[val_idx]

            model = self._build_model(n_classes)
            model.fit(X_tr, y_tr)

            preds = model.predict(X_val)
            acc = accuracy_score(y_val, preds)
            f1 = f1_score(y_val, preds, average='macro', zero_division=0)
            wf_scores.append({"fold": fold + 1, "accuracy": round(acc, 4), "f1_macro": round(f1, 4)})
            logger.info(f"  Fold {fold+1}: accuracy={acc:.4f}, f1_macro={f1:.4f} "
                        f"(train={len(train_idx)}, val={len(val_idx)})")

        # Final model trained on full training set
        final_model = self._build_model(n_classes)
        final_model.fit(X_train_scaled, y_train_full)

        # Evaluate on held-out test set
        test_preds = final_model.predict(X_test_scaled)
        test_acc = accuracy_score(y_test, test_preds)
        test_f1 = f1_score(y_test, test_preds, average='macro', zero_division=0)

        # Reverse map for readable report
        reverse_map = {0: 'Short (-1)', 1: 'No Trade (0)', 2: 'Long (+1)'}
        target_names = [reverse_map[i] for i in sorted(y_mapped.unique())]
        report = classification_report(
            y_test, test_preds,
            target_names=target_names,
            zero_division=0,
        )
        logger.info(f"\nFinal test results ({tf_name}):")
        logger.info(f"  Accuracy: {test_acc:.4f}")
        logger.info(f"  F1 Macro: {test_f1:.4f}")
        logger.info(f"\n{report}")

        # Feature importance
        if hasattr(final_model, 'feature_importances_'):
            importances = dict(zip(X.columns, final_model.feature_importances_))
            top20 = dict(sorted(importances.items(), key=lambda x: x[1], reverse=True)[:20])
        else:
            top20 = {}

        # Save model and scaler
        os.makedirs(self.config.model_dir, exist_ok=True)
        model_path = os.path.join(
            self.config.model_dir,
            f"{self.config.symbol}_{tf_name}_model.joblib",
        )
        scaler_path = os.path.join(
            self.config.model_dir,
            f"{self.config.symbol}_{tf_name}_scaler.joblib",
        )
        joblib.dump(final_model, model_path)
        joblib.dump(scaler, scaler_path)
        logger.info(f"Model saved: {model_path}")

        self.models[tf_name] = final_model
        self.scalers[tf_name] = scaler

        return TimeframeResult(
            timeframe=tf_name,
            total_bars=len(X) + len(X_test),
            train_bars=len(X_train_full),
            test_bars=len(X_test),
            label_distribution=label_dist,
            walk_forward_scores=wf_scores,
            final_test_accuracy=round(test_acc, 4),
            final_test_f1_macro=round(test_f1, 4),
            classification_report=report,
            feature_importance_top20={k: round(float(v), 6) for k, v in top20.items()},
            model_path=model_path,
        )

    def train_all(self, all_data: Dict[str, pd.DataFrame]) -> Dict[str, TimeframeResult]:
        """Train models for every configured timeframe, using higher TFs as context features."""
        from .feature_engine import build_full_feature_matrix
        from .data_fetcher import add_base_indicators

        results = {}

        for tf_name in self.config.timeframes:
            if tf_name not in all_data:
                logger.warning(f"Skipping {tf_name}: no data available")
                continue

            target_df = all_data[tf_name]

            # Gather higher-TF context
            context_tfs = self.config.context_timeframes.get(tf_name, [])
            higher_tf_data = {}
            for ctx_tf in context_tfs:
                if ctx_tf in all_data:
                    higher_tf_data[ctx_tf] = add_base_indicators(all_data[ctx_tf])

            logger.info(f"\nBuilding features for {tf_name} "
                        f"(context: {list(higher_tf_data.keys())})")

            X, y = build_full_feature_matrix(
                target_df,
                higher_tf_data=higher_tf_data,
                forward_bars=self.config.forward_bars,
                min_move_atr=self.config.min_move_atr,
            )

            if len(X) < 500:
                logger.warning(f"Skipping {tf_name}: only {len(X)} samples after feature engineering")
                continue

            result = self.train_timeframe(tf_name, X, y)
            results[tf_name] = result

        self.results = results
        self._save_summary(results)
        return results

    def _save_summary(self, results: Dict[str, TimeframeResult]):
        """Write a JSON summary of all timeframe results."""
        os.makedirs(self.config.model_dir, exist_ok=True)
        summary_path = os.path.join(self.config.model_dir, f"{self.config.symbol}_training_summary.json")

        summary = {
            "symbol": self.config.symbol,
            "trained_at": datetime.now().isoformat(),
            "config": {
                "forward_bars": self.config.forward_bars,
                "min_move_atr": self.config.min_move_atr,
                "n_splits": self.config.n_splits,
                "n_estimators": self.config.n_estimators,
                "max_depth": self.config.max_depth,
                "learning_rate": self.config.learning_rate,
            },
            "timeframes": {},
        }

        for tf_name, res in results.items():
            summary["timeframes"][tf_name] = {
                "total_bars": res.total_bars,
                "train_bars": res.train_bars,
                "test_bars": res.test_bars,
                "label_distribution": res.label_distribution,
                "walk_forward_scores": res.walk_forward_scores,
                "test_accuracy": res.final_test_accuracy,
                "test_f1_macro": res.final_test_f1_macro,
                "top_features": res.feature_importance_top20,
                "model_path": res.model_path,
            }

        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"\nTraining summary saved: {summary_path}")

        # Print comparison table
        logger.info(f"\n{'='*70}")
        logger.info(f"{'TIMEFRAME COMPARISON':^70}")
        logger.info(f"{'='*70}")
        logger.info(f"{'TF':<6} {'Bars':>8} {'Train':>8} {'Test':>8} {'Acc':>8} {'F1':>8}")
        logger.info(f"{'-'*70}")
        for tf_name, res in results.items():
            logger.info(
                f"{tf_name:<6} {res.total_bars:>8} {res.train_bars:>8} "
                f"{res.test_bars:>8} {res.final_test_accuracy:>8.4f} {res.final_test_f1_macro:>8.4f}"
            )
        logger.info(f"{'='*70}")


def load_trained_model(symbol: str, tf_name: str, model_dir: str = "models"):
    """Load a previously trained model and scaler for live prediction."""
    model_path = os.path.join(model_dir, f"{symbol}_{tf_name}_model.joblib")
    scaler_path = os.path.join(model_dir, f"{symbol}_{tf_name}_scaler.joblib")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"No trained model found at {model_path}")

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    return model, scaler
