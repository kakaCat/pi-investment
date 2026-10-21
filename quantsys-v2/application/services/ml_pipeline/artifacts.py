"""ML 模型工件（artifact）存取约定

背景（2026-10-19 修复）：`{model_type}_{version}_scaler.pkl` 的命名此前散落在
3 处（tools/_train_worker.py 保存、/api/ml/predict 读取、两处训练路径不保存），
导致 2026-08-20 之后每日重训的模型全部没有 scaler 存档，预测侧因此落入
legacy「K线→FactorRegistry」路径，特征与训练时的 DB 因子错配（S1 复发形态）。
本模块把命名与保存收敛为单一约定，训练侧与预测侧必须都走这里。
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = Path(".pi-invest/ml/models")


def scaler_path(
    model_type: str,
    version: str,
    model_dir: Path | str = DEFAULT_MODEL_DIR,
) -> Path:
    """scaler 存档路径（训练保存与预测加载的唯一命名约定）。"""
    return Path(model_dir) / f"{model_type}_{version}_scaler.pkl"


def save_scaler(
    scaler: Any,
    model_type: str,
    version: str,
    model_dir: Path | str = DEFAULT_MODEL_DIR,
) -> Path:
    """把训练时拟合的 scaler 随模型落盘，返回存档路径。

    预测时（/api/ml/predict）必须用同一个 scaler 还原特征空间；
    没有它，预测会落入 legacy 特征路径，输出不可信。
    """
    path = scaler_path(model_type, version, model_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(scaler, f)
    logger.info("Scaler saved to %s", path)
    return path
