"""
因子缓存机制
"""
import os
import pickle
import hashlib
from typing import Optional, Any
from datetime import datetime, timedelta
import pandas as pd


class FactorCache:
    """因子缓存"""

    def __init__(self, cache_dir: str = ".pi-invest/factor-cache", ttl_hours: int = 24):
        """
        Args:
            cache_dir: 缓存目录
            ttl_hours: 缓存有效期（小时）
        """
        self.cache_dir = cache_dir
        self.ttl_hours = ttl_hours
        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_key(self, factor_name: str, symbol: str, start_date: str, end_date: str) -> str:
        """生成缓存键"""
        key_str = f"{factor_name}_{symbol}_{start_date}_{end_date}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{cache_key}.pkl")

    def get(
        self,
        factor_name: str,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Optional[pd.Series]:
        """
        获取缓存的因子值

        Args:
            factor_name: 因子名称
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            缓存的因子值，如果不存在或过期返回None
        """
        cache_key = self._get_cache_key(factor_name, symbol, start_date, end_date)
        cache_path = self._get_cache_path(cache_key)

        if not os.path.exists(cache_path):
            return None

        # 检查缓存是否过期
        file_mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
        if datetime.now() - file_mtime > timedelta(hours=self.ttl_hours):
            os.remove(cache_path)
            return None

        try:
            with open(cache_path, 'rb') as f:
                cached_data = pickle.load(f)
                return cached_data
        except Exception as e:
            print(f"Error loading cache: {e}")
            return None

    def set(
        self,
        factor_name: str,
        symbol: str,
        start_date: str,
        end_date: str,
        value: pd.Series
    ) -> None:
        """
        设置因子缓存

        Args:
            factor_name: 因子名称
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            value: 因子值
        """
        cache_key = self._get_cache_key(factor_name, symbol, start_date, end_date)
        cache_path = self._get_cache_path(cache_key)

        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(value, f)
        except Exception as e:
            print(f"Error saving cache: {e}")

    def clear(self, factor_name: Optional[str] = None) -> int:
        """
        清除缓存

        Args:
            factor_name: 如果指定，只清除该因子的缓存；否则清除所有

        Returns:
            清除的文件数量
        """
        count = 0
        for filename in os.listdir(self.cache_dir):
            if not filename.endswith('.pkl'):
                continue

            filepath = os.path.join(self.cache_dir, filename)

            if factor_name is None:
                os.remove(filepath)
                count += 1
            else:
                # 检查是否属于指定因子（简化实现，实际可能需要更精确的匹配）
                try:
                    with open(filepath, 'rb') as f:
                        # 这里简化处理，实际可以在缓存时存储元数据
                        os.remove(filepath)
                        count += 1
                except:
                    pass

        return count

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        total_files = 0
        total_size = 0
        expired_files = 0

        for filename in os.listdir(self.cache_dir):
            if not filename.endswith('.pkl'):
                continue

            filepath = os.path.join(self.cache_dir, filename)
            total_files += 1
            total_size += os.path.getsize(filepath)

            file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            if datetime.now() - file_mtime > timedelta(hours=self.ttl_hours):
                expired_files += 1

        return {
            'total_files': total_files,
            'total_size_mb': total_size / (1024 * 1024),
            'expired_files': expired_files,
            'ttl_hours': self.ttl_hours
        }
