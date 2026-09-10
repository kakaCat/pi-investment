"""
融资融券数据源

获取个股的融资融券数据
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import random

from domain.ports.datasource_ports import DataSourceError

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
    """AkShare 融资融券数据源

    2026-09-11（w-8f2c4cc5）：akshare 1.18.x 的 stock_margin_detail_sse/szse/bse 均为
    「按日期取全市场明细」，不接受 symbol 关键字——旧调用
    ak.stock_margin_detail_sse(symbol=stock_code) 直接 TypeError（board 事件 3cef6bef）。
    现改为：按代码前缀选市场接口 → 逐交易日回溯（跳周末/未发布日）→ 按证券代码过滤该股行。
    注意沪市明细（sse）无「融券余额」列，此时 margin_balance 记 0 并以 has_margin_balance=False 标注。
    """

    name = "akshare"

    # A 股代码前缀 → akshare 明细接口市场后缀
    _MARKET_PREFIXES = (('6', 'sse'), ('0', 'szse'), ('3', 'szse'), ('4', 'bse'), ('8', 'bse'))

    @classmethod
    def _market_for(cls, code: str) -> Optional[str]:
        """按 6 位代码前缀判定市场（沪/深/北）。"""
        for prefix, market in cls._MARKET_PREFIXES:
            if code.startswith(prefix):
                return market
        return None

    @staticmethod
    def _candidate_dates(days: int) -> List[str]:
        """从今天往前生成候选交易日（YYYYMMDD，跳过周末），多取缓冲以覆盖节假日与未发布日。"""
        dates: List[str] = []
        cursor = datetime.now()
        for _ in range(days * 3 + 12):
            if cursor.weekday() < 5:
                dates.append(cursor.strftime('%Y%m%d'))
            cursor -= timedelta(days=1)
            if len(dates) >= days + 6:
                break
        return dates

    @staticmethod
    def _match_row(df, code: str):
        """在当日全市场明细中定位该股行（沪市列名为标的证券代码，深/北为证券代码）。"""
        for col in ('标的证券代码', '证券代码'):
            if col in df.columns:
                hit = df[df[col].astype(str).str.zfill(6) == code]
                if len(hit):
                    return hit.iloc[0]
        return None

    @staticmethod
    def _to_float(value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _to_standard(cls, row, date_str: str) -> Dict:
        """把 akshare 明细行归一为既有字段口径（金额元 → 万元，量保持股）。"""
        raw_date = str(row.get('信用交易日期') or row.get('日期') or date_str).replace('-', '')[:8]
        date_out = raw_date[:4] + "-" + raw_date[4:6] + "-" + raw_date[6:8] if len(raw_date) == 8 else str(raw_date)
        financing_balance = cls._to_float(row.get('融资余额', 0))
        has_margin_balance = '融券余额' in getattr(row, 'index', [])
        margin_balance = cls._to_float(row.get('融券余额', 0)) if has_margin_balance else 0.0
        total_balance = cls._to_float(row.get('融资融券余额', 0)) or (financing_balance + margin_balance)
        return {
            'date': date_out,
            'financing_balance': financing_balance / 10000,  # 元转万元
            'financing_buy': cls._to_float(row.get('融资买入额', 0)) / 10000,
            'financing_repay': cls._to_float(row.get('融资偿还额', 0)) / 10000,
            'margin_balance': margin_balance / 10000,
            'has_margin_balance': has_margin_balance,  # False=该市场明细未提供融券余额（非真实 0）
            'margin_sell': cls._to_float(row.get('融券卖出量', 0)),
            'margin_repay': cls._to_float(row.get('融券偿还量', 0)),
            'total_balance': total_balance / 10000,
        }

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

                stock_code = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '').strip()
                logger.info(f"获取 {stock_code} 融资融券数据")

                market = self._market_for(stock_code)
                if market is None:
                    raise DataSourceError(f"无法识别 {stock_code} 所属市场（仅支持沪/深/北交所标的）")
                fetch_detail = getattr(ak, f"stock_margin_detail_{market}", None)
                if fetch_detail is None:
                    raise DataSourceError(f"当前 akshare 无 stock_margin_detail_{market} 接口")

                # 重试机制（按交易日逐日回溯，单日失败降级为跳过，连续失败则判数据源不可用）
                max_retries = 3
                retry_delay = 1

                result: List[Dict] = []
                consecutive_failures = 0
                candidate_dates = self._candidate_dates(days)
                for date_str in candidate_dates:
                    if len(result) >= days:
                        break
                    df = None
                    for attempt in range(max_retries):
                        try:
                            df = fetch_detail(date=date_str)
                            consecutive_failures = 0
                            break
                        except Exception as e:
                            if isinstance(e, ValueError) and 'Length mismatch' in str(e):
                                # akshare 对「当日尚未发布」的沪市明细会抛该 ValueError（空 payload 仍按 13 列建轴）——
                                # 属正常无数据，直接跳过该日，不做无谓重试
                                logger.info(f"{date_str} 无融资融券明细（akshare 空返回），跳过")
                                break
                            if attempt < max_retries - 1:
                                logger.warning(f"{date_str} 明细获取失败（尝试 {attempt + 1}/{max_retries}），{retry_delay}秒后重试: {e}")
                                time.sleep(retry_delay)
                                retry_delay *= 2
                            else:
                                logger.warning(f"{date_str} 融资融券明细获取失败，跳过该日: {e}")
                                consecutive_failures += 1
                    if consecutive_failures >= 3:
                        raise DataSourceError(f"{stock_code} 连续 3 个交易日获取失败（最近 {date_str}），疑似数据源不可用")
                    if df is None or df.empty:
                        continue
                    row = self._match_row(df, stock_code)
                    if row is None:
                        continue
                    result.append(self._to_standard(row, date_str))

                if result:
                    logger.info(f"成功获取 {stock_code} 融资融券数据，共 {len(result)} 条（{result[0]['date']} .. {result[-1]['date']}，市场 {market}）")
                else:
                    logger.warning(f"{stock_code} 近期无融资融券明细（市场 {market}，已回溯 {len(candidate_dates)} 个交易日）")
                return result

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


# DataSourceError 已归一至 domain/ports/datasource_ports.py（2026-09-10），此处不再重复定义
