"""K 线数据质量审计仓储（public.kline_data_quality）。

2026-09-14（w-32314d00，REQ-24e15d B2）：读取侧原先是
infrastructure/jobs/data_quality_check_job.py 里的 text() 裸 SQL（还配了"连接被回收就
重建会话重试一次"的补丁），这里收口成仓储方法；写入侧在
application/services/data_quality_service.py，单独评估。

⚠️ 与 data_quality_repository.py 的区别：那个管的是 **quant.data_quality_records**
（按标的的检查明细，带 check_date 列）；本文件管的是 **public.kline_data_quality**
（每次 K 线清洗的评分与评级，只有 created_at 时间戳）。两张表名字像、schema 不同、用途不同。
"""
from __future__ import annotations

import logging
from datetime import date as _date
from typing import Optional

from sqlalchemy import func

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import KlineDataQuality

logger = logging.getLogger(__name__)

__all__ = ['KlineQualityRepository']


class KlineQualityRepository(BaseORMRepository[KlineDataQuality]):
    """K 线质量审计（public.kline_data_quality）只读访问。"""

    model = KlineDataQuality

    def count_by_grade_on(self, grade: str, day: Optional[_date] = None) -> int:
        """某日某评级的记录数（默认今天）。

        口径与原 SQL 一致：按 created_at 的**日期**过滤（该表没有 check_date 列，
        只有 created_at 时间戳），故用 func.date(created_at)，与 PostgreSQL 的
        DATE(created_at) 等价。
        """
        target = day or _date.today()
        try:
            return int(
                self.session.query(func.count(KlineDataQuality.id))
                .filter(func.date(KlineDataQuality.created_at) == target)
                .filter(KlineDataQuality.grade == grade)
                .scalar() or 0
            )
        except Exception:
            # 失败必须回滚：调用方（data_quality_check_job）在长流水线末尾做这个查询，
            # 此时同线程的 scoped_session 上可能挂着已 aborted 的事务 ——
            # 不回滚会让"重试一次"直接撞 "current transaction is aborted"（线程毒化）。
            # 这正是原 _get_alert_session() 手工模拟的语义，现在收在仓储里。
            self._safe_rollback()
            raise

    def record_check_result(
        self,
        symbol: str,
        start_date: Optional[str],
        end_date: Optional[str],
        original_count: int,
        cleaned_count: int,
        removed_count: int,
        fixed_count: int,
        error_count: int,
        warning_count: int,
        errors_json,
        warnings_json,
        cleaning_operations_json,
        completeness_score: float,
        consistency_score: float,
        accuracy_score: float,
        overall_score: float,
        grade: str,
        duration_ms: int,
        period: str = 'daily',
    ) -> None:
        """写入一条 K 线清洗质量审计（public.kline_data_quality）。

        2026-09-14（REQ-24e15d）：原实现是
        application/services/data_quality_service.py 里的 session.execute(text("INSERT INTO
        kline_data_quality (...) VALUES (..., NOW())"), {...})。现收口到此，改成 ORM insert。

        逐值对齐要点：
        · **不带 schema 前缀**的旧写法靠的是 search_path（实测 = "$user", public），
          落到的是 public.kline_data_quality —— 模型的 __table_args__ 显式写死 schema='public'，
          两边同一张表（不是 quant.kline_data_quality，后者不存在）；
        · created_at 显式传 func.now()：与原 SQL 的 NOW() 同为"事务时间戳"，
          不依赖列默认值（两者结果相同，显式传是为了让语义写在代码里而不是藏在 DDL 里）；
        · errors_json / warnings_json / cleaning_operations_json 是 **jsonb** 列：
          旧写法传 json.dumps(...) 生成的字符串（PG 隐式 text→jsonb），
          这里传 Python 列表由 JSONB 类型序列化 —— 落库的 jsonb 值逐值一致
          （已用真实写入 + jsonb::text 比对验证）；
        · 异常向上抛：调用方（_persist_quality_result）自己 try/except 记 warning 且不阻断主流程，
          仓储不吞异常；失败时先 rollback，避免把同线程 scoped_session 毒化成
          "current transaction is aborted"（原实现没有回滚，属既有缺陷，见报告）。
        """
        record = KlineDataQuality(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            original_count=original_count,
            cleaned_count=cleaned_count,
            removed_count=removed_count,
            fixed_count=fixed_count,
            error_count=error_count,
            warning_count=warning_count,
            errors_json=errors_json,
            warnings_json=warnings_json,
            cleaning_operations_json=cleaning_operations_json,
            completeness_score=completeness_score,
            consistency_score=consistency_score,
            accuracy_score=accuracy_score,
            overall_score=overall_score,
            grade=grade,
            duration_ms=duration_ms,
            created_at=func.now(),
        )
        try:
            self.session.add(record)
            self.session.commit()
        except Exception:
            self._safe_rollback()
            raise
