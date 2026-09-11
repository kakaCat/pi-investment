"""产业链 provider 端口（一类一文件，对齐 domain/trading/ports 既有组织方式）

RFC 015 §2.1 / §1.5（2026-09-11，REQ-cf627b）。实现方（出站适配器）必须：
1. 提供唯一 name（注册进 DataProviderManager 的 industry_chain_providers）
2. 成功返回 List[dict]（可为空列表 = 该源无此链路/该标的），
   失败返回 None 且写 self.last_error（**失败与空结果语义分离**：失败 fail-loud，
   空结果由 manager 继续降级到下一源，禁止用空结果/默认值冒充成功）

## 行契约（provider 与领域层之间的唯一接口，改这里=改所有 provider）

### A. list_chains() -> List[dict]
    {'chain_id': str, 'name': str, 'node_count': int, 'member_count': int,
     'updated_at': str, 'source': str, 'stale': bool}

### B. get_chain(chain_id_or_name) -> List[dict]（**node 行**，每行可带 members）
    {'chain_id': str, 'chain_name': str,
     'node_id': str, 'node_name': str, 'stage': 'upstream|midstream|downstream|terminal',
     'upstream_of': [node_id], 'downstream_of': [node_id], 'rationale': str,
     'keywords': [str],
     'members': [
        {'symbol': '600176', 'name': '中国巨石', 'stage': 'upstream', 'role': '龙头',
         'exposure_ratio': 0.9732,        # 0-1 小数，百分数须由 provider 归一；无则 None
         'exposure_basis': '主营构成：玻纤及其制品相关（东财F10）',
         'exposure_as_of': '2026-06-30',
         'evidence': '证据文本（可追溯，必须写清来源与时点）',
         'evidence_kind': '主营构成|产品构成|策展|行业分类|概念成分',
         'confidence': 'high|medium|low',
         'source': provider name}
     ]}

### C. get_revenue_exposure(symbol) -> List[dict]（主营构成原始行）
    {'symbol': str, 'name': str, 'report_date': 'YYYY-MM-DD',
     'classification': '按产品分类|按行业分类|按地区分类',
     'item': '玻纤及其制品相关', 'revenue': float|None,
     'ratio': 0.9732,                     # 0-1 小数
     'basis': str, 'as_of': str, 'source': str}
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class IIndustryChainProvider(ABC):
    """产业链数据 provider 抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称（唯一，用于日志与 source 归因）"""
        pass

    @abstractmethod
    def list_chains(self) -> Optional[List[Dict]]:
        """全部产业链清单（行契约 A）

        Returns:
            成功返回 List[dict]（空列表 = 该源不提供产业链清单）；
            失败返回 None（必须同时在 self.last_error 写明原因）
        """
        pass

    @abstractmethod
    def get_chain(self, chain_id_or_name: str) -> Optional[List[Dict]]:
        """单条产业链的环节 + 成员原始行（行契约 B）

        Args:
            chain_id_or_name: chain_id（如 'fiberglass_pcb'）或名称/别名（如 '玻纤'）

        Returns:
            成功返回 List[dict]（空列表 = 该源没有这条链）；失败返回 None
            （必须同时在 self.last_error 写明原因——"没这条链" 与 "取数失败" 必须可辨）
        """
        pass

    @abstractmethod
    def get_revenue_exposure(self, symbol: str) -> Optional[List[Dict]]:
        """个股主营构成（行契约 C）

        Returns:
            成功返回 List[dict]（空列表 = 该标的无主营构成数据）；
            失败返回 None（必须同时在 self.last_error 写明原因）
        """
        pass
