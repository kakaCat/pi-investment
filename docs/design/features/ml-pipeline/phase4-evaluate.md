# ML Pipeline Phase 4: Evaluate 命令

## 目标
实现模型评估功能，输出准确率、精确率、召回率、F1分数。

## evaluate 命令实现

### ml_pipeline.py

```python
def _evaluate_signal_model() -> int:
    if SignalTrainer is None:
        print("[Evaluate] 错误: 缺少训练依赖", file=sys.stderr)
        return 1

    model_path = Path(__file__).resolve().parent / "models" / "signal_model.pkl"
    if not model_path.exists():
        print("[Evaluate] 错误: 模型文件不存在，请先训练", file=sys.stderr)
        return 1

    db = Database()
    try:
        # 读取测试数据
        symbols = db.get_all_symbols()[10:15]  # 使用不同的股票测试
        if not symbols:
            print("[Evaluate] 错误: 没有测试数据", file=sys.stderr)
            return 1

        feature_frames = []
        for symbol in symbols:
            df = db.get_klines(symbol, 500)
            if df.empty:
                continue
            featured = TechnicalFeatures.calculate_all(df)
            if featured.empty:
                continue
            feature_frames.append(featured)

        if not feature_frames:
            print("[Evaluate] 错误: 没有可用测试数据", file=sys.stderr)
            return 1

        test_df = pd.concat(feature_frames, ignore_index=True)
        y_true = test_df["label"]
        X = test_df.drop(columns=["label", "symbol", "date"], errors="ignore")
        X = X.select_dtypes(include="number")

        # 加载模型预测
        predictor = SignalPredictor(str(model_path))
        y_pred_proba = predictor.predict(X)
        y_pred = (y_pred_proba > 0.6).astype(int)

        # 计算指标
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)

        print("[Evaluate] 模型评估结果")
        print(f"准确率 (Accuracy): {accuracy:.2%}")
        print(f"精确率 (Precision): {precision:.2%}")
        print(f"召回率 (Recall): {recall:.2%}")
        print(f"F1分数: {f1:.2%}")
        print(f"测试样本数: {len(y_true)}")
        return 0
    finally:
        db.close()
```

## 实现步骤

1. 更新 ml_pipeline.py 添加 _evaluate_signal_model()
2. 在 evaluate 命令中调用
3. 测试: python ml-pipeline/ml_pipeline.py evaluate
