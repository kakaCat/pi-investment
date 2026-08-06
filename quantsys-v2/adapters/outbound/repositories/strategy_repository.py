"""策略ORM Repository - 快速迁移版本"""
from typing import List, Dict, Optional, Any
from infrastructure.persistence.orm import BaseORMRepository, get_session
from sqlalchemy import Column, Integer, String, Float, Date, Text, BigInteger, JSON, Boolean, DateTime
from infrastructure.persistence.orm.base import Base
import structlog

logger = structlog.get_logger(__name__)

# Strategy Metadata - 系统内置策略元数据
class Strategy(Base):
    __tablename__ = 'strategy_metadata'
    __table_args__ = {'schema': 'quant'}
    strategy_type = Column(String(100), primary_key=True)  # 主键是 strategy_type，不是 id
    class_name = Column(String(100))
    description = Column(Text)
    category = Column(String(50))
    default_params = Column(JSON)
    param_schema = Column(JSON)

# Strategy Config - 用户自定义策略/指标代码
class StrategyConfig(Base):
    __tablename__ = 'strategy_configs'
    __table_args__ = {'schema': 'quant'}
    id = Column(BigInteger, primary_key=True)
    strategy_name = Column(Text)
    description = Column(Text)
    strategy_type = Column(Text)
    code_content = Column(Text)
    code_type = Column(String(50))  # 'indicator' or 'script'
    parameters = Column(JSON)
    parsed_params = Column(JSON)
    is_active = Column(Boolean)
    is_public = Column(Boolean)
    category = Column(String(50))
    author = Column(Text)
    favorite_count = Column(Integer)
    strategy_metadata = Column('metadata', JSON)  # 使用别名避免冲突
    strategy_profile = Column(JSON)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    last_executed_at = Column(DateTime)  # 最后执行时间

from domain.ports import IStrategyRepository

class StrategyORMRepository(BaseORMRepository[Strategy], IStrategyRepository):
    model = Strategy

    def get_by_name(self, name: str):
        try:
            return self.session.query(Strategy).filter_by(strategy_type=name).first()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error: {e}")
            return None

    # ==================== IStrategyRepository接口实现 ====================

    def get_strategy(self, strategy_id: int) -> Optional[Dict[str, Any]]:
        """获取策略（IStrategyRepository接口实现）

        注意：strategy_id 在这里实际是 strategy_type（字符串）
        """
        try:
            strategy = self.session.query(Strategy).filter_by(strategy_type=str(strategy_id)).first()
            if not strategy:
                return None
            return {
                'strategy_type': strategy.strategy_type,
                'class_name': strategy.class_name,
                'description': strategy.description,
                'category': strategy.category,
                'parameters': strategy.default_params,
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting strategy {strategy_id}: {e}")
            return None

    def list_strategies(
        self,
        source: Optional[str] = None,
        code_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """列出策略（IStrategyRepository接口实现）"""
        try:
            query = self.session.query(Strategy)

            if source:
                query = query.filter(Strategy.category == source)

            strategies = query.all()
            return [{
                'strategy_type': s.strategy_type,
                'class_name': s.class_name,
                'description': s.description,
                'category': s.category,
                'parameters': s.default_params,
            } for s in strategies]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error listing strategies: {e}")
            return []

    def create_strategy(self, strategy_data: Dict[str, Any]) -> int:
        """创建策略（IStrategyRepository接口实现）"""
        try:
            strategy = Strategy(
                strategy_type=strategy_data.get('strategy_type'),
                class_name=strategy_data.get('class_name'),
                description=strategy_data.get('description'),
                category=strategy_data.get('category', 'other'),
                default_params=strategy_data.get('parameters', {}),
            )
            self.session.add(strategy)
            self.session.commit()
            return 1  # 返回成功标志
        except Exception as e:
            logger.error(f"Error creating strategy: {e}")
            self.session.rollback()
            return 0

    def update_strategy(self, strategy_id: int, updates: Dict[str, Any]) -> bool:
        """更新策略（IStrategyRepository接口实现）

        注意：strategy_id 实际是 strategy_type（字符串）
        """
        try:
            strategy = self.session.query(Strategy).filter_by(strategy_type=str(strategy_id)).first()
            if not strategy:
                return False

            for key, value in updates.items():
                if hasattr(strategy, key):
                    setattr(strategy, key, value)

            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating strategy {strategy_id}: {e}")
            self.session.rollback()
            return False
            return True
        except Exception as e:
            logger.error(f"Error updating strategy {strategy_id}: {e}")
            self.session.rollback()
            return False

    def get_user_strategies(
        self,
        code_type: Optional[str] = None,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """获取用户策略列表（从 strategy_configs 表查询）

        Args:
            code_type: 策略代码类型过滤 ('indicator', 'script', etc.)
            active_only: 是否只返回激活的策略

        Returns:
            策略字典列表
        """
        try:
            query = self.session.query(StrategyConfig)

            # 按 code_type 过滤
            if code_type:
                query = query.filter(StrategyConfig.code_type == code_type)

            # 只返回激活的策略
            if active_only:
                query = query.filter(StrategyConfig.is_active == True)

            strategies = query.all()
            return [{
                'id': s.id,
                'name': s.strategy_name,
                'strategy_name': s.strategy_name,
                'strategy_type': s.strategy_type,
                'code_type': s.code_type,
                'code_content': s.code_content,
                'description': s.description,
                'parameters': s.parameters,
                'params': s.parameters,
                'parsed_params': s.parsed_params,
                'category': s.category,
                'author': s.author,
                'is_active': s.is_active,
                'is_public': s.is_public,
                'favorite_count': s.favorite_count or 0,
                'metadata': s.strategy_metadata,  # 使用别名字段
                'strategy_profile': s.strategy_profile,
                'created_at': s.created_at.isoformat() if s.created_at else None,
                'updated_at': s.updated_at.isoformat() if s.updated_at else None,
            } for s in strategies]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting user strategies: {e}")
            return []

    def get_all(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """获取所有策略

        Args:
            active_only: 是否只返回激活的策略

        Returns:
            策略字典列表
        """
        return self.get_user_strategies(code_type=None, active_only=active_only)

    def get_by_id(self, strategy_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取策略（从 strategy_configs 表）

        Args:
            strategy_id: 策略 ID

        Returns:
            策略字典
        """
        try:
            strategy = self.session.query(StrategyConfig).filter_by(id=strategy_id).first()
            if not strategy:
                return None

            return {
                'id': strategy.id,
                'name': strategy.strategy_name,
                'strategy_name': strategy.strategy_name,
                'strategy_type': strategy.strategy_type,
                'code_type': strategy.code_type,
                'code_content': strategy.code_content,
                'description': strategy.description,
                'parameters': strategy.parameters,
                'parsed_params': strategy.parsed_params,
                'category': strategy.category,
                'author': strategy.author,
                'is_active': strategy.is_active,
                'is_public': strategy.is_public,
                'favorite_count': strategy.favorite_count or 0,
                'metadata': strategy.strategy_metadata,  # 使用别名字段
                'strategy_profile': strategy.strategy_profile,
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting strategy by id {strategy_id}: {e}")
            return None

    def update_last_executed(self, strategy_id: int) -> bool:
        """更新策略的最后执行时间

        Args:
            strategy_id: 策略 ID

        Returns:
            bool: 是否更新成功
        """
        try:
            from datetime import datetime
            strategy = self.session.query(StrategyConfig).filter_by(id=strategy_id).first()
            if not strategy:
                return False

            # 更新 last_executed_at 字段
            strategy.last_executed_at = datetime.now()
            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating last_executed for strategy {strategy_id}: {e}")
            self.session.rollback()
            return False

    def create_user_strategy(self, strategy_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建用户策略（写入 strategy_configs 表）

        Args:
            strategy_data: 策略数据字典，包含:
                - name: 策略名称
                - code_content: 代码内容
                - code_type: 代码类型 ('indicator', 'script')
                - description: 描述
                - category: 分类
                - is_public: 是否公开
                - validation_status: 验证状态
                - is_active: 是否激活
                - parsed_params: 解析的参数
                - risk_config: 风险配置
                - metadata: 元数据

        Returns:
            创建的策略字典，包含 id
        """
        try:
            from datetime import datetime

            cat = strategy_data.get('category', 'custom')
            strategy = StrategyConfig(
                strategy_name=strategy_data.get('name'),
                code_content=strategy_data.get('code_content'),
                code_type=strategy_data.get('code_type'),
                description=strategy_data.get('description'),
                strategy_type=strategy_data.get('strategy_type', cat),
                category=cat,
                author=strategy_data.get('author', 'user'),
                is_public=strategy_data.get('is_public', False),
                is_active=strategy_data.get('is_active', True),
                parameters=strategy_data.get('parameters', {}),
                parsed_params=strategy_data.get('parsed_params'),
                strategy_metadata=strategy_data.get('metadata', {}),
                strategy_profile=strategy_data.get('risk_config', {}),
                favorite_count=0,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            self.session.add(strategy)
            self.session.commit()
            self.session.refresh(strategy)

            logger.info(f"Created user strategy: {strategy.id} - {strategy.strategy_name}")

            return {
                'id': strategy.id,
                'name': strategy.strategy_name,
                'strategy_name': strategy.strategy_name,
                'code_type': strategy.code_type,
                'code_content': strategy.code_content,
                'description': strategy.description,
                'category': strategy.category,
                'is_active': strategy.is_active,
                'is_public': strategy.is_public,
                'created_at': strategy.created_at.isoformat() if strategy.created_at else None
            }
        except Exception as e:
            logger.error(f"Error creating user strategy: {e}")
            self.session.rollback()
            raise

    def update_validation_status(
        self,
        strategy_id: int,
        status: str,
        errors: Optional[str] = None
    ) -> bool:
        """更新策略的验证状态

        Args:
            strategy_id: 策略 ID
            status: 验证状态 ('valid', 'invalid', 'pending')
            errors: 验证错误信息（可选）

        Returns:
            bool: 是否更新成功
        """
        try:
            from datetime import datetime
            strategy = self.session.query(StrategyConfig).filter_by(id=strategy_id).first()
            if not strategy:
                logger.warning(f"Strategy {strategy_id} not found for validation status update")
                return False

            # 更新元数据中的验证状态
            metadata = strategy.strategy_metadata or {}
            metadata['validation_status'] = status
            if errors:
                metadata['validation_errors'] = errors

            strategy.strategy_metadata = metadata
            strategy.updated_at = datetime.now()

            # 如果验证失败，设为不激活
            if status == 'invalid':
                strategy.is_active = False

            self.session.commit()
            logger.info(f"Updated validation status for strategy {strategy_id}: {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating validation status for strategy {strategy_id}: {e}")
            self.session.rollback()
            return False
