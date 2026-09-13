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
