#!/usr/bin/env python3
"""独立模型训练脚本（对齐 /api/ml/train 数据流，避免 HTTP 超时）

修复记录（2026-08-20, RFC003-P3, agent-dh）:
- 旧版 Bug: extract_features 只产出特征不产出 target，`metadata["target"]` 必然 KeyError，
  脚本在训练前必然崩溃，永远无法产出模型
- 旧版 Segfault: 数据进程内 polars/torch/sklearn 多份 OpenMP 与 lightgbm/xgboost 的
  Homebrew libomp 混载，worker 线程 fit 时段错误（__kmp_suspend_initialize_thread）。
  本版双重防护：POLARS_MAX_THREADS=4（import 前）+ 训练在干净子进程执行（tools/_train_worker.py）
- 配套修复: trainer.py 的 xgboost 改为延迟导入（与 lightgbm 一致），
  训练进程只加载所需后端的 OpenMP
- 本版数据流镜像 ml_async.ml_train：
  因子取自 DB 新管线（小写因子，R2 回填后约 230 交易日历史），
  target = 次日涨跌方向，MLTrainer 训练，结果写回模型仓库（model_evaluate 可读）

用法:
    source activate-py313.sh
    python tools/train_lightgbm_simple.py --model-type lightgbm --limit 100
"""
import os

# 必须在 import polars/numpy 之前设置：限制 polars 线程，
# 避免与 NumPy 内存分配器冲突导致 Segmentation Fault（2026-08-20 实测复现/验证）
os.environ.setdefault("POLARS_MAX_THREADS", "4")

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="独立模型训练（对齐 /api/ml/train 数据流）")
    parser.add_argument("--model-type", default="lightgbm", choices=["xgboost", "lightgbm"])
    parser.add_argument("--limit", type=int, default=100, help="训练股票数（默认100，验证后可提到500）")
    parser.add_argument("--start-date", default="2025-09-04")
    parser.add_argument("--end-date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--test-size", type=float, default=0.2)
    args = parser.parse_args()

    from adapters.shared.services import get_stock_repo, get_kline_repo, get_factor_repo
    from adapters.shared.ml_helpers import (
        MODEL_DIR, _json, _get_model_repo, _normalize_kline,
    )

    stock_repo = get_stock_repo()
    kline_repo = get_kline_repo()
    factor_repo = get_factor_repo()

    print(f"=== 模型训练（{args.model_type}） ===")
    print(f"数据范围: {args.start_date} ~ {args.end_date}, 股票数上限: {args.limit}\n")

    # 1. 股票列表
    stocks = stock_repo.get_all(limit=args.limit)
    symbols = [s["symbol"] for s in stocks]
    print(f"实际训练股票: {len(symbols)} 只")

    # 2. K线（供 target 计算次日涨跌）
    klines_dict: dict = {}

    def _fetch_one_kline(sym: str):
        try:
            rows = kline_repo.get_daily_klines(sym, args.start_date, args.end_date)
            import polars as pl
            if isinstance(rows, pl.DataFrame):
                if rows.is_empty():
                    return sym, None
                rows = rows.to_dicts()
            if rows:
                return sym, [_normalize_kline(r) for r in rows]
        except Exception:
            logger.debug("Skip %s (no kline data)", sym)
        return sym, None

    print("加载K线数据...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch_one_kline, s): s for s in symbols}
        for i, future in enumerate(as_completed(futures)):
            sym, rows = future.result()
            if rows:
                klines_dict[sym] = rows
            if (i + 1) % 20 == 0:
                print(f"  K线已加载 {i + 1}/{len(symbols)}")
    print(f"成功加载 {len(klines_dict)} 只股票K线\n")

    # 3. 因子 + target（次日涨跌方向），与 ml_async.ml_train 逐行对齐
    all_rows: list = []

    def _process_one_symbol(sym: str):
        try:
            factors_data = factor_repo.get_factors_range(sym, args.start_date, args.end_date)
            # get_factors_range 返回 polars DataFrame：bool(df) 抛 TypeError，
            # 必须用 is_empty + iter_rows(named=True)
            if factors_data is None or factors_data.is_empty():
                return []
            by_date: dict = {}
            for fv in factors_data.iter_rows(named=True):
                d = str(fv.get("factor_date") or fv.get("date", ""))
                if not d:
                    continue
                by_date.setdefault(d, {})[fv["factor_name"]] = float(fv.get("factor_value", 0) or 0)
            close_map: dict = {}
            for k in klines_dict.get(sym, []):
                d = str(k.get("date", k.get("trade_date", "")))
                close_map[d] = float(k.get("close", 0))
            rows = []
            sorted_dates = sorted(by_date.keys())
            for i in range(len(sorted_dates) - 1):
                cur_date, next_date = sorted_dates[i], sorted_dates[i + 1]
                cur_close = close_map.get(cur_date, 0)
                next_close = close_map.get(next_date, 0)
                if cur_close <= 0:
                    continue
                row = dict(by_date[cur_date])
                row["__target"] = 1 if next_close > cur_close else 0
                rows.append(row)
            return rows
        except Exception:
            logger.debug("Skip factor data for %s", sym)
            return []

    print("构建训练样本（DB因子 × 次日涨跌target）...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_process_one_symbol, s): s for s in klines_dict}
        for future in as_completed(futures):
            all_rows.extend(future.result())

    if len(all_rows) < 10:
        print(f"❌ 有效样本不足 (仅有 {len(all_rows)} 条)")
        sys.exit(1)

    X = pd.DataFrame(all_rows)
    y = X.pop("__target")
    X = X.fillna(X.median(numeric_only=True)).fillna(0)
    # 注意：不在此标准化。StandardScaler 在训练子进程内拟合并随模型保存
    # （{model_type}_{version}_scaler.pkl），保证训练/预测特征空间一致。
    print(f"样本: {X.shape[0]} 条 × {X.shape[1]} 特征; target 分布: {y.value_counts().to_dict()}\n")

    # 4. 训练（子进程隔离：本进程已加载 polars/torch/sklearn 等多份 OpenMP，
    #    直接 fit 会段错误；worker 只加载 numpy/pandas/sklearn/目标后端）
    import json
    import subprocess
    import tempfile
    import numpy as np

    version = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"训练 {args.model_type} 模型（子进程隔离）...")
    with tempfile.NamedTemporaryFile(suffix=".npz", delete=False) as f:
        npz_path = f.name
    np.savez_compressed(npz_path, X=X.values, y=y.values,
                        columns=np.array(json.dumps(list(X.columns))))
    print(f"  训练数据集: {npz_path}（保留供调试/复训）")

    worker = Path(__file__).parent / "_train_worker.py"
    proc = subprocess.run(
        [sys.executable, str(worker), npz_path, args.model_type, version, str(args.test_size)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"❌ 训练子进程失败 (exit={proc.returncode}):\n{proc.stderr[-2000:]}")
        sys.exit(1)
    result_line = [l for l in proc.stdout.splitlines() if l.startswith("RESULT:")]
    if not result_line:
        print(f"❌ 子进程未返回结果:\n{proc.stdout[-2000:]}")
        sys.exit(1)
    results = json.loads(result_line[-1][len("RESULT:"):])
    print(f"  训练完成 (version={version})")

    model_path = str(MODEL_DIR / f"{args.model_type}_{version}.pkl")
    print(f"模型文件已保存: {model_path}")

    # 5. 写回模型仓库（model_evaluate / /api/ml/evaluate 可读）
    def _to_native(val):
        import numpy as _np
        if isinstance(val, dict):
            return {k: _to_native(v) for k, v in val.items()}
        if isinstance(val, (list, tuple)):
            return [_to_native(v) for v in val]
        if isinstance(val, _np.floating):
            return float(val)
        if isinstance(val, _np.integer):
            return int(val)
        if isinstance(val, _np.bool_):
            return bool(val)
        return val

    feature_importance = results.get("feature_importance", {})
    _get_model_repo()._ensure_db(max_retries=5, retry_delay=2.0)
    _get_model_repo().save_model(_to_native({
        "model_type": args.model_type, "version": version, "model_path": model_path,
        "train_accuracy": results.get("train_accuracy"), "test_accuracy": results.get("test_accuracy"),
        "precision": results.get("test_precision"), "recall": results.get("test_recall"),
        "f1_score": results.get("test_f1"), "roc_auc": results.get("test_roc_auc"),
        "feature_count": len(X.columns), "train_samples": int(len(X)),
        "feature_importance": _json.dumps(feature_importance),
        "training_params": _json.dumps({}), "training_report": _json.dumps(results),
        "status": "ready", "train_date": datetime.now(timezone.utc).isoformat(),
    }))
    print("模型元数据已写回仓库")

    # 6. 结果摘要 + 上线门禁（RFC003-P3: AUC>0.55 且 IR>0 才允许接入决策加权）
    auc = results.get("test_roc_auc") or 0.0
    print("\n=== 训练结果 ===")
    print(f"train_acc={results.get('train_accuracy'):.4f}  test_acc={results.get('test_accuracy'):.4f}")
    print(f"precision={results.get('test_precision'):.4f}  recall={results.get('test_recall'):.4f}  "
          f"f1={results.get('test_f1'):.4f}")
    print(f"ROC AUC = {auc:.4f}  (上线门禁 > 0.55)")
    if auc > 0.55:
        print("✅ 达标，可进入 model_evaluate 复核流程")
    else:
        print("❌ 未达标，按 RFC003 原则不接入决策加权（记录原因，回 P1/P2 改进数据与特征）")
    top = sorted(feature_importance.items(), key=lambda kv: kv[1], reverse=True)[:10]
    if top:
        print("\nTop10 特征重要性:")
        for name, imp in top:
            print(f"  {name}: {imp:.4f}")
    print(f"\nversion = {version}")


if __name__ == "__main__":
    main()
