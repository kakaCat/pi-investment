"""
简单文件缓存工具

用于缓存慢速数据源的响应，提高用户体验
"""
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SimpleCache:
    """简单的文件缓存实现"""

    def __init__(self, cache_dir: str = ".cache"):
        """
        初始化缓存

        Args:
            cache_dir: 缓存目录，相对于项目根目录
        """
        # 获取项目根目录
        project_root = Path(__file__).parent.parent
        self.cache_dir = project_root / cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def get(self, key: str, max_age_seconds: int = 3600) -> Optional[Dict[str, Any]]:
        """
        获取缓存数据

        Args:
            key: 缓存键
            max_age_seconds: 最大有效期（秒），默认1小时

        Returns:
            缓存的数据，如果不存在或过期则返回 None
        """
        cache_file = self.cache_dir / f"{key}.json"

        if not cache_file.exists():
            self.logger.debug(f"缓存未命中: {key}")
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)

            # 检查缓存时间
            cached_at = datetime.fromisoformat(cached.get('cached_at'))
            age = (datetime.now() - cached_at).total_seconds()

            if age > max_age_seconds:
                self.logger.debug(f"缓存过期: {key} (age={age:.0f}s)")
                return None

            self.logger.info(f"缓存命中: {key} (age={age:.0f}s)")
            return cached.get('data')

        except Exception as e:
            self.logger.warning(f"读取缓存失败: {key}, {e}")
            return None

    def get_stale(self, key: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存数据（忽略过期时间）

        用于降级场景：数据源不可用时返回旧缓存

        Args:
            key: 缓存键

        Returns:
            缓存的数据及元信息
        """
        cache_file = self.cache_dir / f"{key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)

            cached_at = datetime.fromisoformat(cached.get('cached_at'))
            age = (datetime.now() - cached_at).total_seconds()

            self.logger.info(f"使用旧缓存: {key} (age={age:.0f}s)")

            # 返回数据并标记为 stale
            data = cached.get('data')
            if isinstance(data, dict):
                data['_cache_stale'] = True
                data['_cache_age_seconds'] = int(age)
                data['_cache_timestamp'] = cached.get('cached_at')

            return data

        except Exception as e:
            self.logger.warning(f"读取旧缓存失败: {key}, {e}")
            return None

    def set(self, key: str, data: Dict[str, Any]) -> bool:
        """
        设置缓存数据

        Args:
            key: 缓存键
            data: 要缓存的数据

        Returns:
            是否成功
        """
        cache_file = self.cache_dir / f"{key}.json"

        try:
            cached = {
                'cached_at': datetime.now().isoformat(),
                'data': data
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cached, f, ensure_ascii=False, indent=2)

            self.logger.info(f"缓存已更新: {key}")
            return True

        except Exception as e:
            self.logger.error(f"写入缓存失败: {key}, {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        删除缓存

        Args:
            key: 缓存键

        Returns:
            是否成功
        """
        cache_file = self.cache_dir / f"{key}.json"

        try:
            if cache_file.exists():
                cache_file.unlink()
                self.logger.info(f"缓存已删除: {key}")
            return True

        except Exception as e:
            self.logger.error(f"删除缓存失败: {key}, {e}")
            return False

    def clear_all(self) -> int:
        """
        清空所有缓存

        Returns:
            删除的文件数
        """
        count = 0
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
                count += 1
            self.logger.info(f"已清空所有缓存: {count} 个文件")
            return count

        except Exception as e:
            self.logger.error(f"清空缓存失败: {e}")
            return count
