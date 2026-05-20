# ML Module Refactoring

## Overview

Complete refactoring of the ML module to fix critical issues and implement best practices.

## Problems Fixed

### 1. ❌ Training Set = Test Set (CRITICAL)
**Before:**
```python
model.fit(X, y)
accuracy = model.score(X, y)  # ❌ Evaluating on training data!
```

**After:**
```python
# Time-aware train/test split
X_train, X_test, y_train, y_test = tscv.get_train_test_split(X, y, test_ratio=0.2)

# 5-fold time series cross-validation
cv_results = tscv.validate_model(model, X_train, y_train)

# Final evaluation on held-out test set
test_accuracy = model.score(X_test, y_test)
```

### 2. ❌ Only 8 Basic Features
**Before:** 8 simple features (RSI, MA ratios, MACD, etc.)

**After:** 50+ engineered features:
- Price features (6): returns at multiple horizons
- Volatility features (4): Bollinger Band metrics
- Technical indicators (12): RSI, MACD, momentum
- Volume features (4): volume ratios and surges
- Time features (6): day of week, quarter end, etc.
- Statistical features (6): skewness, kurtosis, percentiles
- Cross features (10): interaction terms (RSI × volume, etc.)

### 3. ❌ No Hyperparameter Tuning
**After:** Optuna-based Bayesian optimization
```python
trainer = ModelTrainer(tune_hyperparams=True, n_trials=50)
```

### 4. ❌ Simple Label Definition
**Before:** `label = 1 if future_return > 0.02 else 0`

**After:** Configurable threshold with class balance monitoring
```python
train_model(return_threshold=0.02)  # Adjustable
```

### 5. ❌ No Model Ensemble
**After:** Stacking ensemble with XGBoost + LightGBM + RandomForest

## New Module Structure

```
python/ml/
├── features/
│   ├── feature_engineering.py    # 50+ features
│   ├── feature_selection.py      # Statistical + model-based selection
│   └── feature_importance.py     # Analysis and visualization
├── models/
│   ├── xgboost_model.py         # XGBoost wrapper
│   ├── lightgbm_model.py        # LightGBM wrapper
│   └── ensemble.py              # Stacking ensemble
├── training/
│   ├── cross_validation.py      # Time series CV ⭐
│   ├── hyperparameter_tuning.py # Optuna optimization
│   └── trainer.py               # Unified training framework
├── prediction/
│   └── predictor.py             # Prediction service
└── refactored_trainer.py        # New training entry point
```

## Usage

### Basic Training
```python
from ml.refactored_trainer import train_model

result = train_model(
    days=60,              # Use 60 days of signals
    min_samples=100,      # Minimum samples required
    model_type='xgboost', # or 'lightgbm', 'ensemble'
    tune_hyperparams=False,
    return_threshold=0.02 # 2% return = positive
)
```

### With Hyperparameter Tuning
```python
result = train_model(
    days=60,
    model_type='xgboost',
    tune_hyperparams=True,
    n_trials=50  # Optuna trials
)
```

### Ensemble Model
```python
result = train_model(
    days=60,
    model_type='ensemble'  # XGBoost + LightGBM + RandomForest
)
```

## Expected Performance

**Target Metrics:**
- CV Accuracy: > 60%
- Test Accuracy: > 60%
- AUC: > 0.65
- CV-Test gap: < 0.1 (avoid overfitting)

## Testing

Run the test suite:
```bash
cd python
python test_ml_refactor.py
```

Tests:
1. ✅ Feature engineering (50+ features)
2. ✅ Time series cross-validation
3. ✅ Model training with proper validation
4. ✅ Hyperparameter tuning (optional)

## Migration Path

### Old API (Deprecated)
```python
from ml.signal_trainer import train_model
result = train_model(days=30, min_samples=50)
```

### New API
```python
from ml.refactored_trainer import train_model
result = train_model(
    days=60,
    min_samples=100,
    model_type='xgboost',
    tune_hyperparams=False
)
```

## Key Improvements

1. **No Data Leakage**: Time series CV ensures training data always comes before test data
2. **Rich Features**: 50+ engineered features capture complex patterns
3. **Proper Validation**: 5-fold CV + held-out test set
4. **Hyperparameter Optimization**: Bayesian optimization with Optuna
5. **Model Ensemble**: Stacking for better generalization
6. **Monitoring**: Class balance, overfitting detection, feature importance

## Dependencies

Required:
```bash
pip install xgboost scikit-learn numpy
```

Optional (for advanced features):
```bash
pip install lightgbm optuna matplotlib
```

## Next Steps

1. Run test suite to verify installation
2. Train initial model with basic settings
3. Analyze feature importance
4. Tune hyperparameters if needed
5. Consider ensemble model for production
