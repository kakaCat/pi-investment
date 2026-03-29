#!/usr/bin/env python3
"""ML Pipeline - 机器学习管道"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from db import Database
from backtesting.engine import BacktestEngine
from features.technical import TechnicalFeatures
from inference.predictor import SignalPredictor

try:
    from training.trainer import SignalTrainer
except ModuleNotFoundError:
    SignalTrainer = None


def _train_signal_model() -> int:
    if SignalTrainer is None:
        print("[Train] 错误: 缺少训练依赖，请先安装 xgboost", file=sys.stderr)
        return 1

    db = Database()

    try:
        symbols = db.get_all_symbols()[:100]
        if not symbols:
            print("[Train] 错误: 没有可用于训练的数据", file=sys.stderr)
            return 1

        feature_frames = []
        for symbol in symbols:
            df = db.get_klines(symbol, 500)
            if df.empty:
                continue

            featured_df = TechnicalFeatures.calculate_all(df)
            if featured_df.empty:
                continue

            feature_frames.append(featured_df)

        if not feature_frames:
            print("[Train] 错误: 没有可用于训练的数据", file=sys.stderr)
            return 1

        training_df = pd.concat(feature_frames, ignore_index=True)
        y = training_df["label"]
        X = training_df.drop(columns=["label"], errors="ignore")
        X = X.drop(columns=["symbol", "date"], errors="ignore")
        X = X.select_dtypes(include="number")

        if X.empty or y.empty:
            print("[Train] 错误: 没有可用于训练的数据", file=sys.stderr)
            return 1

        model_dir = Path(__file__).resolve().parent / "models"
        trainer = SignalTrainer(model_dir=str(model_dir))
        result = trainer.train(X, y)
        model_path = trainer.save("signal_model.pkl")

        print("[Train] 训练完成")
        print(f"model_path: {model_path}")
        print(f"train_score: {result['train_score']:.4f}")
        print(f"test_score: {result['test_score']:.4f}")
        print(f"n_samples: {result['n_samples']}")
        return 0
    finally:
        db.close()


def _predict_signal(symbol: str) -> int:
    db = Database()

    try:
        df = db.get_klines(symbol, 500)
        if df.empty:
            print(f"[Predict] 错误: 没有 {symbol} 的数据")
            return 1

        featured = TechnicalFeatures.calculate_all(df)
        if featured.empty:
            print("[Predict] 错误: 特征计算失败")
            return 1

        X = featured.drop(columns=["label", "symbol", "date"], errors="ignore")
        X = X.select_dtypes(include="number")

        predictor = SignalPredictor()
        proba = predictor.predict(X.tail(1))

        print(f"[Predict] {symbol}")
        print(f"上涨概率: {proba[0]:.2%}")
        print(f"信号: {'买入' if proba[0] > 0.6 else '观望'}")
        return 0
    finally:
        db.close()


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
        symbols = db.get_all_symbols()[10:15]
        if not symbols:
            print("[Evaluate] 错误: 没有测试数据", file=sys.stderr)
            return 1

        feature_frames = []
        for symbol in symbols:
            df = db.get_klines(symbol, 500)
            if df.empty:
                continue

            featured_df = TechnicalFeatures.calculate_all(df)
            if featured_df.empty:
                continue

            feature_frames.append(featured_df)

        if not feature_frames:
            print("[Evaluate] 错误: 没有可用测试数据", file=sys.stderr)
            return 1

        test_df = pd.concat(feature_frames, ignore_index=True)
        y_true = test_df["label"]
        X = test_df.drop(columns=["label", "symbol", "date"], errors="ignore")
        X = X.select_dtypes(include="number")

        if X.empty or y_true.empty:
            print("[Evaluate] 错误: 没有可用测试数据", file=sys.stderr)
            return 1

        predictor = SignalPredictor(str(model_path))
        y_pred_proba = predictor.predict(X)
        y_pred = (y_pred_proba > 0.6).astype(int)

        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

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


def _backtest_signal() -> int:
    db = Database()

    try:
        symbols = db.get_all_symbols()[:5]
        predictor = SignalPredictor()

        results = []
        for symbol in symbols:
            df = db.get_klines(symbol, 500)
            if df.empty:
                continue

            featured = TechnicalFeatures.calculate_all(df)
            if featured.empty:
                continue

            X = featured.drop(columns=["label", "symbol", "date"], errors="ignore")
            X = X.select_dtypes(include="number")

            proba = predictor.predict(X)
            signals = (proba > 0.6).astype(int)

            engine = BacktestEngine()
            result = engine.run(featured[["date", "close"]], pd.Series(signals))
            results.append({"symbol": symbol, **result})

        print("[Backtest] 回测结果")
        for result in results:
            print(
                f"{result['symbol']}: 收益率 {result['return']:.2f}%, "
                f"交易次数 {result['trades']}, "
                f"胜率 {result['win_rate']:.2f}%, "
                f"最大回撤 {result['max_drawdown']:.2f}%, "
                f"夏普比率 {result['sharpe_ratio']:.2f}"
            )
        return 0
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='ML Pipeline')
    subparsers = parser.add_subparsers(dest='command')

    # train 命令
    train_parser = subparsers.add_parser('train')
    train_parser.add_argument('--model', default='signal')

    # predict 命令
    predict_parser = subparsers.add_parser('predict')
    predict_parser.add_argument('--model', default='signal')
    predict_parser.add_argument('--symbol', required=True)

    # evaluate 命令
    evaluate_parser = subparsers.add_parser('evaluate')
    evaluate_parser.add_argument('--model', default='signal')

    # backtest 命令
    backtest_parser = subparsers.add_parser('backtest')
    backtest_parser.add_argument('--model', default='signal')

    # list-models 命令
    list_parser = subparsers.add_parser('list-models')

    args = parser.parse_args(argv)

    if args.command == 'train':
        if args.model != 'signal':
            print(f"[Train] 错误: 不支持的模型 {args.model}", file=sys.stderr)
            return 1
        return _train_signal_model()
    elif args.command == 'predict':
        if args.model != 'signal':
            print(f"[Predict] 错误: 不支持的模型 {args.model}", file=sys.stderr)
            return 1
        return _predict_signal(args.symbol)
    elif args.command == 'evaluate':
        if args.model != 'signal':
            print(f"[Evaluate] 错误: 不支持的模型 {args.model}", file=sys.stderr)
            return 1
        print(f"[Evaluate] 评估模型: {args.model}")
        return _evaluate_signal_model()
    elif args.command == 'backtest':
        if args.model != 'signal':
            print(f"[Backtest] 错误: 不支持的模型 {args.model}", file=sys.stderr)
            return 1
        return _backtest_signal()
    elif args.command == 'list-models':
        print("[List] 可用模型: signal")
    else:
        parser.print_help()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
