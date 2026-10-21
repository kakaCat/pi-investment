"""本地 DB 产业链 provider（RFC 015 §2.3 优先级 4 / §1.5.2 硬约束 4：**最后一级兜底**）

上游全挂时链路不中断，但必须**显式标记 stale**（stale-while-error）：
本 provider 返回的每一行都带 `stale=True` + `updated_at`（库里上次成功写入的时间），
应用层据此在响应里置 stale=true，**不得**当作实时数据。

只读不写（写入走 adapters/outbound/repositories/industry_chain_repository.upsert_chain）。
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from domain.industry_chain.ports.IIndustryChainProvider import IIndustryChainProvider

logger = logging.getLogger(__name__)


class DatabaseChainProvider(IIndustryChainProvider):
    """本地 quant.industry_chain(_node/_member) 兜底源（stale）"""

    def __init__(self, repository=None):
        """Args: repository —— IIndustryChainRepository（缺省走进程级单例）"""
        self._repo = repository
        self.last_error: Optional[str] = None
        self.stale_reason: str = ''
        #: 成员归位失败（node_id 不在本链节点里）的行——如实回报，不静默丢弃
        #: （静默丢成员会让"某标的不在链上"与"库里数据不一致"无法区分）
        self.orphan_members: List[Dict] = []

    @property
    def repo(self):
        if self._repo is None:
            from adapters.outbound.repositories.industry_chain_repository import (
                get_industry_chain_repo,
            )
            self._repo = get_industry_chain_repo()
        return self._repo

    @property
    def name(self) -> str:
        return 'database_chain'

    # -------------------------------------------------------------- 契约实现

    def list_chains(self) -> Optional[List[Dict]]:
        """库中已落库的产业链清单（stale）；库为空返回 []（空结果 ≠ 失败）"""
        self.last_error = None
        try:
            rows = self.repo.list_chains()
        except Exception as exc:
            self.last_error = f"DB 产业链查询异常: {type(exc).__name__}: {exc}"
            logger.warning(self.last_error)
            return None
        out: List[Dict] = []
        for row in rows:
            out.append({
                'chain_id': row.get('chain_id'),
                'name': row.get('name'),
                'description': row.get('description') or '',
                'node_count': row.get('node_count') or 0,
                'member_count': row.get('member_count') or 0,
                'updated_at': str(row.get('updated_at') or ''),
                'curator': '',
                'source': self.name,
                'stale': True,
            })
        return out

    def get_chain(self, chain_id_or_name: str) -> Optional[List[Dict]]:
        """库中某条链的环节 + 成员（stale）；库中没有返回 []（空结果 ≠ 失败）"""
        self.last_error = None
        try:
            data = self.repo.get_chain(chain_id_or_name)
        except Exception as exc:
            self.last_error = f"DB 产业链查询异常: {type(exc).__name__}: {exc}"
            logger.warning(self.last_error)
            return None
        if not data:
            return []
        self.stale_reason = 'DB 缓存（上游策展/主营构成不可用时的兜底），非实时'
        self.orphan_members = []
        updated_at = str(data.get('updated_at') or '')
        nodes_by_id: Dict[str, Dict] = {}
        for node in data.get('nodes') or []:
            nodes_by_id[node.get('node_id')] = {
                'chain_id': data.get('chain_id'),
                'chain_name': data.get('name'),
                'description': data.get('description') or '',
                'chain_rationale': data.get('rationale') or '',
                'node_id': node.get('node_id'),
                'node_name': node.get('name'),
                'stage': node.get('stage'),
                'upstream_of': node.get('upstream_of') or [],
                'downstream_of': node.get('downstream_of') or [],
                'rationale': node.get('rationale') or '',
                'keywords': node.get('keywords') or [],
                'members': [],
                'updated_at': updated_at,
                'stale': True,
                'source': self.name,
            }
        for member in data.get('members') or []:
            node = nodes_by_id.get(member.get('node_id'))
            if node is None:
                # 不静默丢：如实记下"哪个成员指向了不存在的节点"，调用方可据此发现库内不一致
                self.orphan_members.append({
                    'symbol': member.get('symbol'),
                    'node_id': member.get('node_id'),
                    'reason': 'node_id 不在本链节点集合内（库内数据不一致或链被裁剪过）',
                })
                logger.warning('database_chain: 成员 %s 的 node_id=%r 不在链 %s 的节点里，已跳过',
                               member.get('symbol'), member.get('node_id'), chain_id_or_name)
                continue
            node['members'].append({
                'symbol': member.get('symbol'),
                'name': member.get('name'),
                'stage': member.get('stage'),
                'role': member.get('role') or '',
                'exposure_ratio': member.get('exposure_ratio'),
                'exposure_basis': member.get('exposure_basis') or '',
                'exposure_as_of': member.get('exposure_as_of') or '',
                'evidence': member.get('evidence') or '',
                'evidence_kind': member.get('evidence_kind') or '策展',
                'confidence': member.get('confidence') or 'low',
                'source': member.get('source') or self.name,
                'stale': True,
            })
        return list(nodes_by_id.values())

    def get_revenue_exposure(self, symbol: str) -> Optional[List[Dict]]:
        """库中该标的上次成功的主营占比（stale 兜底）；无记录返回 []"""
        self.last_error = None
        try:
            rows = self.repo.get_chain_by_symbol(symbol)
        except Exception as exc:
            self.last_error = f"DB 成员查询异常: {type(exc).__name__}: {exc}"
            logger.warning(self.last_error)
            return None
        out: List[Dict] = []
        fetched_at = datetime.now().isoformat(timespec='seconds')
        for row in rows:
            if row.get('exposure_ratio') is None:
                continue
            out.append({
                'symbol': row.get('symbol'),
                'name': row.get('name') or '',
                'report_date': str(row.get('exposure_as_of') or ''),
                'classification': '按产品分类(DB缓存)',
                'item': str(row.get('exposure_basis') or ''),
                'revenue': None,
                'ratio': row.get('exposure_ratio'),
                'basis': 'DB 缓存（%s 上次落库）' % (row.get('updated_at') or '未知时间'),
                'as_of': str(row.get('exposure_as_of') or row.get('updated_at') or ''),
                'fetched_at': fetched_at,
                'source': self.name,
                'stale': True,
            })
        return out
