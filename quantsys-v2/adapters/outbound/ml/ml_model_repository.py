"""
ML模型仓库适配器实现

将现有的 ml_helpers 模块封装为符合端口接口的适配器。
"""
import logging
from typing import Any, Optional, Tuple, List
from pathlib import Path
import pickle
from datetime import datetime

from domain.ports.ml_model_port import IMLModelRepository, IMLModelMetadataRepository
from adapters.shared.ml_helpers import (
    _get_model_repo,
    _resolve_latest_version,
    MODEL_DIR
)

logger = logging.getLogger(__name__)


class MLModelFileRepository(IMLModelRepository):
    """基于文件系统的ML模型仓库实现

    适配器模式：将现有的 ml_helpers 功能封装为端口接口实现
    """

    def __init__(self):
        """初始化模型仓库"""
        self._model_repo = _get_model_repo()
        self._model_dir = MODEL_DIR
        self._model_dir.mkdir(parents=True, exist_ok=True)

    def save_model(
        self,
        model: Any,
        model_type: str,
        version: str,
        metadata: dict
    ) -> Path:
        """保存模型到文件系统

        Args:
            model: 训练好的模型对象
            model_type: 模型类型（如 'lightgbm', 'xgboost'）
            version: 版本号（如 '20260821_143052'）
            metadata: 模型元数据

        Returns:
            保存的模型文件路径
        """
        model_path = self._model_dir / f"{model_type}_{version}.pkl"

        try:
            # 保存模型文件
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)

            logger.info(f"Model saved: {model_path}")

            # 保存元数据到数据库（如果 repo 可用）
            if self._model_repo is not None:
                try:
                    self._model_repo.create({
                        'model_type': model_type,
                        'version': version,
                        'train_date': metadata.get('train_date', datetime.now().isoformat()),
                        'metrics': metadata.get('metrics', {}),
                        'hyperparameters': metadata.get('hyperparameters', {}),
                        'dataset_info': metadata.get('dataset_info', {}),
                        'file_path': str(model_path)
                    })
                except Exception as e:
                    logger.warning(f"Failed to save model metadata to DB: {e}")

            return model_path

        except Exception as e:
            logger.error(f"Failed to save model {model_type}_{version}: {e}")
            raise

    def load_model(
        self,
        model_type: str,
        version: Optional[str] = None
    ) -> Tuple[Any, dict]:
        """加载模型

        Args:
            model_type: 模型类型
            version: 版本号，如果为None则加载最新版本

        Returns:
            (模型对象, 元数据字典)
        """
        # 解析版本号
        if version is None or version == 'latest':
            version = self.resolve_latest_version(model_type)
            if version is None:
                raise FileNotFoundError(f"No model found for type: {model_type}")

        model_path = self._model_dir / f"{model_type}_{version}.pkl"

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        try:
            # 加载模型文件
            with open(model_path, 'rb') as f:
                model = pickle.load(f)

            # 加载元数据
            metadata = {}
            if self._model_repo is not None:
                try:
                    db_record = self._model_repo.get_by_type_version(model_type, version)
                    if db_record:
                        metadata = {
                            'version': db_record.get('version'),
                            'train_date': db_record.get('train_date'),
                            'metrics': db_record.get('metrics', {}),
                            'hyperparameters': db_record.get('hyperparameters', {}),
                            'dataset_info': db_record.get('dataset_info', {})
                        }
                except Exception as e:
                    logger.warning(f"Failed to load model metadata from DB: {e}")

            logger.info(f"Model loaded: {model_path}")
            return model, metadata

        except Exception as e:
            logger.error(f"Failed to load model {model_type}_{version}: {e}")
            raise

    def resolve_latest_version(self, model_type: str) -> Optional[str]:
        """解析最新模型版本

        使用现有的 _resolve_latest_version 实现
        """
        return _resolve_latest_version(model_type)

    def list_versions(self, model_type: str) -> List[str]:
        """列出所有版本"""
        versions = []

        # 从文件系统扫描
        if self._model_dir.exists():
            for model_file in self._model_dir.glob(f"{model_type}_*.pkl"):
                # 提取版本号: xgboost_20260821_143052.pkl -> 20260821_143052
                stem = model_file.stem
                version = stem[len(model_type) + 1:]
                versions.append(version)

        # 按时间倒序排序（假设版本号格式为 YYYYMMDD_HHMMSS）
        versions.sort(reverse=True)

        return versions

    def get_model_path(
        self,
        model_type: str,
        version: Optional[str] = None
    ) -> Path:
        """获取模型文件路径"""
        if version is None or version == 'latest':
            version = self.resolve_latest_version(model_type)
            if version is None:
                raise FileNotFoundError(f"No model found for type: {model_type}")

        model_path = self._model_dir / f"{model_type}_{version}.pkl"

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        return model_path

    def delete_model(self, model_type: str, version: str) -> bool:
        """删除指定版本的模型"""
        model_path = self._model_dir / f"{model_type}_{version}.pkl"

        try:
            if model_path.exists():
                model_path.unlink()
                logger.info(f"Model deleted: {model_path}")

            # 删除数据库记录
            if self._model_repo is not None:
                try:
                    self._model_repo.delete_by_type_version(model_type, version)
                except Exception as e:
                    logger.warning(f"Failed to delete model metadata from DB: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to delete model {model_type}_{version}: {e}")
            return False

    def model_exists(self, model_type: str, version: Optional[str] = None) -> bool:
        """检查模型是否存在"""
        if version is None:
            # 检查是否存在任何版本
            versions = self.list_versions(model_type)
            return len(versions) > 0
        else:
            # 检查特定版本
            model_path = self._model_dir / f"{model_type}_{version}.pkl"
            return model_path.exists()


class MLModelMetadataDBRepository(IMLModelMetadataRepository):
    """基于数据库的ML模型元数据仓库实现"""

    def __init__(self):
        """初始化元数据仓库"""
        self._model_repo = _get_model_repo()

    def save_training_record(
        self,
        model_type: str,
        version: str,
        metrics: dict,
        training_params: dict,
        dataset_info: dict
    ) -> str:
        """保存训练记录"""
        if self._model_repo is None:
            logger.warning("Model repository not available, skipping metadata save")
            return ""

        try:
            record = self._model_repo.create({
                'model_type': model_type,
                'version': version,
                'train_date': datetime.now().isoformat(),
                'metrics': metrics,
                'hyperparameters': training_params,
                'dataset_info': dataset_info
            })
            return str(record.get('id', ''))
        except Exception as e:
            logger.error(f"Failed to save training record: {e}")
            raise

    def get_training_record(self, model_type: str, version: str) -> Optional[dict]:
        """获取训练记录"""
        if self._model_repo is None:
            return None

        try:
            return self._model_repo.get_by_type_version(model_type, version)
        except Exception as e:
            logger.warning(f"Failed to get training record: {e}")
            return None

    def list_training_history(
        self,
        model_type: str,
        limit: int = 10
    ) -> List[dict]:
        """列出训练历史"""
        if self._model_repo is None:
            return []

        try:
            records = self._model_repo.get_by_type(model_type, limit=limit)
            return records if records else []
        except Exception as e:
            logger.warning(f"Failed to list training history: {e}")
            return []

    def get_best_model_version(
        self,
        model_type: str,
        metric: str = 'f1'
    ) -> Optional[str]:
        """获取性能最好的模型版本"""
        records = self.list_training_history(model_type, limit=100)

        if not records:
            return None

        # 找出指定指标最高的版本
        best_record = None
        best_score = -float('inf')

        for record in records:
            metrics = record.get('metrics', {})
            if metric in metrics:
                score = metrics[metric]
                if score > best_score:
                    best_score = score
                    best_record = record

        if best_record:
            return best_record.get('version')

        return None
