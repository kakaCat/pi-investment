"""市场事件仓储端口（一类一文件）

RFC 015 §3.2（2026-09-11，REQ-cf627b，P3）：应用层只依赖本接口，
ORM 实现见 adapters/outbound/repositories/event_repository.py（表：quant.event_calendar 扩展）。

写入语义（幂等，RFC §5）：
- upsert 以 **evidence_hash 唯一索引**为锚：同 hash 重复写入只更新、不新增行；
  调用方重复 ingest 同一批事件不产生重复行。
- 返回值必须如实反映写入行数（inserted / updated / skipped），禁止静默吞掉失败。
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class IMarketEventRepository(ABC):
    """事件仓储接口（读写在 quant.event_calendar，宏观/政策/个股同表）"""

    @abstractmethod
    def upsert(self, events: List[Dict]) -> Dict:
        """批量幂等写入事件（按 evidence_hash 去重）

        Args:
            events: 领域层 MarketEvent.to_dict() 形态的列表（必须含 evidence_hash）

        Returns:
            {'inserted': int, 'updated': int, 'skipped': int, 'errors': [str]}
            —— skipped = evidence_hash 缺失或非法被拒绝的行（**如实回报**，不静默丢）
        """
        pass

    @abstractmethod
    def list(self, scope: Optional[str] = None, type: Optional[str] = None,
             date_from: Optional[str] = None, date_to: Optional[str] = None,
             limit: int = 200) -> List[Dict]:
        """按范围/类型/日期区间查询（date 字段按 effective_date 过滤）

        Returns:
            事件 dict 列表（含 evidence_hash/source/url/symbols）；无数据返回 []
        """
        pass

    @abstractmethod
    def for_symbol(self, symbol: str, limit: int = 50) -> List[Dict]:
        """某标的的事件（symbols 数组包含该代码，或 scope=macro 的全市场事件）

        Returns:
            事件 dict 列表；无记录返回 []（"没有事件"与"查不到"由调用方按 source 区分）
        """
        pass

    @abstractmethod
    def upcoming(self, days: int = 7, limit: int = 100) -> List[Dict]:
        """未来 N 天内即将发生的事件（含今天，按 effective_date 升序、importance 降序）

        兼容既有语义：原有 /api/events/upcoming 只返回 pending/notified 的宏观事件，
        本方法返回**全部 scope**（宏观+政策+个股）且不按 status 过滤——
        查询口径的切换由调用方（入站适配器）显式选择，不在仓储里偷偷改。
        """
        pass

    @abstractmethod
    def exists_by_hash(self, evidence_hash: str) -> bool:
        """该证据哈希是否已入库（幂等预检 / 增量 ingest 用）"""
        pass

    @abstractmethod
    def default_universe(self, limit: int = 200) -> List[str]:
        """默认个股事件采集池（RFC §3.5 定时任务的标的范围）

        口径（按重要性排序，去重、只取 quant.stocks 中真实存在的代码）：
          1. 持仓（quant.positions 中 quantity > 0 的标的）
          2. 盯盘规则（quant.watch_rules 中 enabled 的标的）
          3. 最近被关注/信号命中的标的（若无更权威来源则留空）
        Returns:
            6 位代码列表；三者皆空时返回 []（调用方据此只做政策 ingest，不伪造标的）
        """
        pass
