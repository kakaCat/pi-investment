"""
ML Model ORM Repository - 机器学习模型仓储

修复记录：2026-07-19 补全
  - 原 stub 缺少 ml_routes 依赖的 get_by_type_version / save_model /
    get_feature_importance / _ensure_db（模型监控 500、训练元数据写入失败）
  - 模型字段补齐至 quant.ml_models 完整结构
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text as sql_text
from infrastructure.persistence.orm.base import Base
from domain.ports import IMlModelRepository
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json
import time
import structlog

logger = structlog.get_logger(__name__)


class MlModel(Base):
    __tablename__ = 'ml_models'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    model_type = Column(String(50), nullable=False)
    version = Column(String(50), nullable=False)
    model_path = Column(Text)
    train_accuracy = Column(Float)
    test_accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    roc_auc = Column(Float)
    feature_count = Column(Integer)
    train_samples = Column(Integer)
    feature_importance = Column(Text, default='{}')
    training_params = Column(Text, default='{}')
    training_report = Column(Text, default='{}')
    status = Column(String(20), default='ready')
    train_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MlModelORMRepository(BaseORMRepository[MlModel], IMlModelRepository):
    """ORM Repository for ml_models"""
    model = MlModel

    # ---------- ml_routes 依赖方法 ----------

    def get_by_type_version(self, model_type: str, version: str) -> Optional[Dict[str, Any]]:
        """按类型 + 版本查询模型（version='latest' 取最新一条）"""
        try:
            query = self.session.query(self.model).filter(
                self.model.model_type == model_type)
            if version == 'latest':
                row = query.order_by(self.model.train_date.desc()).first()
            else:
                row = query.filter(self.model.version == version).first()
            return self._to_dict(row) if row else None
        except SQLAlchemyError as e:
            self._safe_rollback()
            logger.error(f"Error in get_by_type_version({model_type}, {version}): {e}")
            return None

    def save_model(self, data: Dict[str, Any]) -> int:
        """保存模型元数据（按 model_type + version upsert），返回记录ID"""
        try:
            model_type = data.get('model_type')
            version = data.get('version')
            row = (self.session.query(self.model)
                   .filter_by(model_type=model_type, version=version)
                   .first())
            if row is None:
                row = self.model(model_type=model_type, version=version)
                self.session.add(row)

            for field in ('model_path', 'train_accuracy', 'test_accuracy', 'precision',
                          'recall', 'f1_score', 'roc_auc', 'feature_count', 'train_samples',
                          'feature_importance', 'training_params', 'training_report', 'status'):
                if field in data and data[field] is not None:
                    setattr(row, field, data[field])

            train_date = data.get('train_date')
            if train_date:
                if isinstance(train_date, str):
                    try:
                        train_date = datetime.fromisoformat(train_date.replace('Z', '+00:00'))
                    except ValueError:
                        self._safe_rollback()
                        train_date = datetime.now(timezone.utc)
                row.train_date = train_date

            self.session.commit()
            self.session.refresh(row)
            return row.id
        except SQLAlchemyError as e:
            logger.error(f"Error in save_model: {e}")
            self.session.rollback()
            raise

    def get_feature_importance(self, model_type: Optional[str] = None) -> Optional[Dict[str, float]]:
        """获取最新模型的特征重要性（解析 JSON 文本列）"""
        try:
            query = self.session.query(self.model)
            if model_type:
                query = query.filter(self.model.model_type == model_type)
            row = query.order_by(self.model.train_date.desc()).first()
            if row is None or not row.feature_importance:
                return None
            importance = json.loads(row.feature_importance)
            return importance if isinstance(importance, dict) and importance else None
        except (SQLAlchemyError, json.JSONDecodeError) as e:
            self._safe_rollback()
            logger.error(f"Error in get_feature_importance: {e}")
            return None

    def _ensure_db(self, max_retries: int = 3, retry_delay: float = 1.0) -> bool:
        """确保数据库连接可用（训练后连接池可能耗尽，强制重连）

        Args:
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）

        Returns:
            连接可用返回 True
        """
        for attempt in range(1, max_retries + 1):
            try:
                self.session.execute(sql_text('SELECT 1'))
                return True
            except SQLAlchemyError as e:
                logger.warning(f"DB connection check failed (attempt {attempt}/{max_retries}): {e}")
                try:
                    self.session.rollback()
                    self.session.close()
                except Exception:
                    self._safe_rollback()
                    pass
                self._session = None  # 强制下次访问时重建 session
                if attempt < max_retries:
                    time.sleep(retry_delay)
        return False

    # ---------- 已有方法（保持不变） ----------

    def get_model(self, model_id: int) -> Optional[Dict[str, Any]]:
        try:
            row = self.session.query(self.model).filter(self.model.id == model_id).first()
            if row is None:
                return None
            return self._to_dict(row)
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_model: {e}")
            return None

    def list_models(self, model_type: Optional[str] = None, status: Optional[str] = None,
                    limit: int = 20) -> List[Dict[str, Any]]:
        """列出模型（按训练时间倒序）"""
        try:
            query = self.session.query(self.model)
            if model_type:
                query = query.filter(self.model.model_type == model_type)
            if status:
                query = query.filter(self.model.status == status)
            rows = query.order_by(self.model.train_date.desc()).limit(limit).all()
            return [self._to_dict(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in list_models: {e}")
            return []

    def list_all(self, limit: int = 100) -> List:
        try:
            return self.session.query(self.model).limit(limit).all()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing: {e}")
            return []

    @staticmethod
    def _to_dict(row: MlModel) -> Dict[str, Any]:
        result = {}
        for c in row.__table__.columns:
            value = getattr(row, c.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[c.name] = value
        return result


__all__ = ['MlModelORMRepository']
