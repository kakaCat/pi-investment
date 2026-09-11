"""产业链仓储 ORM 实现（RFC 015 §2.1/§2.5，P2）

实现 domain/industry_chain/ports/IIndustryChainRepository 的全部方法。
本文件是**出站适配器**（允许 import infrastructure/ORM），领域/应用层不得反向依赖它。

写入纪律（防静默坏数据）：
- upsert_chain 是**整链替换**（先删后写），保证重复 build 幂等（RFC §5「幂等」验收项）。
- symbol 外键安全：写库前用 known_symbols 过滤，不在 quant.stocks 的代码**如实回报**
  （skipped_symbols），而不是让外键异常炸掉整条链或悄悄丢掉。
- exposure_ratio 由 DB CHECK 兜底（0-1），百分数写不进去 = fail-loud。
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.exc import SQLAlchemyError

from domain.industry_chain.ports.IIndustryChainRepository import IIndustryChainRepository
from infrastructure.persistence.orm.models.industry_chain import (
    IndustryChain as IndustryChainORM,
    IndustryChainMember as IndustryChainMemberORM,
    IndustryChainNode as IndustryChainNodeORM,
)
from infrastructure.persistence.orm.models.stock import Stock

logger = logging.getLogger(__name__)


class IndustryChainORMRepository(IIndustryChainRepository):
    """quant.industry_chain(_node/_member) 仓储"""

    # ------------------------------------------------------------------ 内部

    @property
    def session(self):
        from infrastructure.persistence.orm.config import get_session
        return get_session()

    def _safe_rollback(self):
        try:
            self.session.rollback()
        except Exception:
            pass

    @staticmethod
    def _iso(value) -> str:
        if value is None:
            return ''
        if isinstance(value, datetime):
            return value.isoformat(timespec='seconds')
        return str(value)

    def _chain_model(self, chain_id_or_name: str) -> Optional[IndustryChainORM]:
        key = str(chain_id_or_name or '').strip()
        if not key:
            return None
        row = self.session.query(IndustryChainORM).filter_by(chain_id=key).first()
        if row is not None:
            return row
        row = self.session.query(IndustryChainORM).filter_by(name=key).first()
        if row is not None:
            return row
        return (self.session.query(IndustryChainORM)
                .filter(IndustryChainORM.name.contains(key))
                .order_by(IndustryChainORM.chain_id)
                .first())

    # ------------------------------------------------------------------ 读

    def list_chains(self) -> List[Dict]:
        try:
            chains = (self.session.query(IndustryChainORM)
                      .order_by(IndustryChainORM.chain_id).all())
            out: List[Dict] = []
            for chain in chains:
                node_count = (self.session.query(IndustryChainNodeORM)
                              .filter_by(chain_id=chain.chain_id).count())
                member_count = (self.session.query(IndustryChainMemberORM)
                                .filter_by(chain_id=chain.chain_id).count())
                out.append({
                    'chain_id': chain.chain_id,
                    'name': chain.name,
                    'description': chain.description or '',
                    'rationale': chain.rationale or '',
                    'curator': chain.curator or '',
                    'source': chain.source,
                    'node_count': node_count,
                    'member_count': member_count,
                    'created_at': self._iso(chain.created_at),
                    'updated_at': self._iso(chain.updated_at),
                })
            return out
        except SQLAlchemyError as exc:
            self._safe_rollback()
            logger.error("list_chains failed: %s", exc)
            raise

    def get_chain(self, chain_id_or_name: str) -> Optional[Dict]:
        try:
            chain = self._chain_model(chain_id_or_name)
            if chain is None:
                return None
            nodes = (self.session.query(IndustryChainNodeORM)
                     .filter_by(chain_id=chain.chain_id)
                     .order_by(IndustryChainNodeORM.id).all())
            members = (self.session.query(IndustryChainMemberORM)
                       .filter_by(chain_id=chain.chain_id)
                       .order_by(IndustryChainMemberORM.id).all())
            return {
                'chain_id': chain.chain_id,
                'name': chain.name,
                'description': chain.description or '',
                'rationale': chain.rationale or '',
                'curator': chain.curator or '',
                'source': chain.source,
                'created_at': self._iso(chain.created_at),
                'updated_at': self._iso(chain.updated_at),
                'nodes': [{
                    'node_id': node.node_id,
                    'name': node.name,
                    'stage': node.stage,
                    'upstream_of': list(node.upstream_of or []),
                    'downstream_of': list(node.downstream_of or []),
                    'keywords': list(node.keywords or []),
                    'rationale': node.rationale or '',
                } for node in nodes],
                'members': [{
                    'symbol': item.symbol,
                    'name': item.name or '',
                    'node_id': item.node_id,
                    'stage': item.stage,
                    'role': item.role or '',
                    'exposure_ratio': item.exposure_ratio,
                    'exposure_basis': item.exposure_basis or '',
                    'exposure_as_of': item.exposure_as_of or '',
                    'evidence': item.evidence or '',
                    'evidence_kind': item.evidence_kind or '',
                    'confidence': item.confidence or 'low',
                    'source': item.source or '',
                    'conflict': item.conflict or '',
                    'as_of': self._iso(item.as_of),
                    'updated_at': self._iso(item.updated_at),
                } for item in members],
            }
        except SQLAlchemyError as exc:
            self._safe_rollback()
            logger.error("get_chain failed: %s", exc)
            raise

    def get_chain_by_symbol(self, symbol: str) -> List[Dict]:
        try:
            rows = (self.session.query(IndustryChainMemberORM, IndustryChainORM)
                    .join(IndustryChainORM,
                          IndustryChainORM.chain_id == IndustryChainMemberORM.chain_id)
                    .filter(IndustryChainMemberORM.symbol == str(symbol).strip())
                    .order_by(IndustryChainORM.chain_id, IndustryChainMemberORM.node_id)
                    .all())
            out: List[Dict] = []
            for member, chain in rows:
                out.append({
                    'chain_id': chain.chain_id,
                    'chain_name': chain.name,
                    'node_id': member.node_id,
                    'node_name': '',
                    'stage': member.stage,
                    'symbol': member.symbol,
                    'name': member.name or '',
                    'role': member.role or '',
                    'exposure_ratio': member.exposure_ratio,
                    'exposure_basis': member.exposure_basis or '',
                    'exposure_as_of': member.exposure_as_of or '',
                    'evidence': member.evidence or '',
                    'evidence_kind': member.evidence_kind or '',
                    'confidence': member.confidence or 'low',
                    'source': member.source or '',
                    'conflict': member.conflict or '',
                    'updated_at': self._iso(member.updated_at),
                })
            # 补 node_name（一次查询，避免 N+1）
            node_ids = {row['node_id'] for row in out}
            if node_ids:
                nodes = (self.session.query(IndustryChainNodeORM)
                         .filter(IndustryChainNodeORM.node_id.in_(node_ids)).all())
                name_by_key = {(n.chain_id, n.node_id): n.name for n in nodes}
                for row in out:
                    row['node_name'] = name_by_key.get((row['chain_id'], row['node_id']), '')
            return out
        except SQLAlchemyError as exc:
            self._safe_rollback()
            logger.error("get_chain_by_symbol failed: %s", exc)
            raise

    def search_nodes(self, keyword: str, limit: int = 50) -> List[Dict]:
        try:
            key = str(keyword or '').strip()
            query = self.session.query(IndustryChainNodeORM, IndustryChainORM).join(
                IndustryChainORM, IndustryChainORM.chain_id == IndustryChainNodeORM.chain_id)
            if key:
                query = query.filter(
                    IndustryChainNodeORM.name.contains(key)
                    | IndustryChainNodeORM.node_id.contains(key)
                    | IndustryChainORM.name.contains(key)
                )
            rows = query.order_by(IndustryChainORM.chain_id, IndustryChainNodeORM.id).limit(int(limit)).all()
            return [{
                'chain_id': chain.chain_id,
                'chain_name': chain.name,
                'node_id': node.node_id,
                'node_name': node.name,
                'stage': node.stage,
                'keywords': list(node.keywords or []),
                'rationale': node.rationale or '',
            } for node, chain in rows]
        except SQLAlchemyError as exc:
            self._safe_rollback()
            logger.error("search_nodes failed: %s", exc)
            raise

    def known_symbols(self, symbols: List[str]) -> List[str]:
        wanted = [str(s).strip() for s in (symbols or []) if str(s).strip()]
        if not wanted:
            return []
        try:
            rows = (self.session.query(Stock.symbol)
                    .filter(Stock.symbol.in_(wanted)).all())
            known = {row[0] for row in rows}
            return [s for s in wanted if s in known]
        except SQLAlchemyError as exc:
            self._safe_rollback()
            logger.error("known_symbols failed: %s", exc)
            raise

    # ------------------------------------------------------------------ 写

    def upsert_chain(self, chain: Dict, replace: bool = True) -> Dict:
        chain_id = str(chain.get('chain_id') or '').strip()
        if not chain_id:
            raise ValueError("upsert_chain 需要 chain_id")
        nodes = chain.get('nodes') or []
        members = chain.get('members') or []
        if not nodes:
            raise ValueError(f"upsert_chain 拒绝写入无环节的链: {chain_id}")

        symbols = [str(m.get('symbol')) for m in members if m.get('symbol')]
        known = set(self.known_symbols(symbols))
        skipped = sorted({s for s in symbols if s not in known})

        try:
            if replace:
                existing = self.session.query(IndustryChainORM).filter_by(chain_id=chain_id).first()
                if existing is not None:
                    self.session.delete(existing)  # 级联删 node/member
                    self.session.flush()

            row = self.session.query(IndustryChainORM).filter_by(chain_id=chain_id).first()
            if row is None:
                row = IndustryChainORM(
                    chain_id=chain_id,
                    name=str(chain.get('name') or chain_id),
                    description=str(chain.get('description') or ''),
                    rationale=str(chain.get('rationale') or ''),
                    curator=str(chain.get('curator') or ''),
                    source=str(chain.get('source') or 'curated'),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                self.session.add(row)
            else:
                row.name = str(chain.get('name') or row.name)
                row.description = str(chain.get('description') or row.description or '')
                row.rationale = str(chain.get('rationale') or row.rationale or '')
                row.curator = str(chain.get('curator') or row.curator or '')
                row.source = str(chain.get('source') or row.source)
                row.updated_at = datetime.now()

            node_ids = set()
            for node in nodes:
                node_id = str(node.get('node_id') or '').strip()
                if not node_id:
                    continue
                node_ids.add(node_id)
                self.session.add(IndustryChainNodeORM(
                    chain_id=chain_id,
                    node_id=node_id,
                    name=str(node.get('name') or node_id),
                    stage=str(node.get('stage') or 'upstream'),
                    upstream_of=list(node.get('upstream_of') or []),
                    downstream_of=list(node.get('downstream_of') or []),
                    keywords=list(node.get('keywords') or []),
                    rationale=str(node.get('rationale') or ''),
                    updated_at=datetime.now(),
                ))

            written = 0
            seen_keys = set()
            for member in members:
                symbol = str(member.get('symbol') or '').strip()
                node_id = str(member.get('node_id') or '').strip()
                if not symbol or not node_id or node_id not in node_ids:
                    continue
                if symbol not in known:
                    continue  # 外键安全：不在 stocks 表的代码不入库（已在 skipped 中如实回报）
                key = (symbol, node_id)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                self.session.add(IndustryChainMemberORM(
                    chain_id=chain_id,
                    node_id=node_id,
                    symbol=symbol,
                    name=str(member.get('name') or '')[:80],
                    stage=str(member.get('stage') or 'midstream'),
                    role=str(member.get('role') or '')[:40],
                    exposure_ratio=member.get('exposure_ratio'),
                    exposure_basis=str(member.get('exposure_basis') or '')[:2000],
                    exposure_as_of=str(member.get('exposure_as_of') or '')[:20],
                    evidence=str(member.get('evidence') or ''),
                    evidence_kind=str(member.get('evidence_kind') or '')[:20],
                    confidence=str(member.get('confidence') or 'low')[:10],
                    source=str(member.get('source') or '')[:40],
                    conflict=str(member.get('conflict') or ''),
                    as_of=datetime.now(),
                    updated_at=datetime.now(),
                ))
                written += 1

            self.session.commit()
            return {
                'chain_id': chain_id,
                'nodes_written': len(node_ids),
                'members_written': written,
                'skipped_symbols': skipped,
                'replaced': bool(replace),
            }
        except SQLAlchemyError as exc:
            self._safe_rollback()
            logger.error("upsert_chain failed for %s: %s", chain_id, exc)
            raise


_repo_instance: Optional[IndustryChainORMRepository] = None


def get_industry_chain_repo() -> IndustryChainORMRepository:
    """进程级单例（与 get_kline_repo/get_minute_kline_repo 同一模式）"""
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = IndustryChainORMRepository()
    return _repo_instance
