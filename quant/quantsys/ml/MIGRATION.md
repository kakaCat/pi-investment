# ML Module Migration Guide

## Why Migrate?

The old `signal_trainer.py` has **critical issues** that make model evaluation unreliable:

### Critical Issue: Training Set = Test Set

```python
# ❌ OLD CODE (signal_trainer.py line 132)
model.fit(X, y)
accuracy = model.score(X, y)  # Evaluating on training data!
```

This is **data leakage**. The model sees the test data during training, leading to:
- Inflated accuracy scores (looks good but isn't)
- Poor generalization to new data
- Overfitting goes undetected

### Other Issues
- Only 8 basic features (insufficient for complex patterns)
- No cross-validation (can't detect overfitting)
- No hyperparameter tuning (suboptimal performance)
- Simple label definition (no flexibility)

## Migration Steps

### Step 1: Update Imports

**Before:**
```python
from ml.signal_trainer import train_model
```

**After:**
```python
from ml.refactored_trainer import train_model
```

### Step 2: Update Function Calls

**Before:**
```python
result = train_model(days=30, min_samples=50)
```

**After:**
```python
result = train_model(
    days=60,              # Increased for more data
    min_samples=100,      # Higher threshold for reliability
    model_type='xgboost',
    tune_hyperparams=False,
    return_threshold=0.02
)
```

### Step 3: Update Result Handling

The result structure is similar but has additional fields:

**New fields:**
```python
result = {
    'cv_results': {
        'mean_scores': {'accuracy': 0.65, 'auc': 0.70, ...},
        'std_scores': {'accuracy': 0.05, ...}
    },
    'test_metrics': {
        'accuracy': 0.63,
        'auc': 0.68,
        'precision': 0.60,
        'recall': 0.65,
        'f1': 0.62
    },
    'data': {
        'total_samples': 500,
        'train_samples': 400,
        'test_samples': 100,
        'n_features': 56  # Now 50+ features!
    }
}
```

## Code Examples

### Basic Training
```python
from ml.refactored_trainer import train_model

result = train_model(
    days=60,
    min_samples=100,
    model_type='xgboost'
)

if 'error' in result:
    print(f"Training failed: {result['error']}")
else:
    print(f"CV Accuracy: {result['cv_results']['mean_scores']['accuracy']:.4f}")
    print(f"Test Accuracy: {result['test_metrics']['accuracy']:.4f}")
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

### Custom Return Threshold
```python
# Adjust threshold based on your strategy
result = train_model(
    days=60,
    return_threshold=0.03  # 3% return = positive (more conservative)
)
```

## TypeScript Integration

If you're calling from TypeScript (via python-caller.ts):

**Before:**
```typescript
const result = await callPython('ml.signal_trainer', 'train_model', {
    days: 30,
    min_samples: 50
});
```

**After:**
```typescript
const result = await callPython('ml.refactored_trainer', 'train_model', {
    days: 60,
    min_samples: 100,
    model_type: 'xgboost',
    tune_hyperparams: false,
    return_threshold: 0.02
});
```

## Validation Checklist

After migration, verify:

1. ✅ **CV-Test Gap < 0.1**: No significant overfitting
   ```python
   cv_acc = result['cv_results']['mean_scores']['accuracy']
   test_acc = result['test_metrics']['accuracy']
   gap = cv_acc - test_acc
   assert gap < 0.1, f"Overfitting detected: gap={gap}"
   ```

2. ✅ **Test Accuracy > 0.55**: Better than random
   ```python
   assert result['test_metrics']['accuracy'] > 0.55
   ```

3. ✅ **AUC > 0.6**: Reasonable discrimination
   ```python
   assert result['test_metrics']['auc'] > 0.6
   ```

4. ✅ **50+ Features**: Rich feature set
   ```python
   assert result['data']['n_features'] >= 50
   ```

## Performance Expectations

### Old Module (signal_trainer.py)
- Training accuracy: ~0.85 (inflated due to data leakage)
- Real performance: Unknown (no proper test set)
- Features: 8
- Validation: None

### New Module (refactored_trainer.py)
- CV accuracy: 0.60-0.70 (realistic)
- Test accuracy: 0.58-0.68 (honest evaluation)
- Features: 50+
- Validation: 5-fold time series CV + held-out test set

**Note:** Lower numbers are expected because we're now measuring real performance!

## Troubleshooting

### "Insufficient samples" Error
```python
# Increase days or wait for more signals
result = train_model(days=90, min_samples=80)
```

### "Severe class imbalance" Warning
```python
# Adjust return threshold
result = train_model(return_threshold=0.015)  # Lower threshold
```

### Low Accuracy
- Collect more signals (increase `days`)
- Try ensemble model (`model_type='ensemble'`)
- Enable hyperparameter tuning (`tune_hyperparams=True`)

### Missing Dependencies
```bash
# Required
pip install xgboost scikit-learn numpy

# Optional (for advanced features)
pip install lightgbm optuna matplotlib
```

## Testing

Run the test suite to verify everything works:

```bash
cd python
python test_ml_refactor.py
```

Expected output:
```
✅ PASS: Feature Engineering
✅ PASS: Time Series Cross-Validation
✅ PASS: Basic Training
✅ PASS: Hyperparameter Tuning

Total: 4/4 tests passed
```

## Rollback Plan

If you need to rollback temporarily:

```python
# Old API still works (with deprecation warning)
from ml.signal_trainer import train_model

result = train_model(days=30, min_samples=50)
```

But **do not use this for production** due to validation issues.

## Questions?

See `python/ml/README.md` for detailed documentation.
