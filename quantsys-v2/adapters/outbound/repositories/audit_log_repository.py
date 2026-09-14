"""audit_log ORM Repository —— 策略日检决策留痕（V13/V14 使用）。

2026-09-14（REQ-24e15d B4-c5）：application/strategies/v13_use_case.py 的 _log_to_db
在 position_repo 没有 log_decision 时的回退分支，原为裸 SQL INSERT（见 git HEAD）：

    缩进块（非 SQL 字面量，仅供阅读）：
        INSERT INTO audit_log
            (event_type, account_name, strategy, version, event_date, payload, created_at)
        VALUES (:event_type, :account_name, :strategy, :version, :event_date, :payload, NOW())

本模块把该写入收进仓储（见 audit_log 的 schema 说明：表名**未限定**，靠 search_path）。
"""
import json
from typing import Any, Dict

import structlog
from sqlalchemy import Column, DateTime, Integer, String, Text, func, insert

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)


class AuditLog(Base):
    """策略决策审计行（表名 audit_log，**不带 schema 前缀**）。

    2026-09-14 实测（information_schema，库 quant_investment）：
      · audit_log **在任何 schema 下都不存在** —— 全库 table_name ILIKE '%audit%' 只命中
        quant.operation_audit / quant.memory_recall_audit；
      · 本仓也没有它的 DDL：全仓 *.sql grep 'audit_log' 为 0 命中。
    因此这里**不写 schema**，让表名保持未限定 —— 与迁移前的裸 SQL 逐字一致，交给
    search_path（本库 = "$user", public）解析。哪天该表被建到 quant schema，未限定名同样
    找不到它（与原实现同）；要改口径必须先有 DDL 并把 schema 显式写进来。

    payload 声明为 Text 而非 JSONB：原实现传的是**已 json.dumps 的字符串**
    （json.dumps(record, ensure_ascii=False, default=str)），落库靠 PG 的 text→jsonb
    隐式转换。若声明 JSONB，SQLAlchemy 会对这个字符串**再序列化一次**（双重编码），
    存下去的就不是同一个值了。

    新增模型带来的**已知副作用**（2026-09-14 实测）：本模块一被 import，AuditLog 就注册进
    infrastructure.persistence.orm.base.Base.metadata（实测 59 -> 60 张表）。两个 create_all
    脚本（scripts/migrate_20260720_multi_account.py / migrate_20260813_action_case_unify.py）
    都是先 import orm.models（不含仓储）再 create_all，所以**当前不会被顺带建出来**；
    但若哪天有脚本在 import 本模块之后 create_all，就会按这里的列定义 CREATE 出这张
    当前不存在的表。已登记在 B4-c5 报告里，未在本批动手修（不擅自建表/改口径）。
    """

    __tablename__ = 'audit_log'

    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), nullable=False)
    account_name = Column(String(100))
    strategy = Column(String(50))
    version = Column(String(50))
    # 原实现把 'YYYY-MM-DD' 字符串**原样**交给 PG（Python 侧不做 date 转换），
    # 故声明为 String 以保持参数逐字一致（表不存在，真实类型暂不可核）。
    event_date = Column(String(20))
    payload = Column(Text)
    created_at = Column(DateTime, nullable=False)


class AuditLogORMRepository(BaseORMRepository[AuditLog]):
    """audit_log 只写仓储（当前唯一调用方：XGBoostStrategyUseCase._log_to_db）。"""

    model = AuditLog

    def log_decision(self, record: Dict[str, Any]) -> None:
        """落一行策略日检决策（event_type 固定为 strategy_daily_check）。

        与迁移前裸 SQL 的列/取值/默认值逐字对应：
          · account_name / strategy / version / event_date 取自 record 的同名字段；
          · payload = json.dumps(record, ensure_ascii=False, default=str)；
          · created_at 仍由 PG 的 now() 生成（不改成 Python 侧时间戳，语义不变）。

        异常策略：回滚后**上抛** —— 调用方 _log_to_db 的 except 是既有容错路径
        （记 warning、不影响策略流程）。回滚是必须的：PG 语句报错会让本线程的
        session 事务进入 aborted，不回滚会毒化同线程后续查询。
        """
        try:
            self.session.execute(
                insert(AuditLog).values(
                    event_type='strategy_daily_check',
                    account_name=record['account_name'],
                    strategy=record['strategy'],
                    version=record['version'],
                    event_date=record['date'],
                    payload=json.dumps(record, ensure_ascii=False, default=str),
                    created_at=func.now(),
                )
            )
            self.session.commit()
        except Exception:
            self._safe_rollback()
            raise


__all__ = ['AuditLog', 'AuditLogORMRepository']
