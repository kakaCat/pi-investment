"""博弈告警去重状态：文件持久化 + 同机跨进程原子 observe。

状态只保存内容指纹与首末次观察时间，不保存交易指令。锁文件与 JSON 均位于
quantsys-v2/data（运行时目录，已被 git 忽略）。损坏/不可写必须抛错，不能重置后
伪装成“从未告警”。
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, Optional, Tuple


class FileGameAlertStateStore:
    persistence = 'file_atomic'
    restart_safe = True

    def __init__(self, path: Optional[str] = None):
        default = Path(__file__).resolve().parents[3] / 'data' / 'game-alert-state.json'
        self.path = Path(path or os.getenv('GAME_ALERT_STATE_PATH') or default)
        self.lock_path = self.path.with_suffix(self.path.suffix + '.lock')
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_unlocked(self) -> Dict[str, Dict[str, Any]]:
        if not self.path.exists():
            return {}
        with self.path.open('r', encoding='utf-8') as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f'告警去重状态必须是 object: {self.path}')
        return data

    def _write_unlocked(self, data: Dict[str, Dict[str, Any]]) -> None:
        # 最多保留 2000 个内容键，优先淘汰最久未观察者；不产生无界运行文件。
        if len(data) > 2000:
            keep = sorted(data.items(), key=lambda row: str(row[1].get('last_seen_at', '')))[-2000:]
            data = dict(keep)
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', dir=self.path.parent,
                prefix=self.path.name + '.', suffix='.tmp', delete=False,
            ) as handle:
                tmp_name = handle.name
                json.dump(data, handle, ensure_ascii=False, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
            tmp_name = None
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def observe(self, key: str, fingerprint: str, observed_at: str,
               ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """同一把排他文件锁内完成读→判重→写，避免多 worker 同时判为首次。"""
        with self.lock_path.open('a+', encoding='utf-8') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                data = self._read_unlocked()
                previous = data.get(key)
                unchanged = bool(previous and previous.get('fingerprint') == fingerprint)
                first_seen_at = (
                    str(previous.get('first_seen_at'))
                    if unchanged and previous.get('first_seen_at') else observed_at
                )
                data[key] = {
                    'fingerprint': fingerprint,
                    'first_seen_at': first_seen_at,
                    'last_seen_at': observed_at,
                }
                self._write_unlocked(data)
                return dict(previous) if previous else None, unchanged
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
