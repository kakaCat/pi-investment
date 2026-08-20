"""
融资融券数据源

获取个股的融资融券数据
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)


class MarginDataSource:
    """融资融券数据源"""

    def __init__(self):
        self.sources = [
            AkShareMarginSource(),
            SimulatedMarginSource(),  # 备用模拟数据
        ]

    def get_margin_data(self, symbol: str, days: int = 5) -> Dict:
        """
        获取融资融券数据

        Args:
            symbol: 股票代码
            days: 查询天数

        Returns:
            {
                'symbol': str,
                'days': int,
                'data': [
                    {
                        'date': str,
                        'financing_balance': float,      # 融资余额(万元)
                        'financing_buy': float,          # 融资买入额(万元)
                        'financing_repay': float,        # 融资偿还额(万元)
                        'margin_balance': float,         # 融券余额(万元)
                        'margin_sell': float,            # 融券卖出量(股)
                        'margin_repay': float,           # 融券偿还量(股)
                        'total_balance': float,          # 融资融券余额(万元)
                    }
                ],
                'summary': {
                    'financing_trend': str,              # 融资趋势
                    'margin_trend': str,                 # 融券趋势
                    'financing_change_rate': float,      # 融资余额变化率
                    'activity_level': str,               # 活跃程度
                },
                'source': str,
                'timestamp': str
            }
        """
        for source in self.sources:
            try:
                logger.info(f"尝试从 {source.name} 获取 {symbol} 融资融券数据")
                data = source.fetch(symbol, days)

                if data and len(data) > 0:
                    summary = self._calculate_summary(data)

                    return {
                        'symbol': symbol,
                        'days': days,
                        'data': data,
                        'summary': summary,
                        'source': source.name,
                        'timestamp': datetime.now().isoformat()
                    }
            except Exception as e:
                logger.warning(f"{source.name} 获取失败: {e}")
                continue

        raise DataSourceError(f"所有数据源获取 {symbol} 融资融券数据失败")

    def _calculate_summary(self, data: List[Dict]) -> Dict:
        """计算汇总信息"""
        if not data or len(data) < 2:
            return {}

        # 最新和最旧的融资余额
        latest = data[0]
        oldest = data[-1]

        latest_financing = latest.get('financing_balance', 0)
        oldest_financing = oldest.get('financing_balance', 1)

        # 融资余额变化率
        financing_change_rate = ((latest_financing - oldest_financing) / oldest_financing * 100
                                if oldest_financing > 0 else 0)

        # 判断融资趋势
        if financing_change_rate > 5:
            financing_trend = 'increasing'
        elif financing_change_rate < -5:
            financing_trend = 'decreasing'
        else:
            financing_trend = 'stable'

        # 融券趋势（简化处理）
        latest_margin = latest.get('margin_balance', 0)
        oldest_margin = oldest.get('margin_balance', 1)
        margin_change_rate = ((latest_margin - oldest_margin) / oldest_margin * 100
                            if oldest_margin > 0 else 0)

        if margin_change_rate > 10:
            margin_trend = 'increasing'
        elif margin_change_rate < -10:
            margin_trend = 'decreasing'
        else:
            margin_trend = 'stable'

        # 活跃程度（基于融资买入额）
        avg_buy = sum(d.get('financing_buy', 0) for d in data) / len(data)
        if avg_buy > 10000:  # 大于1亿
            activity_level = 'high'
        elif avg_buy > 5000:  # 大于5千万
            activity_level = 'medium'
        else:
            activity_level = 'low'

        return {
            'financing_trend': financing_trend,
            'margin_trend': margin_trend,
            'financing_change_rate': round(financing_change_rate, 2),
            'activity_level': activity_level,
        }


class AkShareMarginSource:
    """AkShare 融资融券数据源"""

    name = "akshare"

    def fetch(self, symbol: str, days: int) -> List[Dict]:
        """
        从 AkShare 获取融资融券数据
        """
        import os
        import time
        from contextlib import contextmanager

        @contextmanager
        def _disable_proxies():
            """临时禁用代理的上下文管理器（akshare 对代理支持不好）"""
            proxy_keys = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
            original_proxies = {k: os.environ.get(k) for k in proxy_keys}
            
            try:
                # 临时删除所有代理环境变量
                for key in proxy_keys:
                    if key in os.environ:
                        del os.environ[key]
                yield
            finally:
                # 恢复原始代理设置
                for key, value in original_proxies.items():
                    if value is not None:
                        os.environ[key] = value
                    elif key in os.environ:
                        del os.environ[key]

        try:
            with _disable_proxies():
                import akshare as ak

                stock_code = symbol.replace('.SH', '').replace('.SZ', '')
                logger.info(f"获取 {stock_code} 融资融券数据")

                # 重试机制
                max_retries = 3
                retry_delay = 1

                for attempt in range(max_retries):
                    try:
                        # 使用 akshare 的融资融券接口
                        df = ak.stock_margin_detail_sse(symbol=stock_code)

                        if df is None or df.empty:
                            logger.warning(f"{stock_code} 返回空数据")
                            return []

                        # 只取最近 N 天
                        df = df.head(days)

                        # 转换为标准格式
                        result = []
                        for _, row in df.iterrows():
                            result.append({
                                'date': str(row.get('日期', '')),
                                'financing_balance': float(row.get('融资余额', 0)) / 10000,  # 元转万元
                                'financing_buy': float(row.get('融资买入额', 0)) / 10000,
                                'financing_repay': float(row.get('融资偿还额', 0)) / 10000,
                                'margin_balance': float(row.get('融券余额', 0)) / 10000,
                                'margin_sell': float(row.get('融券卖出量', 0)),
                                'margin_repay': float(row.get('融券偿还量', 0)),
                                'total_balance': float(row.get('融资融券余额', 0)) / 10000,
                            })

                        logger.info(f"成功获取 {stock_code} 融资融券数据，共 {len(result)} 条")
                        return result

                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"获取失败（尝试 {attempt + 1}/{max_retries}），{retry_delay}秒后重试: {e}")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                        else:
                            raise

        except Exception as e:
            logger.error(f"AkShare 融资融券数据源获取失败: {e}")
            raise


class SimulatedMarginSource:
    """模拟融资融券数据源（备用）"""

    name = "simulated"

    def fetch(self, symbol: str, days: int) -> List[Dict]:
        """
        返回模拟数据
        """
        logger.warning(f"使用模拟数据作为 {symbol} 融资融券备用方案")

        result = []
        base_date = datetime.now()

        # 生成模拟数据
        base_financing = 50000  # 基础融资余额5亿
        base_margin = 5000      # 基础融券余额5千万

        for i in range(days):
            date = (base_date - timedelta(days=i)).strftime('%Y-%m-%d')

            # 随机波动
            financing_balance = base_financing * (1 + random.uniform(-0.05, 0.05))
            financing_buy = financing_balance * random.uniform(0.01, 0.05)
            financing_repay = financing_balance * random.uniform(0.01, 0.04)

            margin_balance = base_margin * (1 + random.uniform(-0.1, 0.1))
            margin_sell = margin_balance * random.uniform(0.05, 0.15)
            margin_repay = margin_balance * random.uniform(0.03, 0.12)

            result.append({
                'date': date,
                'financing_balance': round(financing_balance, 2),
                'financing_buy': round(financing_buy, 2),
                'financing_repay': round(financing_repay, 2),
                'margin_balance': round(margin_balance, 2),
                'margin_sell': round(margin_sell, 2),
                'margin_repay': round(margin_repay, 2),
                'total_balance': round(financing_balance + margin_balance, 2),
            })

        return result


class DataSourceError(Exception):
    """数据源错误"""
    pass
