"""人工策展产业链 provider（RFC 015 §2.3 优先级 0，**权威且不可降级**）

通道：domain/industry_chain/seed/*.yaml（人工撰写，带 rationale，可审计、可质疑、可 review）。
**不用 LLM 自动生成拓扑**（RFC §7 明确不做：不可审计）。

契约（domain/industry_chain/ports/IIndustryChainProvider.py 的行契约 A/B）：
- list_chains()   → 行契约 A（8 条策展链）
- get_chain(name) → 行契约 B（环节 + 代表标的）；**未命中返回 None + last_error**（fail-loud：
  拓扑不可降级，不能把"没有这条链"伪装成"这条链是空的"，否则调用方会拿着空拓扑去扫描）
- get_revenue_exposure(symbol) → 恒返回 []（策展不提供主营构成；空列表=该源无此类数据，
  与"失败"语义严格区分，避免污染熔断统计）

真实数据说明：seed 里的成员 evidence 是**人工依据**（主线逻辑/既有股票池/财报口径打样），
构建链时由应用层再用东财/同花顺主营构成做**动态校验**，冲突时以主营构成为准（RFC §2.3）。
"""
import logging
import os
from typing import Dict, List, Optional

import yaml

from domain.industry_chain.ports.IIndustryChainProvider import IIndustryChainProvider

logger = logging.getLogger(__name__)

# 默认 seed 目录：repo_root/domain/industry_chain/seed
# 本文件位于 <repo>/adapters/outbound/datasources/providers/industry_chain/curated.py
# → 上溯 5 层到 <repo>。可用环境变量 QUANTSYS_INDUSTRY_CHAIN_SEED_DIR 覆盖（测试/多部署用）。
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          '..', '..', '..', '..', '..'))
_DEFAULT_SEED_DIR = os.environ.get(
    'QUANTSYS_INDUSTRY_CHAIN_SEED_DIR',
    os.path.join(_REPO_ROOT, 'domain', 'industry_chain', 'seed'),
)


class CuratedChainProvider(IIndustryChainProvider):
    """人工策展产业链（seed YAML）"""

    def __init__(self, seed_dir: Optional[str] = None):
        self.seed_dir = seed_dir or _DEFAULT_SEED_DIR
        self.last_error: Optional[str] = None
        self._cache: Optional[Dict[str, dict]] = None
        self._cache_stamp: Optional[float] = None

    @property
    def name(self) -> str:
        return 'curated'

    # ------------------------------------------------------------------ seed

    def _seed_files(self) -> List[str]:
        if not os.path.isdir(self.seed_dir):
            return []
        return sorted(
            os.path.join(self.seed_dir, f)
            for f in os.listdir(self.seed_dir)
            if f.endswith(('.yaml', '.yml'))
        )

    def _load(self) -> Dict[str, dict]:
        """加载全部 seed（按目录 mtime 缓存；文件损坏直接抛错，不静默跳过）"""
        files = self._seed_files()
        stamp = max([os.path.getmtime(f) for f in files], default=0.0)
        if self._cache is not None and self._cache_stamp == stamp:
            return self._cache

        chains: Dict[str, dict] = {}
        for path in files:
            with open(path, encoding='utf-8') as handle:
                data = yaml.safe_load(handle)
            if not isinstance(data, dict) or not data.get('chain_id'):
                raise ValueError(f"seed 文件缺少 chain_id: {path}")
            if not data.get('rationale'):
                raise ValueError(f"seed 文件缺少 rationale（拓扑必须写人工判断依据）: {path}")
            chain_id = str(data['chain_id'])
            if chain_id in chains:
                raise ValueError(f"chain_id 重复: {chain_id}（{path}）")
            for node in data.get('nodes') or []:
                if not node.get('rationale'):
                    raise ValueError(f"seed 节点缺少 rationale: {chain_id}.{node.get('node_id')}")
                if not node.get('keywords'):
                    raise ValueError(f"seed 节点缺少 keywords（主营构成归位需要关键词）: {chain_id}.{node.get('node_id')}")
            data['_source_file'] = path
            chains[chain_id] = data
        self._cache = chains
        self._cache_stamp = stamp
        return chains

    # ------------------------------------------------------------- 匹配逻辑

    @staticmethod
    def _matches(data: dict, key: str) -> bool:
        key = str(key or '').strip()
        if not key:
            return False
        candidates = [str(data.get('chain_id') or ''), str(data.get('name') or '')]
        candidates += [str(a) for a in (data.get('aliases') or [])]
        if key in candidates:
            return True
        # 退一步做包含匹配（'玻纤' 命中 '玻纤·电子布·PCB链'），仍不命中则视为不存在
        return any(key in candidate for candidate in candidates if candidate)

    def find(self, chain_id_or_name: str) -> Optional[dict]:
        """按 chain_id / 名称 / 别名查找（未命中返回 None）"""
        chains = self._load()
        key = str(chain_id_or_name or '').strip()
        exact = chains.get(key)
        if exact:
            return exact
        for data in chains.values():
            if self._matches(data, key):
                return data
        return None

    def available(self) -> List[str]:
        return sorted(self._load().keys())

    # -------------------------------------------------------------- 契约实现

    def list_chains(self) -> Optional[List[Dict]]:
        self.last_error = None
        try:
            chains = self._load()
        except Exception as exc:  # seed 损坏 = 部署事故，必须显式失败
            self.last_error = f"策展 seed 加载失败（{self.seed_dir}）: {type(exc).__name__}: {exc}"
            logger.error(self.last_error)
            return None
        if not chains:
            self.last_error = (
                f"策展 seed 目录不存在或无 YAML: {self.seed_dir}"
                "（拓扑是唯一权威源且不可降级，故此处显式失败而非返回空清单）"
            )
            return None
        rows: List[Dict] = []
        for chain_id, data in sorted(chains.items()):
            nodes = data.get('nodes') or []
            members = sum(len(node.get('members') or []) for node in nodes)
            rows.append({
                'chain_id': chain_id,
                'name': data.get('name') or chain_id,
                'description': data.get('description') or '',
                'node_count': len(nodes),
                'member_count': members,
                'updated_at': str(data.get('curated_at') or ''),
                'curator': data.get('curator') or '',
                'source': self.name,
                'stale': False,
            })
        return rows

    def get_chain(self, chain_id_or_name: str) -> Optional[List[Dict]]:
        self.last_error = None
        try:
            data = self.find(chain_id_or_name)
        except Exception as exc:
            self.last_error = f"策展 seed 加载失败（{self.seed_dir}）: {type(exc).__name__}: {exc}"
            logger.error(self.last_error)
            return None
        if data is None:
            self.last_error = (
                f"策展库中不存在产业链 {chain_id_or_name!r}（可用: {', '.join(self.available())}）"
            )
            return None

        chain_id = str(data['chain_id'])
        rows: List[Dict] = []
        for node in data.get('nodes') or []:
            members = []
            for member in node.get('members') or []:
                members.append({
                    'symbol': str(member.get('symbol') or '').strip(),
                    'name': str(member.get('name') or ''),
                    'stage': node.get('stage'),
                    'role': str(member.get('role') or ''),
                    'exposure_ratio': member.get('exposure_ratio'),
                    'exposure_basis': member.get('exposure_basis') or '',
                    'exposure_as_of': str(member.get('exposure_as_of') or data.get('curated_at') or ''),
                    'evidence': str(member.get('evidence') or ''),
                    'evidence_kind': member.get('evidence_kind') or '策展',
                    'confidence': member.get('confidence') or 'medium',
                    'source': self.name,
                })
            rows.append({
                'chain_id': chain_id,
                'chain_name': data.get('name') or chain_id,
                'description': data.get('description') or '',
                'chain_rationale': data.get('rationale') or '',
                'curator': data.get('curator') or '',
                'curated_at': str(data.get('curated_at') or ''),
                'node_id': str(node.get('node_id') or ''),
                'node_name': str(node.get('name') or ''),
                'stage': node.get('stage'),
                'upstream_of': list(node.get('upstream_of') or []),
                'downstream_of': list(node.get('downstream_of') or []),
                'rationale': str(node.get('rationale') or ''),
                'keywords': list(node.get('keywords') or []),
                'members': members,
                'source': self.name,
            })
        return rows

    def get_revenue_exposure(self, symbol: str) -> Optional[List[Dict]]:
        """策展不提供主营构成：返回 []（该源无此类数据），不是失败"""
        self.last_error = None
        return []
