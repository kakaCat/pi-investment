"""
ML模型管理端口接口

定义ML模型仓库的抽象接口，用于：
- 模型持久化（保存/加载）
- 版本管理
- 模型元数据管理

依赖倒置：应用层依赖此接口，适配器层实现此接口
"""
from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple, List
from pathlib import Path


class IMLModelRepository(ABC):
    """ML模型仓库接口

    负责ML模型的持久化存储和版本管理。
    实现可以基于文件系统、对象存储或数据库。
    """

    @abstractmethod
    def save_model(
        self,
        model: Any,
        model_type: str,
        version: str,
        metadata: dict
    ) -> Path:
        """保存模型到仓库

        Args:
            model: 训练好的模型对象
            model_type: 模型类型（如 'lightgbm', 'xgboost'）
            version: 版本号（如 '2026-08-21_v1'）
            metadata: 模型元数据（训练参数、指标等）

        Returns:
            保存的模型文件路径

        Raises:
            ModelSaveError: 保存失败时抛出
        """
        pass

    @abstractmethod
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

        Raises:
            ModelNotFoundError: 模型不存在时抛出
            ModelLoadError: 加载失败时抛出
        """
        pass

    @abstractmethod
    def resolve_latest_version(self, model_type: str) -> Optional[str]:
        """解析最新模型版本

        Args:
            model_type: 模型类型

        Returns:
            最新版本号，如果没有任何版本则返回None
        """
        pass

    @abstractmethod
    def list_versions(self, model_type: str) -> List[str]:
        """列出所有版本

        Args:
            model_type: 模型类型

        Returns:
            版本号列表，按时间倒序排列
        """
        pass

    @abstractmethod
    def get_model_path(
        self,
        model_type: str,
        version: Optional[str] = None
    ) -> Path:
        """获取模型文件路径

        Args:
            model_type: 模型类型
            version: 版本号，如果为None则返回最新版本路径

        Returns:
            模型文件路径

        Raises:
            ModelNotFoundError: 模型不存在时抛出
        """
        pass

    @abstractmethod
    def delete_model(self, model_type: str, version: str) -> bool:
        """删除指定版本的模型

        Args:
            model_type: 模型类型
            version: 版本号

        Returns:
            删除是否成功
        """
        pass

    @abstractmethod
    def model_exists(self, model_type: str, version: Optional[str] = None) -> bool:
        """检查模型是否存在

        Args:
            model_type: 模型类型
            version: 版本号，如果为None则检查是否存在任何版本

        Returns:
            模型是否存在
        """
        pass


class IMLModelMetadataRepository(ABC):
    """ML模型元数据仓库接口

    负责模型训练历史、性能指标等元数据的持久化。
    与模型文件分离存储，便于查询和分析。
    """

    @abstractmethod
    def save_training_record(
        self,
        model_type: str,
        version: str,
        metrics: dict,
        training_params: dict,
        dataset_info: dict
    ) -> str:
        """保存训练记录

        Args:
            model_type: 模型类型
            version: 版本号
            metrics: 性能指标（accuracy, f1, auc等）
            training_params: 训练参数
            dataset_info: 数据集信息

        Returns:
            记录ID
        """
        pass

    @abstractmethod
    def get_training_record(self, model_type: str, version: str) -> Optional[dict]:
        """获取训练记录

        Args:
            model_type: 模型类型
            version: 版本号

        Returns:
            训练记录字典，不存在则返回None
        """
        pass

    @abstractmethod
    def list_training_history(
        self,
        model_type: str,
        limit: int = 10
    ) -> List[dict]:
        """列出训练历史

        Args:
            model_type: 模型类型
            limit: 返回记录数量限制

        Returns:
            训练记录列表，按时间倒序
        """
        pass

    @abstractmethod
    def get_best_model_version(
        self,
        model_type: str,
        metric: str = 'f1'
    ) -> Optional[str]:
        """获取性能最好的模型版本

        Args:
            model_type: 模型类型
            metric: 性能指标名称

        Returns:
            最佳版本号，如果没有记录则返回None
        """
        pass
