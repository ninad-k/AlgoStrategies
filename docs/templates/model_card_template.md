# Model Card: [Name]

## Overview
- **Task**: [Classification / Regression / Time Series Forecasting / RL]
- **Architecture**: [LSTM / XGBoost / Transformer / Ensemble / etc.]
- **Target**: [Price direction / Volatility / Signal generation]
- **Version**: v1.0

## Features
| Feature | Source | Description |
|---------|--------|-------------|
| | | |

## Training
- **Dataset**: [period, source, size]
- **Train/Val/Test split**: [70/15/15]
- **Preprocessing**: [normalization, windowing, etc.]
- **Hyperparameters**: see `models/configs/[name].yaml`

## Performance
| Metric | Train | Validation | Test |
|--------|-------|-----------|------|
| Accuracy / MAE | | | |
| Sharpe (if signal-based) | | | |

## Retraining
- **Frequency**: [weekly / monthly / on drift detection]
- **Drift detection method**:
- **Pipeline location**: `models/training/[script]`

## Limitations
-

## Changelog
| Date | Version | Change |
|------|---------|--------|
|      | v1.0    | Initial version |
