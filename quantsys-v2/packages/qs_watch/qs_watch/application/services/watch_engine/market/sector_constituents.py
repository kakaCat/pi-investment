"""政策与市场服务共用的板块成分取数适配。"""
from typing import Any, Dict, List

DEFAULT_TTL_SEC = 6 * 3600


def _unwrap(result: Any) -> Any:
    data = result.get('data') if isinstance(result, dict) else getattr(result, 'data', None)
    if data is not None and not isinstance(data, dict):
        data = getattr(data, 'data', None)
    return data


class _ManagerSectorSource:
    def __init__(self, manager):
        self._manager = manager

    def list_sectors(self) -> List[str]:
        data = _unwrap(self._manager.get_sector_list())
        if not isinstance(data, dict):
            raise RuntimeError('板块列表获取失败: %r' % (data,))
        names: List[str] = []
        for key in ('industries', 'concepts'):
            for item in data.get(key) or []:
                name = item.get('name') if isinstance(item, dict) else None
                if name and str(name) not in names:
                    names.append(str(name))
        if not names:
            raise RuntimeError('板块列表为空（数据源异常）')
        return names

    def get_members(self, sector: str) -> List[Dict[str, Any]]:
        data = _unwrap(self._manager.get_sector_stocks(sector))
        if not isinstance(data, dict) or not data.get('found'):
            return []
        return [
            {'symbol': row.get('symbol'), 'name': row.get('name'),
             'market_cap': row.get('market_cap')}
            for row in data.get('stocks') or [] if isinstance(row, dict)
        ]


def _bare_symbol(value: Any) -> str:
    text = str(value or '').strip().upper()
    if not text:
        return ''
    if '.' in text:
        text = text.split('.', 1)[0]
    if len(text) > 6 and text[:2] in ('SH', 'SZ', 'BJ') and text[2:].isdigit():
        text = text[2:]
    return text
