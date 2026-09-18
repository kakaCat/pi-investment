"""盯盘回执仓储适配器（REQ-c9f899 t6，2026-09-18）

实现 domain/watch/ports.py 的 IWatchReceiptRepository（data-model.md §5 的
quant.watch_receipts）：

  · record        —— 追加写一条回执（升级即 / 处置后 / 超时 / 抑噪）；
  · list_by_todo  —— 按待办取回执链（时间升序），供追溯"升级即 → 处置后"两段；
  · exists        —— 幂等查询：同一 (todo_id, kind, payload_digest) 是否已落过。

按 ADR-001（六边形架构）：**SQL/ORM 只允许出现在适配器层**——应用层（ReceiptService）
只依赖端口。失败语义与 watch_todo_repository 一致：**读写失败一律向上抛**（回滚线程
scoped session 后 re-raise）。特别注意 exists 不得静默返回 False——那会把"回执库坏了"
伪装成"这条回执还没发过"，随后每轮巡检都会重复发送（正是 I1 要治的噪音）。

幂等的真实边界（诚实标注）：本适配器只提供 **check-then-act** 的幂等查询；迁移
20260918_watch_todo_loop.py 没有为 (todo_id, kind, payload_digest) 建唯一索引，
因此**两个进程同时跑巡检**仍可能双写双发。单实例 1 分钟巡检（t12 的注册方式）下
不触发该竞态；若将来要多实例，必须补唯一约束并改用 ON CONFLICT DO NOTHING
（属迁移改动，不在 t6 范围）。
"""
from typing import Any, List, Optional

import structlog

from domain.watch.ports import RECEIPT_KINDS
from infrastructure.persistence.orm.base_repository import BaseORMRepository
from infrastructure.persistence.orm.models.watch_todo import WatchReceipt

logger = structlog.get_logger(__name__)

#: payload_digest 列宽（VARCHAR(64)）——sha256 十六进制正好 64 字符
_MAX_DIGEST_LEN = 64


def _iso(value):
    """datetime → ISO 字符串（None 透传）"""
    return value.isoformat() if value is not None else None


def receipt_to_dict(receipt: Any) -> dict:
    """回执记录 → API 响应 dict（snake_case，与 todo_to_dict 同风格）

    ⚠️ created_at 一律 ISO 字符串：JSONResponse 无法序列化 datetime（会 500）。
    """
    return {
        'id': receipt.id,
        'todo_id': receipt.todo_id,
        'kind': receipt.kind,
        'channel': receipt.channel,
        'delivery_status': receipt.delivery_status,
        'message_id': receipt.message_id,
        'payload_digest': receipt.payload_digest,
        'created_at': _iso(receipt.created_at),
    }


class WatchReceiptRepository(BaseORMRepository[WatchReceipt]):
    """IWatchReceiptRepository 的 PostgreSQL 实现（quant.watch_receipts）"""

    model = WatchReceipt

    # ── 写入 ────────────────────────────────────────────────

    def record(self, todo_id: int, kind: str, channel: Optional[str] = None,
               delivery_status: Optional[str] = None, message_id: Optional[str] = None,
               payload_digest: str = '') -> WatchReceipt:
        """追加写一条回执。

        写库前先做**响亮校验**（在触碰 session 之前）：
          · kind ∈ RECEIPT_KINDS（与 DB CHECK 同集）；
          · payload_digest 非空且 ≤64 字符——空 digest 让幂等退化为"每次都是新回执"，
            必须拒绝而不是让列 NOT NULL 在提交时才报错。
        """
        kind_value = str(kind or '').strip().lower()
        if kind_value not in RECEIPT_KINDS:
            raise ValueError(f'kind={kind!r} 不在 {list(RECEIPT_KINDS)} 内')
        digest = str(payload_digest or '').strip()
        if not digest:
            raise ValueError('payload_digest 必填：空摘要会让回执幂等失效（只落一条/只发一次）')
        if len(digest) > _MAX_DIGEST_LEN:
            raise ValueError(
                f'payload_digest 超长（{len(digest)} > {_MAX_DIGEST_LEN}），列宽不够会静默截断')

        receipt = WatchReceipt(
            todo_id=todo_id, kind=kind_value, channel=channel,
            delivery_status=delivery_status, message_id=message_id,
            payload_digest=digest,
        )
        try:
            session = self.session
            session.add(receipt)
            session.commit()
            session.refresh(receipt)
        except Exception as e:  # noqa: BLE001 - 失败必须响亮
            logger.error('回执落库失败', todo_id=todo_id, kind=kind_value, error=str(e))
            self._safe_rollback()
            raise
        return receipt

    # ── 读取 ────────────────────────────────────────────────

    def list_by_todo(self, todo_id: int) -> List[WatchReceipt]:
        """按待办取回执（created_at → id 升序，保证时序可读）"""
        try:
            return (
                self.session.query(WatchReceipt)
                .filter(WatchReceipt.todo_id == todo_id)
                .order_by(WatchReceipt.created_at.asc(), WatchReceipt.id.asc())
                .all()
            )
        except Exception:  # noqa: BLE001
            self._safe_rollback()
            raise

    def exists(self, todo_id: int, kind: str, payload_digest: str) -> bool:
        """幂等查询：已落过该 (todo_id, kind, payload_digest) 返回 True。

        失败**向上抛**（绝不 catch 成 False）：静默 False 会让"回执库坏了"变成
        "还没发过"，下一轮巡检重复发送并再次失败——噪声被放大而不是暴露。
        """
        kind_value = str(kind or '').strip().lower()
        digest = str(payload_digest or '').strip()
        if not digest:
            # 空摘要无法判定：响亮拒绝，避免调用方拿"必然 False"当幂等保障
            raise ValueError('payload_digest 必填：空摘要无法判定幂等（exists 不做猜测）')
        try:
            row = (
                self.session.query(WatchReceipt.id)
                .filter(WatchReceipt.todo_id == todo_id,
                        WatchReceipt.kind == kind_value,
                        WatchReceipt.payload_digest == digest)
                .first()
            )
        except Exception:  # noqa: BLE001
            self._safe_rollback()
            raise
        return row is not None
