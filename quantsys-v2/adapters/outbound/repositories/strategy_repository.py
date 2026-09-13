"""策略ORM Repository - 快速迁移版本"""
from typing import List, Dict, Optional, Any
from infrastructure.persistence.orm import BaseORMRepository, get_session
from sqlalchemy import (
    Column, Integer, String, Float, Date, Text, BigInteger, JSON, Boolean, DateTime, func,
    delete as sa_delete, literal_column, select, update as sa_update,
)
from infrastructure.persistence.orm.base import Base
from infrastructure.persistence.orm.models.strategy_validation import StrategyValidationReport
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
    # 2026-09-14（REQ-24e15d）：补上模型漏掉的 3 列。它们是**表里真实存在**的列
    # （information_schema 实读：risk_params jsonb / risk_config jsonb / version text default '1.0'），
    # 且本类 USER_STRATEGY_UPDATABLE 白名单与 _JSONB_COLUMNS 里早已列出 —— 只补模型，
    # 不改任何调用方（get_user_strategies/get_by_id 都是显式列字典，不受影响）。
    # 补的原因：strategy_lifecycle_service.retire() 的备份语义是 select *（行数组 JSON），
    # 模型缺列会让 json_agg 出来的备份少 3 个字段（实测 missing=['risk_config','risk_params','version']）。
    risk_params = Column(JSON)
    version = Column(Text)
    risk_config = Column(JSON)
    is_active = Column(Boolean)
    is_public = Column(Boolean)
    category = Column(String(50))
    author = Column(Text)
    favorite_count = Column(Integer)
    strategy_metadata = Column('metadata', JSON)  # 使用别名避免冲突
    strategy_profile = Column(JSON)
    validation_status = Column(String(50))  # 【遗留·结构语义】等价 structure_status，保留兼容旧读路径
    validation_errors = Column(Text)  # 独立列：验证错误信息
    # 2026-09-13（w-a9ec14d7）：把 validation_status 的两种含义拆开——结构有效 vs 业绩有效。
    # 见 application/services/strategy_status.py（判定规则单一事实源）。
    structure_status = Column(String(50))  # 代码/参数能否跑通：valid/invalid/pending/unknown
    performance_status = Column(String(50))  # 相对同池等权基准是否有超额：passing/underperform/failing/unmeasured
    performance_evidence = Column(JSON)  # 业绩判定证据（年化/夏普/回撤/基准/来源/窗口/规则）
    performance_checked_at = Column(DateTime)  # 业绩判定时间
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
                'validation_status': s.validation_status or (s.strategy_metadata or {}).get('validation_status'),
                'validation_errors': s.validation_errors or (s.strategy_metadata or {}).get('validation_errors'),
                'structure_status': s.structure_status or (s.strategy_metadata or {}).get('structure_status') or s.validation_status,
                'performance_status': s.performance_status or (s.strategy_metadata or {}).get('performance_status') or 'unmeasured',
                'performance_evidence': s.performance_evidence,
                'performance_checked_at': s.performance_checked_at.isoformat() if s.performance_checked_at else None,
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
                'validation_status': strategy.validation_status or (strategy.strategy_metadata or {}).get('validation_status'),
                'validation_errors': strategy.validation_errors or (strategy.strategy_metadata or {}).get('validation_errors'),
                'structure_status': strategy.structure_status or (strategy.strategy_metadata or {}).get('structure_status') or strategy.validation_status,
                'performance_status': strategy.performance_status or (strategy.strategy_metadata or {}).get('performance_status') or 'unmeasured',
                'performance_evidence': strategy.performance_evidence,
                'performance_checked_at': strategy.performance_checked_at.isoformat() if strategy.performance_checked_at else None,
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting strategy by id {strategy_id}: {e}")
            return None

    # ── 用户策略（quant.strategy_configs）写路径 ──────────────────────────────
    # 2026-09-13（w-32314d00，错误事件 e22c1dc2）：本类继承了 BaseORMRepository 的
    # 通用 update(obj, commit) / delete(obj, commit)，而 StrategyCodeService 按**字典 API**
    # 调用 update(strategy_id, updates) / delete(strategy_id) —— 方法名撞车，参数被当成 ORM 对象：
    #   session.merge("163") / session.delete("163")
    #   → UnmappedInstanceError: Class 'builtins.str' is not mapped
    #   → 被基类 except 吞掉并打成 "Error updating Strategy: ..."（strategy_repo.update 调用点）
    #   → /api/strategies/stop/{id}、/api/strategies/update/{id}、/api/strategies/delete/{id} 全 500。
    # 现补上显式命名的用户策略写方法，服务端同步改调用（不再撞通用 CRUD 的名字）。
    USER_STRATEGY_UPDATABLE = frozenset({
        'strategy_name', 'description', 'strategy_type', 'parameters', 'risk_params',
        'is_active', 'version', 'author', 'code_content', 'code_type', 'parsed_params',
        'risk_config', 'metadata', 'validation_status', 'validation_errors',
        'last_executed_at', 'is_public', 'category', 'favorite_count', 'strategy_profile',
    })
    _JSONB_COLUMNS = frozenset({
        'parameters', 'risk_params', 'parsed_params', 'risk_config', 'metadata',
        'strategy_profile',
    })

    def update_user_strategy(self, strategy_id: int, updates: Dict[str, Any]) -> bool:
        """按 id 更新用户策略（quant.strategy_configs），返回是否命中行。

        白名单外的字段忽略并告警（表列由 information_schema 实测，避免把不存在的列写进 SQL）；
        JSONB 列显式 CAST，None 表示置空。
        """
        import json
        from sqlalchemy import text

        updates = dict(updates or {})
        if 'strategy_metadata' in updates and 'metadata' not in updates:
            updates['metadata'] = updates.pop('strategy_metadata')
        assignments, params = [], {"sid": strategy_id}
        for key, value in updates.items():
            if key not in self.USER_STRATEGY_UPDATABLE:
                logger.warning(f"update_user_strategy: 未知字段 {key!r} 已忽略")
                continue
            if key in self._JSONB_COLUMNS:
                assignments.append(f"{key} = CAST(:{key} AS jsonb)")
                params[key] = None if value is None else json.dumps(value, ensure_ascii=False, default=str)
            else:
                assignments.append(f"{key} = :{key}")
                params[key] = value
        try:
            if not assignments:
                logger.warning(f"update_user_strategy: 无有效字段可更新 (id={strategy_id})")
                return False
            sql = ("UPDATE quant.strategy_configs SET " + ", ".join(assignments)
                   + ", updated_at = now() WHERE id = :sid")
            result = self.session.execute(text(sql), params)
            self.session.commit()
            return bool(result.rowcount)
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error updating user strategy {strategy_id}: {e}")
            return False

    def delete_user_strategy(self, strategy_id: int) -> bool:
        """硬删除策略（物理删除）。

        ⚠️ R-020 数据卫生（2026-09-13 实测代价）——**删之前先查「谁还指着它」**：
        · 本仓历史上（2026-05-31 的 quant.strategy_stock_matching）用**纯文本字段
          best_strategy_id + 写死列名 ret_162/ret_163/ret_164** 引用策略，且**没有外键**。
          结果：策略被合法删除后该表仍有 800/800 行指向不存在的策略，静静躺了 105 天
          （全仓零代码引用 → 不报错、没人更新、也没人看），直到人工追查才撞见。
        · 对照案例（同一根因的反面）：审计表 quant.pool_change_log 因**有外键**，
          反而让「有变更历史的池子删不掉」（DELETE 直接 500）。
        · 正确做法按类型显式选：审计类 → 外键 ON DELETE SET NULL（审计要活得比聚合久，
          并用冗余字段保留身份，如 pool_change_log.pool_name）；派生类 → 先清或级联；
          生产类 → 优先软删（is_active=false）而非物理删除。
        · 新增派生/审计表必须登记 quantsys-v2/config/data_contracts.json；
          悬空引用由 scripts/data_hygiene_probe.py 每周巡检（退出码 1 = 有问题）。
        """

        """按 id 删除用户策略（quant.strategy_configs）。"""
        from sqlalchemy import text
        try:
            result = self.session.execute(
                text("DELETE FROM quant.strategy_configs WHERE id = :sid"),
                {"sid": strategy_id})
            self.session.commit()
            return bool(result.rowcount)
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error deleting user strategy {strategy_id}: {e}")
            return False
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
            
            # 检查策略名称是否已存在
            strategy_name = strategy_data.get('name')
            existing = self.session.query(StrategyConfig).filter(
                StrategyConfig.strategy_name == strategy_name
            ).first()
            if existing:
                raise ValueError(f'策略名称已存在: {strategy_name}')
            
            strategy = StrategyConfig(
                strategy_name=strategy_name,
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
                validation_status=strategy_data.get('validation_status') or (strategy_data.get('metadata') or {}).get('validation_status'),
                validation_errors=strategy_data.get('validation_errors'),
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
        errors: Optional[str] = None,
        deactivate_if_invalid: bool = True
    ) -> Optional[Dict[str, Any]]:
        """更新策略的验证状态（独立列 + metadata JSON 双写，兼容新老读路径）

        Args:
            strategy_id: 策略 ID
            status: 验证状态，必须是 'valid' / 'invalid' / 'pending'
            errors: 验证错误信息（可选）
            deactivate_if_invalid: invalid 时是否自动停用策略。
                True=代码级验证失败停用（create_user_strategy 场景）；
                False=报告性验证（每日回测验证只记录状态，不自动停用）

        Returns:
            dict: {'strategy_id', 'validation_status', 'validation_errors', 'is_active'}；
                  策略不存在时返回 None
        Raises:
            ValueError: status 不是合法取值
        """
        valid_statuses = ('valid', 'invalid', 'pending')
        if status not in valid_statuses:
            raise ValueError(f"status 必须是 {', '.join(valid_statuses)} 之一，收到: {status}")
        try:
            from datetime import datetime
            strategy = self.session.query(StrategyConfig).filter_by(id=strategy_id).first()
            if not strategy:
                logger.warning(f"Strategy {strategy_id} not found for validation status update")
                return None

            # 独立列（真实 schema 主存储）
            strategy.validation_status = status
            strategy.validation_errors = errors if errors else None
            # 2026-09-13：结构状态双写（validation_status 的语义就是结构有效，此处起别名，读端不再混用）
            strategy.structure_status = status

            # metadata JSON（兼容历史读路径双写）
            # 注意：JSON 列原地改 dict 再赋回同一对象，SQLAlchemy 比较前后相等会跳过该列 UPDATE，
            # 必须用 flag_modified 强制标记为已修改
            from sqlalchemy.orm.attributes import flag_modified
            metadata = dict(strategy.strategy_metadata or {})
            metadata['validation_status'] = status
            if errors:
                metadata['validation_errors'] = errors
            elif 'validation_errors' in metadata:
                metadata.pop('validation_errors', None)
            strategy.strategy_metadata = metadata
            flag_modified(strategy, 'strategy_metadata')
            strategy.updated_at = datetime.now()

            # 仅当显式要求时才停用（代码级验证失败场景）
            if status == 'invalid' and deactivate_if_invalid:
                strategy.is_active = False

            self.session.commit()
            logger.info(f"Updated validation status for strategy {strategy_id}: {status} (errors={bool(errors)})")
            return {
                'strategy_id': strategy.id,
                'validation_status': strategy.validation_status,
                'validation_errors': strategy.validation_errors,
                'is_active': strategy.is_active,
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error updating validation status for strategy {strategy_id}: {e}")
            raise

    def update_performance_status(
        self,
        strategy_id: int,
        performance_status: str,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """更新策略**业绩状态**（与 structure_status 分离的第二根轴，2026-09-13 w-a9ec14d7）

        背景：原先只有一个 validation_status，'valid' 被读成"这策略好用"——
        实测 14 条 active+valid 策略 OOS CAGR 中位约 -1%（同期同池等权基准 +23.3%）。
        结构有效 ≠ 有超额，两根轴必须分开写、分开读。

        Args:
            strategy_id: 策略 ID
            performance_status: passing / underperform / failing / unmeasured
            evidence: 判定证据（年化/夏普/回撤/基准/来源/窗口/规则），由
                      application.services.strategy_status.performance_evidence() 生成

        Returns:
            dict: {'strategy_id', 'performance_status', 'performance_evidence'}；策略不存在返回 None
        Raises:
            ValueError: 状态非法
        """
        from application.services.strategy_status import PERFORMANCE_STATUSES
        if performance_status not in PERFORMANCE_STATUSES:
            raise ValueError(
                f"performance_status 必须是 {', '.join(PERFORMANCE_STATUSES)} 之一，收到: {performance_status}"
            )
        try:
            from datetime import datetime
            strategy = self.session.query(StrategyConfig).filter_by(id=strategy_id).first()
            if not strategy:
                logger.warning(f"Strategy {strategy_id} not found for performance status update")
                return None
            strategy.performance_status = performance_status
            if evidence is not None:
                strategy.performance_evidence = evidence
            strategy.performance_checked_at = datetime.now()
            strategy.updated_at = datetime.now()
            self.session.commit()
            logger.info(f"Updated performance status for strategy {strategy_id}: {performance_status}")
            return {
                'strategy_id': strategy.id,
                'performance_status': strategy.performance_status,
                'performance_evidence': strategy.performance_evidence,
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error updating performance status for strategy {strategy_id}: {e}")
            raise

    def save_validation_report(self, report_data: Dict[str, Any]) -> int:
        """保存策略验证报告（写入 quant.strategy_validation_reports）

        Args:
            report_data: 验证报告数据，包含:
                - strategy_id: 策略 ID
                - score: 综合评分
                - status: 验证状态 ('valid'/'invalid')
                - annual_return / sharpe_ratio / max_drawdown / win_rate / profit_factor: 指标
                - backtest_count / error_count: 回测统计
                - start_date / end_date: 回测窗口

        Returns:
            int: 新报告 ID
        """
        try:
            from datetime import datetime, date as date_cls
            from sqlalchemy import text as sa_text

            def _parse_date(v):
                if isinstance(v, date_cls):
                    return v
                return date_cls.fromisoformat(str(v)) if v else None

            insert_sql = sa_text("""
                INSERT INTO quant.strategy_validation_reports
                (strategy_id, validation_date, score, status,
                 annual_return, sharpe_ratio, max_drawdown, win_rate, profit_factor,
                 backtest_count, error_count, start_date, end_date, created_at)
                VALUES (:strategy_id, :validation_date, :score, :status,
                        :annual_return, :sharpe_ratio, :max_drawdown, :win_rate, :profit_factor,
                        :backtest_count, :error_count, :start_date, :end_date, :created_at)
                RETURNING id
            """)
            now = datetime.now()
            result = self.session.execute(insert_sql, {
                'strategy_id': report_data.get('strategy_id'),
                'validation_date': now,
                'score': report_data.get('score'),
                'status': report_data.get('status'),
                'annual_return': report_data.get('annual_return'),
                'sharpe_ratio': report_data.get('sharpe_ratio'),
                'max_drawdown': report_data.get('max_drawdown'),
                'win_rate': report_data.get('win_rate'),
                'profit_factor': report_data.get('profit_factor'),
                'backtest_count': report_data.get('backtest_count', 0),
                'error_count': report_data.get('error_count', 0),
                'start_date': _parse_date(report_data.get('start_date')),
                'end_date': _parse_date(report_data.get('end_date')),
                'created_at': now,
            })
            self.session.commit()
            report_id = result.scalar()
            logger.info(f"Saved validation report for strategy {report_data.get('strategy_id')}: id={report_id} score={report_data.get('score')}")
            return int(report_id)
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error saving validation report: {e}")
            raise

    def has_validation_report_since(self, strategy_id: int, since) -> bool:
        """该策略在 since 之后是否已有验证报告（当日幂等判定）。

        2026-09-14（REQ-24e15d）：原实现是
        application/services/strategy_validation_service.py 里的
        session.execute(text("SELECT COUNT(*) FROM quant.strategy_validation_reports
        WHERE strategy_id = :sid AND validation_date >= :today")).scalar()，
        下游按 if exists: 判真假。现收口到此，走 StrategyValidationReport 模型。

        口径逐值对齐原 SQL：同样是 validation_date >= :today 的**计数 > 0** 判定
        （注意不是 = 某时刻：服务层传的是当天零点），保留 COUNT 口径而不改写为
        LIMIT 1 / EXISTS —— 语义等价，但不动它以免引入可见性差异。

        Args:
            strategy_id: 策略 ID
            since: 时间下界（通常为当天 00:00:00）

        Returns:
            True = 已存在当日报告（调用方应跳过，防 reports 表膨胀）
        """
        count = (
            self.session.query(func.count(StrategyValidationReport.id))
            .filter(
                StrategyValidationReport.strategy_id == strategy_id,
                StrategyValidationReport.validation_date >= since,
            )
            .scalar()
        )
        return bool(count)

    def get_strategy_config_snapshot(self, strategy_id: int) -> List[Dict[str, Any]]:
        """取一条策略配置的**全列快照**（行数组的 JSON，供退役前备份）。

        2026-09-14（REQ-24e15d）：原实现是 application/services/strategy_lifecycle_service.py
        retire() 里的
            select coalesce(json_agg(t),'[]'::json)
            from (select * from quant.strategy_configs where id = :sid) t
        （经 strategy_evaluation_service.query_rows 的裸游标执行），现收口到此。

        逐值对齐要点：
        · json_agg(t) 里 t 是**子查询别名**，产出的 JSON 由 PostgreSQL 自己序列化
          （时间戳按 PG 的 ISO 格式、jsonb 嵌套成对象、整型成数字）——这里保持同一写法
          （SQLAlchemy Core 的 literal_column('t')），**不**在 Python 侧重新拼字典，
          以免 Decimal/datetime 的序列化口径与原实现不一致；
        · 无匹配行时 json_agg 返回 NULL（旧写的 coalesce 兜成 '[]'::json），这里
          在 Python 侧返回 [] —— 最终值相同（空列表），语义等价；
        · 形状：list[dict]，一行一 dict，键 = strategy_configs 的全部 27 列（模型必须逐列齐全，
          故本文件补上了 risk_params / version / risk_config 三列）。
        """
        subq = (
            select(StrategyConfig.__table__)
            .where(StrategyConfig.__table__.c.id == strategy_id)
            .subquery('t')
        )
        stmt = select(func.json_agg(literal_column('t'))).select_from(subq)
        value = self.session.execute(stmt).scalar()
        return value if value is not None else []

    def retire_strategy_config(self, strategy_id: int, delete: bool = False) -> None:
        """退役策略行：停用（is_active=false, updated_at=now()），delete=True 时同事务物理删除。

        2026-09-14（REQ-24e15d）：原实现是 strategy_lifecycle_service.retire() 里
        ev._engine().begin() 上的两条 text() 裸 SQL：
            update quant.strategy_configs set is_active=false, updated_at=now() where id = :sid
            delete from quant.strategy_configs where id = :sid      -- 仅 delete=True
        这里收口成仓储方法，并**刻意保持"两条语句同一事务"**：单条 commit 提交两者，
        与旧 begin() 块的原子性一致（若拆成两个方法各自 commit，delete 失败时 update 已被提交 —— 行为会变）。

        ⚠️ 与本类既有的 update_user_strategy / delete_user_strategy 的区别：那两个**吞异常返回 bool**
        （0 行命中与出错都返回 False），而这里的调用方（retire）原本是**异常向上抛**的语义，
        故本方法失败时先 _safe_rollback() 再 raise，不把错误静默成 False。
        """
        try:
            self.session.execute(
                sa_update(StrategyConfig)
                .where(StrategyConfig.id == strategy_id)
                .values(is_active=False, updated_at=func.now())
            )
            if delete:
                self.session.execute(
                    sa_delete(StrategyConfig).where(StrategyConfig.id == strategy_id)
                )
            self.session.commit()
        except Exception:
            self._safe_rollback()
            raise
