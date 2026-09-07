#!/usr/bin/env python3
"""训练子进程 worker（被 train_lightgbm_simple.py 调用，不应直接运行）

存在意义（2026-08-20, RFC003-P3 segfault 修复）：
数据加载进程会引入 polars/torch/sklearn 等多份 OpenMP 运行时，
与 lightgbm/xgboost 依赖的 Homebrew libomp 混载后，
OpenMP worker 线程在 fit 时段错误（__kmp_suspend_initialize_thread）。
因此训练在干净子进程中执行：只 import numpy/pandas/sklearn/目标后端。

输入: npz（X: float 矩阵, y: 0/1, columns: 特征名 json）
输出: stdout 最后一行 `RESULT:{json}`，包含训练指标与特征重要性
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    npz_path, model_type, version, test_size = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])

    import numpy as np
    import pandas as pd

    data = np.load(npz_path, allow_pickle=False)
    columns = json.loads(str(data["columns"].item()))
    X = pd.DataFrame(data["X"], columns=columns)
    y = pd.Series(data["y"])

    # 标准化必须在训练进程内拟合并随模型保存：
    # 预测时（/api/ml/predict）必须使用同一个 scaler，否则特征空间不一致
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    X = pd.DataFrame(scaler.fit_transform(X), columns=X.columns)

    from application.services.ml_pipeline.trainer import MLTrainer
    trainer = MLTrainer(model_type=model_type)
    results = trainer.train(X, y, test_size=test_size, params={})
    trainer.save_model(version=version)

    import pickle
    scaler_path = trainer.model_dir / f"{model_type}_{version}_scaler.pkl"
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)

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

    print("RESULT:" + json.dumps(_to_native(results)))


if __name__ == "__main__":
    main()
