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

# 默认 seed 目录：**按 seed 目录本身定位**，不再猜 repo_root。
#
# 历史与故障（2026-10-21 定位，investor/w-36c3225e）：
#   本文件曾用「自祖先目录向上找 <root>/domain/industry_chain/seed 标记」推断仓库根，
#   再拼 `<root>/domain/industry_chain/seed`。2026-09-11 抽离 qs-intel 二方包
#   （commit 898039f23）把 seed 目录搬到
#   `packages/qs_intel/qs_intel/domain/industry_chain/seed`，
#   但本文件的查找规则没跟着改 ⇒ 解析到 `packages/domain/industry_chain/seed`（不存在）。
#   后果：策展源**一直**读不到任何链（`available()` 返回空列表），
#   chain_list 只能靠 DB 兜底显示 8 条历史链，chain_scan 一律 502
#   「产业链拓扑取数失败（人工策展为唯一权威源且不可降级）」。
#   该故障是**静默**的：既不报错也不告警，只是"策展库中不存在产业链 'xxx'（可用: ）"，
#   且 DB 兜底掩盖了它（清单看起来是正常的 8 条链）。
#
# 修法：**按已知布局枚举候选路径**，逐个探测，第一个存在的即用。
#   ⚠️ 关键结构事实：provider 代码在 **qs_market_data** 包，而 seed 在 **qs_intel** 包
#     （2026-09-11 抽离 qs-intel 二方包 commit 898039f23 后的布局）——
#     **两者是不同包，"自本文件向上找"在结构上永远不可能命中 qs_intel 里的 seed**。
#     这正是原实现失效且静默的根因：它假设 seed 与 provider 同在一条祖先链上。
#   候选布局（按优先级）：
#     0) 环境变量 QUANTSYS_INDUSTRY_CHAIN_SEED_DIR（测试/多部署用）
#     1) <repo>/packages/qs_intel/qs_intel/domain/industry_chain/seed   ← 现役
#     2) <repo>/domain/industry_chain/seed                             ← 旧布局
#   找不到时返回 None（**不猜、不兜底成假路径**）——由调用方显式失败，
#   避免再次"指向一个不存在的目录 ⇒ 可用链列表为空"的静默失败。
# 可用环境变量 QUANTSYS_INDUSTRY_CHAIN_SEED_DIR 覆盖（测试/多部署用）。
def _find_seed_dir() -> Optional[str]:
    """按已知布局枚举 seed 目录；找不到返回 None（不返回假路径）"""
    override = os.environ.get('QUANTSYS_INDUSTRY_CHAIN_SEED_DIR')
    if override:
        return override if os.path.isdir(override) else None

    # 找 repo 根：**按标记定位**（不用固定上溯层数——包一重构层数就变，
    # 原实现的 7 层假设正是与实际 8 层差一层而失效的原因之一）。
    # 标记：含 packages/qs_intel 的目录（现役布局）或含 domain/industry_chain 的目录（旧布局）。
    here = os.path.dirname(os.path.abspath(__file__))
    repo = None
    _d = here
    while True:
        if os.path.isdir(os.path.join(_d, 'packages', 'qs_intel')):
            repo = _d
            break
        if os.path.isdir(os.path.join(_d, 'domain', 'industry_chain')):
            repo = _d
            break
        _parent = os.path.dirname(_d)
        if _parent == _d:
            break
        _d = _parent

    candidates = []
    if repo:
        candidates.append(os.path.join(repo, 'packages', 'qs_intel', 'qs_intel',
                                       'domain', 'industry_chain', 'seed'))   # 布局 1（现役）
        candidates.append(os.path.join(repo, 'domain', 'industry_chain', 'seed'))  # 布局 2（旧）
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    # 兜底：向上逐级找 industry_chain/seed（兼容未来把 seed 与 provider 放回同链的布局）
    _d = here
    while True:
        for pattern in (('domain', 'industry_chain', 'seed'), ('industry_chain', 'seed')):
            candidate = os.path.join(_d, *pattern)
            if os.path.isdir(candidate):
                return candidate
        _parent = os.path.dirname(_d)
        if _parent == _d:
            return None
        _d = _parent


_SEED_DIR = _find_seed_dir()
_DEFAULT_SEED_DIR = _SEED_DIR or ''
if not _SEED_DIR:
    # 显式告警：这条以前是静默失败（解析到假路径 ⇒ 可用链为空）
    logger.error(
        '产业链策展 seed 目录未找到（已查找 <ancestor>/domain/industry_chain/seed 与 '
        '<ancestor>/industry_chain/seed）：策展源将不可用，chain_list 只能走 DB 兜底、'
        'chain_scan 会 502。可用环境变量 QUANTSYS_INDUSTRY_CHAIN_SEED_DIR 指定。'
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
        # seed_dir 为 ''（未找到目录）时 isdir('') 返回 False ⇒ 走空列表分支，不抛异常
        if not self.seed_dir or not os.path.isdir(self.seed_dir):
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
