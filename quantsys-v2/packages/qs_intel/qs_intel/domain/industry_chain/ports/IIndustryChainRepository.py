"""产业链仓储端口（一类一文件）

RFC 015 §2.1（2026-09-11，REQ-cf627b）：应用层只依赖本接口，
ORM 实现见 adapters/outbound/repositories/industry_chain_repository.py。

写入语义（幂等，RFC §5）：
- upsert_chain 是**整链替换**：以 (chain_id) 为界先删后写（node/member 随之重建），
  保证重复 build 不产生重复行；member 唯一键 (chain_id, symbol, node_id)。
- 返回值必须如实反映写入行数，禁止静默吞掉失败。
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class IIndustryChainRepository(ABC):
    """产业链仓储接口"""

    @abstractmethod
    def list_chains(self) -> List[Dict]:
        """全部产业链清单（含成员数、最近刷新时间、source）

        Returns:
            [{'chain_id','name','description','node_count','member_count','source',
              'updated_at','stale'}]；无数据返回 []
        """
        pass

    @abstractmethod
    def get_chain(self, chain_id_or_name: str) -> Optional[Dict]:
        """单链全貌（node 行 + members，契约同 provider 行契约 B 的聚合形态）

        Returns:
            {'chain_id','name','description','rationale','source','updated_at','stale',
             'nodes': [node dict], 'members': [member dict]}
            未找到返回 None（**不是空 dict**——"没有这条链" 与 "链是空的" 必须可辨）
        """
        pass

    @abstractmethod
    def get_chain_by_symbol(self, symbol: str) -> List[Dict]:
        """个股 → 所属链/环节/占比证据（链式扫描的关键查询）

        Returns:
            [{'chain_id','chain_name','node_id','node_name','stage','symbol','name',
              'role','exposure_ratio','exposure_basis','exposure_as_of',
              'evidence','confidence','source','updated_at'}]
            未命中返回 []
        """
        pass

    @abstractmethod
    def upsert_chain(self, chain: Dict, replace: bool = True) -> Dict:
        """整链落库（幂等）

        Args:
            chain: {'chain_id','name','description','rationale','source','nodes':[...],'members':[...]}
            replace: True=先删同 chain_id 的旧行再写（整链替换）

        Returns:
            {'chain_id','nodes_written','members_written','skipped_symbols':[...],'replaced':bool}
        """
        pass

    @abstractmethod
    def search_nodes(self, keyword: str, limit: int = 50) -> List[Dict]:
        """按关键词检索环节（node 名/node_id/关键词命中），用于"哪个环节属于哪条链"的反查"""
        pass

    @abstractmethod
    def known_symbols(self, symbols: List[str]) -> List[str]:
        """过滤出 quant.stocks 中真实存在的代码（外键安全；不存在的必须被如实丢弃并回报）"""
        pass
