"""板块成分股持久化快照缓存（2026-10-21）。

为什么需要：板块成分查询只有东财主源+（此前为桩的）备源。主源被限流/断连时
（实测 `RemoteDisconnected`），
  · 政策盯盘 → 板块成分 → 持仓交集 这条路由直接 `mapping_missing`（fail-open，
    不会误报，但也等于当轮失明）；
  · 共振核验同样降级为「不校验」。
成分股是**低频变化数据**（季度调仓级别），完全适合用「上次成功快照」兜底：
宁可标注 degraded 用昨天的成分，也不要在盘中整段失明。

设计纪律：
  · 只缓存**成功且非空**的结果（found=True 且 stocks 非空）——空/未找到绝不入缓存，
    否则「板块改名/不存在」会被固化成假事实；
  · 读取不设 TTL：stale 也比没有强，但返回 `saved_at/age_sec` 让调用方如实标注；
  · 落盘原子（tmp + os.replace），并发读安全；写失败只告警不抛（不影响主链路）；
  · 路径可用 `QS_SECTOR_CACHE_PATH` 覆盖（测试用临时文件）。
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_CACHE_PATH_ENV = 'QS_SECTOR_CACHE_PATH'


def _default_path() -> Path:
    override = os.getenv(DEFAULT_CACHE_PATH_ENV, '').strip()
    if override:
        return Path(override)
    # 仓库根下的 data/（与 logs/ 同级）；qs_market_data 包位置无关，避免写进包目录
    return Path(__file__).resolve().parents[6] / 'data' / 'sector_constituents.json'


class SectorConstituentCache:
    """sector → [{symbol,name,...}] 的持久化快照（单文件 JSON，进程内加锁）。"""

    def __init__(self, path: Optional[str] = None):
        self._path = Path(path) if path else _default_path()
        self._lock = threading.RLock()

    # ── 读 ─────────────────────────────────────────────────
    def get(self, sector: str) -> Optional[Dict[str, Any]]:
        """读快照：{stocks, source, saved_at, age_sec}；无缓存/读坏返回 None。"""
        key = str(sector or '').strip()
        if not key:
            return None
        with self._lock:
            doc = self._load()
        entry = (doc.get('sectors') or {}).get(key)
        if not isinstance(entry, dict):
            return None
        stocks = entry.get('stocks')
        if not isinstance(stocks, list) or not stocks:
            return None
        saved_at = entry.get('saved_at')
        age = None
        try:
            ts = datetime.fromisoformat(str(saved_at))
            age = max(0.0, (datetime.now() - ts).total_seconds())
        except (TypeError, ValueError):
            pass
        return {
            'sector': key,
            'stocks': stocks,
            'source': entry.get('source') or 'cache',
            'saved_at': saved_at,
            'age_sec': age,
        }

    # ── 写 ─────────────────────────────────────────────────
    def put(self, sector: str, stocks: List[Dict[str, Any]],
            source: str = '') -> bool:
        """存快照（空列表直接拒绝：不以空覆盖已知事实）。返回是否落盘。"""
        key = str(sector or '').strip()
        if not key or not isinstance(stocks, list) or not stocks:
            return False
        with self._lock:
            doc = self._load()
            sectors = doc.setdefault('sectors', {})
            sectors[key] = {
                'stocks': stocks,
                'source': str(source or '')[:40],
                'saved_at': datetime.now().isoformat(timespec='seconds'),
            }
            doc['updated_at'] = datetime.now(timezone.utc).isoformat(
                timespec='seconds')
            return self._save(doc)

    # ── 内部 ───────────────────────────────────────────────
    def _load(self) -> Dict[str, Any]:
        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                doc = json.load(f)
            return doc if isinstance(doc, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception as e:  # noqa: BLE001 - 缓存坏了等同于没有，不阻断取数
            logger.warning('板块成分缓存读取失败（忽略并重建）', path=str(self._path),
                           error=str(e))
            return {}

    def _save(self, doc: Dict[str, Any]) -> bool:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self._path.parent),
                                       prefix='.sector-cache-', suffix='.json')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(doc, f, ensure_ascii=False)
                os.replace(tmp, self._path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            return True
        except Exception as e:  # noqa: BLE001 - 写失败只告警（缓存是增益不是依赖）
            logger.warning('板块成分缓存写入失败（不影响主链路）',
                           path=str(self._path), error=str(e))
            return False


_CACHE: Optional[SectorConstituentCache] = None


def get_sector_constituent_cache() -> SectorConstituentCache:
    """进程级单例（测试可 set_sector_constituent_cache 替换）。"""
    global _CACHE
    if _CACHE is None:
        _CACHE = SectorConstituentCache()
    return _CACHE


def set_sector_constituent_cache(cache: Optional[SectorConstituentCache]) -> None:
    """替换单例（测试/灰度用；传 None 恢复默认，下次取用时重建）。"""
    global _CACHE
    _CACHE = cache
