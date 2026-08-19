"""
多数据源数据获取器 - 用于V14交易系统

支持多个数据源的自动failover：
1. 新浪财经（不需要代理，速度快）
2. AKShare（备用）
3. Tushare（如果配置了token）

当一个数据源失败时，自动尝试下一个
"""
import os
import logging
import pandas as pd
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class DataSource:
    """数据源基类"""

    def __init__(self, name: str):
        self.name = name
        self.success_count = 0
        self.failure_count = 0

    def fetch_stock_list(self) -> Optional[pd.DataFrame]:
        """获取股票列表"""
        raise NotImplementedError()

    def fetch_klines(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """获取K线数据"""
        raise NotImplementedError()

    def record_success(self):
        self.success_count += 1

    def record_failure(self):
        self.failure_count += 1


class SinaSource(DataSource):
    """新浪财经数据源（不需要代理）"""

    def __init__(self):
        super().__init__("Sina")

    def fetch_stock_list(self) -> Optional[pd.DataFrame]:
        """获取股票列表（Sina 接口已不维护，返回 None）"""
        try:
            logger.info(f"[{self.name}] 获取股票列表...")
            
            # 新浪股票列表接口已不稳定，且 DataProviderManager 不支持全量列表
            # 返回 None，让上层 failover 到其他源
            logger.warning(f"[{self.name}] Sina 全量股票列表接口已废弃，跳过")
            self.record_failure()
            return None

        except Exception as e:
            logger.warning(f"[{self.name}] 获取股票列表失败: {e}")
            self.record_failure()
            return None

    def fetch_klines(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """获取K线数据 - 直接使用requests获取新浪数据"""
        try:
            import requests
            import json as json_lib
            from datetime import datetime, timedelta

            clean_symbol = symbol.split('.')[0]
            logger.info(f"[{self.name}] 获取 {clean_symbol} K线数据...")

            # 确定市场代码
            if clean_symbol.startswith('6'):
                market = 'sh'
            elif clean_symbol.startswith(('0', '3')):
                market = 'sz'
            else:
                logger.warning(f"[{self.name}] 无法识别市场代码")
                return None

            # 新浪财经历史数据API
            sina_symbol = f'{market}{clean_symbol}'
            url = f'http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={sina_symbol}&scale=240&ma=no&datalen=100'

            # 不使用代理
            session = requests.Session()
            session.trust_env = False

            response = session.get(url, timeout=10)

            if response.status_code != 200:
                logger.warning(f"[{self.name}] HTTP状态码: {response.status_code}")
                return None

            data = json_lib.loads(response.text)

            if not data or len(data) == 0:
                logger.warning(f"[{self.name}] 返回数据为空")
                return None

            # 转换为DataFrame
            df = pd.DataFrame(data)

            # 列名映射
            df = df.rename(columns={
                'day': '日期',
                'open': '开盘',
                'high': '最高',
                'low': '最低',
                'close': '收盘',
                'volume': '成交量'
            })

            # 转换数据类型
            for col in ['开盘', '最高', '最低', '收盘']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df['成交量'] = pd.to_numeric(df['成交量'], errors='coerce')

            # 过滤日期范围
            df['日期'] = pd.to_datetime(df['日期'])
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            df = df[(df['日期'] >= start_dt) & (df['日期'] <= end_dt)]
            df['日期'] = df['日期'].dt.strftime('%Y-%m-%d')

            if df.empty:
                logger.warning(f"[{self.name}] 过滤后数据为空")
                return None

            logger.info(f"[{self.name}] 成功获取 {len(df)} 条K线")
            self.record_success()
            return df

        except Exception as e:
            logger.warning(f"[{self.name}] 获取K线失败: {e}")
            self.record_failure()
            return None


class LocalDatabaseSource(DataSource):
    """本地数据库数据源（最快，但需要有缓存数据）"""

    def __init__(self):
        super().__init__("LocalDB")

    def fetch_stock_list(self) -> Optional[pd.DataFrame]:
        """从本地数据库获取股票列表"""
        try:
            from application.services.data_service import DataService

            logger.info(f"[{self.name}] 从本地数据库获取股票列表...")
            ds = DataService()

            # 这里需要调用DataService的方法获取股票列表
            # 简化版本：直接返回None，让它fallback到其他数据源
            logger.info(f"[{self.name}] 本地数据库暂不支持股票列表")
            return None

        except Exception as e:
            logger.warning(f"[{self.name}] 从本地数据库获取失败: {e}")
            self.record_failure()
            return None

    def fetch_klines(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """从本地数据库获取K线数据"""
        try:
            from application.services.data_service import DataService

            logger.info(f"[{self.name}] 从本地数据库获取 {symbol} K线...")
            ds = DataService()

            klines_df = ds.kline.get_daily_klines(symbol, start_date, end_date)

            if klines_df is None or klines_df.is_empty():
                logger.warning(f"[{self.name}] 本地无缓存数据")
                return None

            # 转换为pandas DataFrame
            df = klines_df.to_pandas()

            logger.info(f"[{self.name}] 从本地数据库获取 {len(df)} 条K线")
            self.record_success()
            return df

        except Exception as e:
            logger.warning(f"[{self.name}] 从本地数据库获取失败: {e}")
            self.record_failure()
            return None


class AKShareSource(DataSource):
    """AKShare数据源（委托 DataProviderManager）"""

    def __init__(self):
        super().__init__("AKShare")
        self._manager = None

    def _get_manager(self):
        """延迟加载 DataProviderManager"""
        if self._manager is None:
            from adapters.outbound.datasources import get_data_provider_manager
            self._manager = get_data_provider_manager()
        return self._manager

    def fetch_stock_list(self) -> Optional[pd.DataFrame]:
        """获取股票列表（通过 manager.get_quote 批量）"""
        try:
            logger.info(f"[{self.name}] 获取股票列表...")
            
            # DataProviderManager 不提供全量股票列表接口
            # 此处返回 None，让上层 failover 到其他源
            logger.warning(f"[{self.name}] DataProviderManager 不支持全量股票列表，跳过")
            self.record_failure()
            return None

        except Exception as e:
            logger.warning(f"[{self.name}] 获取股票列表失败: {e}")
            self.record_failure()
            return None

    def fetch_klines(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """获取K线数据（委托 DataProviderManager）"""
        try:
            manager = self._get_manager()
            
            logger.info(f"[{self.name}] 通过 DataProviderManager 获取 {symbol} K线数据...")
            
            result = manager.get_klines(symbol, 'daily', start_date, end_date)
            
            if not result.get('success'):
                logger.warning(f"[{self.name}] K线数据获取失败: {result.get('error')}")
                self.record_failure()
                return None
            
            klines_data = result['data']
            if not klines_data:
                logger.warning(f"[{self.name}] K线数据为空")
                self.record_failure()
                return None
            
            # 转换为 DataFrame（与 akshare 格式兼容）
            rows = []
            for kline in klines_data:
                rows.append({
                    '日期': kline.timestamp.strftime('%Y-%m-%d') if hasattr(kline.timestamp, 'strftime') else str(kline.timestamp),
                    '开盘': kline.open,
                    '最高': kline.high,
                    '最低': kline.low,
                    '收盘': kline.close,
                    '成交量': kline.volume,
                    '成交额': kline.turnover if kline.turnover else 0,
                })
            
            df = pd.DataFrame(rows)
            
            logger.info(f"[{self.name}] 成功获取 {len(df)} 条K线")
            self.record_success()
            return df

        except Exception as e:
            logger.warning(f"[{self.name}] 获取K线失败: {e}")
            self.record_failure()
            return None


class MultiSourceDataFetcher:
    """多数据源数据获取器"""

    def __init__(self):
        # 按优先级排序：本地数据库 > 新浪 > AKShare
        self.sources: List[DataSource] = [
            LocalDatabaseSource(),
            SinaSource(),
            AKShareSource(),
        ]

        logger.info(f"多数据源获取器初始化完成，支持 {len(self.sources)} 个数据源")

    def fetch_stock_list(self) -> Optional[pd.DataFrame]:
        """
        使用多数据源failover获取股票列表

        Returns:
            DataFrame或None
        """
        for source in self.sources:
            try:
                df = source.fetch_stock_list()
                if df is not None and not df.empty:
                    logger.info(f"✓ 使用 {source.name} 成功获取股票列表")
                    return df
            except Exception as e:
                logger.warning(f"✗ {source.name} 异常: {e}")
                continue

        logger.error("❌ 所有数据源均失败，无法获取股票列表")
        return None

    def fetch_klines(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """
        使用多数据源failover获取K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            DataFrame或None
        """
        for source in self.sources:
            try:
                df = source.fetch_klines(symbol, start_date, end_date)
                if df is not None and not df.empty:
                    logger.info(f"✓ 使用 {source.name} 成功获取 {symbol} K线数据")
                    return df
            except Exception as e:
                logger.warning(f"✗ {source.name} 异常: {e}")
                continue

        logger.error(f"❌ 所有数据源均失败，无法获取 {symbol} K线数据")
        return None

    def fetch_multiple_stocks(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        max_failures: int = 10
    ) -> dict:
        """
        批量获取多只股票的K线数据

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            max_failures: 最大失败数，超过则停止

        Returns:
            {symbol: DataFrame} 字典
        """
        results = {}
        failures = 0

        for i, symbol in enumerate(symbols):
            logger.info(f"获取股票 {i+1}/{len(symbols)}: {symbol}")

            df = self.fetch_klines(symbol, start_date, end_date)

            if df is not None:
                results[symbol] = df
            else:
                failures += 1
                if failures >= max_failures:
                    logger.error(f"失败次数达到 {max_failures}，停止批量获取")
                    break

        logger.info(f"批量获取完成: 成功 {len(results)}/{len(symbols)} 只股票")
        return results

    def get_health_report(self) -> dict:
        """获取各数据源健康报告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'sources': []
        }

        for source in self.sources:
            total = source.success_count + source.failure_count
            success_rate = source.success_count / total if total > 0 else 0

            report['sources'].append({
                'name': source.name,
                'success_count': source.success_count,
                'failure_count': source.failure_count,
                'success_rate': f"{success_rate:.1%}"
            })

        return report


if __name__ == '__main__':
    # 测试多数据源获取器
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    fetcher = MultiSourceDataFetcher()

    # 测试获取股票列表
    print("\n" + "="*70)
    print("测试1: 获取股票列表")
    print("="*70)
    stock_list = fetcher.fetch_stock_list()
    if stock_list is not None:
        print(f"✓ 成功获取 {len(stock_list)} 只股票")
        print(stock_list.head(3))
    else:
        print("✗ 获取失败")

    # 测试获取K线数据
    print("\n" + "="*70)
    print("测试2: 获取K线数据")
    print("="*70)
    klines = fetcher.fetch_klines('000001', '2026-07-01', '2026-07-17')
    if klines is not None:
        print(f"✓ 成功获取 {len(klines)} 条K线")
        print(klines.tail(3))
    else:
        print("✗ 获取失败")

    # 健康报告
    print("\n" + "="*70)
    print("数据源健康报告")
    print("="*70)
    report = fetcher.get_health_report()
    import json
    print(json.dumps(report, indent=2, ensure_ascii=False))
