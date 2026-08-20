"""
资金流向数据源

数据源：东方财富（唯一真实源）

⚠️ 历史上曾有 AkShareFundFlowSource 备用源用 random.uniform 生成模拟资金流
还标记 source: 'api'，污染下游所有资金分析，已于 2026-07-28 删除。
主源失败时必须显式报错，绝不返回假数据。
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)


class FundFlowDataSource:
    """资金流向数据源 - 东方财富 + 本地缓存"""

    def __init__(self):
        self.sources = [
            EastMoneyFundFlowSource(),
        ]
        # 新增：本地缓存 Repository
        try:
            from adapters.outbound.repositories import FundFlowORMRepository
            self.repository = FundFlowORMRepository()
            self.cache_enabled = True
            self.cache_ttl_hours = 24  # 缓存有效期
        except Exception as e:
            logger.warning(f"缓存 Repository 初始化失败，禁用缓存: {e}")
            self.repository = None
            self.cache_enabled = False

    def get_stock_fund_flow(self, symbol: str, days: int = 5) -> Dict:
        """
        获取个股资金流向（优先本地缓存）

        Args:
            symbol: 股票代码
            days: 查询天数

        Returns:
            {
                'symbol': str,
                'name': str,
                'days': int,
                'data': [...],
                'summary': {...},
                'source': str,  # 'cache' | 'api' | 'stale_cache'
                'timestamp': str
            }
        """
        # 标准化股票代码（去除后缀）
        clean_symbol = symbol.split('.')[0]

        # 1. 尝试从缓存查询
        if self.cache_enabled and self.repository:
            try:
                cached_data = self.repository.get_latest_fund_flow(clean_symbol, days)

                if self._is_cache_valid(cached_data, days):
                    logger.info(f"命中本地缓存: {symbol}")
                    return self._format_cache_response(cached_data, clean_symbol, 'cache')
            except Exception as e:
                logger.warning(f"缓存查询失败: {e}")

        # 2. 缓存 miss，从 API 获取
        logger.info(f"缓存 miss，调用 API: {symbol}")
        try:
            for source in self.sources:
                try:
                    logger.info(f"尝试从 {source.name} 获取 {clean_symbol} 资金流向数据")
                    data = source.fetch(clean_symbol, days)

                    if data and len(data) > 0:
                        # 3. 写入缓存
                        if self.cache_enabled and self.repository:
                            try:
                                self._save_to_cache(clean_symbol, data, source.name)
                            except Exception as e:
                                logger.warning(f"缓存写入失败: {e}")

                        # 计算汇总信息
                        summary = self._calculate_summary(data)

                        return {
                            'symbol': clean_symbol,
                            'days': days,
                            'data': data,
                            'summary': summary,
                            'source': 'api',
                            'timestamp': datetime.now().isoformat()
                        }
                except Exception as e:
                    logger.warning(f"{source.name} 获取失败: {e}")
                    continue

            raise DataSourceError(f"所有数据源获取 {clean_symbol} 资金流向失败")

        except Exception as e:
            # 4. API 失败，降级使用旧缓存
            if self.cache_enabled and self.repository:
                logger.warning(f"API 调用失败，尝试使用旧缓存: {e}")
                try:
                    fallback_data = self.repository.get_latest_fund_flow(clean_symbol, days=30)
                    if fallback_data:
                        logger.info(f"使用旧缓存数据: {symbol}")
                        return self._format_cache_response(fallback_data, clean_symbol, 'stale_cache')
                except Exception as cache_err:
                    logger.error(f"旧缓存查询失败: {cache_err}")
            raise

    def _is_cache_valid(self, cached_data: List[Dict], days: int) -> bool:
        """
        判断缓存是否有效

        条件：
        1. 数据条数 >= max(1, days - 3)（考虑周末节假日）
        2. 最新数据的 updated_at < 24 小时
        """
        if not cached_data:
            return False

        # 检查数据量（容忍周末节假日缺失）
        min_expected = max(1, days - 3)
        if len(cached_data) < min_expected:
            return False

        # 检查最新数据的更新时间
        latest = cached_data[0]  # 降序排列，第一条是最新
        updated_at = latest.get('updated_at')
        if not updated_at:
            return False

        age_hours = (datetime.now() - updated_at).total_seconds() / 3600

        return age_hours < self.cache_ttl_hours

    def _format_cache_response(self, cached_data: List[Dict], symbol: str, source: str) -> Dict:
        """格式化缓存数据为标准响应"""
        # 转换缓存数据为标准格式
        formatted_data = []
        for item in cached_data:
            formatted_data.append({
                'date': item['trade_date'].strftime('%Y-%m-%d') if hasattr(item['trade_date'], 'strftime') else str(item['trade_date']),
                'close_price': float(item.get('close_price', 0)) if item.get('close_price') else None,
                'change_pct': float(item.get('change_pct', 0)) if item.get('change_pct') else None,
                'main_net_inflow': float(item.get('main_net_inflow', 0)),
                'main_net_inflow_rate': float(item.get('main_net_inflow_rate', 0)),
                'large_net_inflow': float(item.get('large_net_inflow', 0)),
                'large_net_inflow_rate': float(item.get('large_net_inflow_rate', 0)),
                'big_net_inflow': float(item.get('big_net_inflow', 0)),
                'big_net_inflow_rate': float(item.get('big_net_inflow_rate', 0)),
                'medium_net_inflow': float(item.get('medium_net_inflow', 0)),
                'medium_net_inflow_rate': float(item.get('medium_net_inflow_rate', 0)),
                'small_net_inflow': float(item.get('small_net_inflow', 0)),
                'small_net_inflow_rate': float(item.get('small_net_inflow_rate', 0)),
            })

        summary = self._calculate_summary(formatted_data)

        return {
            'symbol': symbol,
            'days': len(formatted_data),
            'data': formatted_data,
            'summary': summary,
            'source': source,
            'timestamp': datetime.now().isoformat()
        }

    def _save_to_cache(self, symbol: str, data: List[Dict], source: str):
        """保存数据到缓存"""
        records = []
        for item in data:
            records.append({
                'symbol': symbol,
                'trade_date': item.get('date', ''),
                'close_price': item.get('close_price'),
                'change_pct': item.get('change_pct'),
                'main_net_inflow': item.get('main_net_inflow'),
                'main_net_inflow_rate': item.get('main_net_inflow_rate'),
                'large_net_inflow': item.get('large_net_inflow'),
                'large_net_inflow_rate': item.get('large_net_inflow_rate'),
                'big_net_inflow': item.get('big_net_inflow'),
                'big_net_inflow_rate': item.get('big_net_inflow_rate'),
                'medium_net_inflow': item.get('medium_net_inflow'),
                'medium_net_inflow_rate': item.get('medium_net_inflow_rate'),
                'small_net_inflow': item.get('small_net_inflow'),
                'small_net_inflow_rate': item.get('small_net_inflow_rate'),
                'source': source
            })

        count = self.repository.batch_upsert(records)
        logger.info(f"已缓存 {symbol} 资金流数据: {count} 条")

    def _calculate_summary(self, data: List[Dict]) -> Dict:
        """计算汇总统计信息"""
        if not data:
            return {}

        # 累计主力净流入
        total_main_net_inflow = sum(d.get('main_net_inflow', 0) for d in data)

        # 平均主力净流入率
        rates = [d.get('main_net_inflow_rate', 0) for d in data if d.get('main_net_inflow_rate') is not None]
        avg_main_net_inflow_rate = sum(rates) / len(rates) if rates else 0

        # 连续净流入天数（从最近一天往前数）
        consecutive_inflow_days = 0
        for d in reversed(data):
            if d.get('main_net_inflow', 0) > 0:
                consecutive_inflow_days += 1
            else:
                break

        # 趋势判断
        if consecutive_inflow_days >= 3:
            trend = 'strong_inflow'
        elif consecutive_inflow_days >= 1:
            trend = 'inflow'
        elif total_main_net_inflow > 0:
            trend = 'weak_inflow'
        elif total_main_net_inflow < 0:
            trend = 'outflow'
        else:
            trend = 'neutral'

        return {
            'total_main_net_inflow': round(total_main_net_inflow, 2),
            'avg_main_net_inflow_rate': round(avg_main_net_inflow_rate, 2),
            'consecutive_inflow_days': consecutive_inflow_days,
            'trend': trend,
        }


class EastMoneyFundFlowSource:
    """东方财富资金流向数据源"""

    name = "eastmoney"

    def fetch(self, symbol: str, days: int) -> List[Dict]:
        """
        从东方财富获取资金流向数据

        使用 akshare 的 stock_individual_fund_flow 接口
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

                # 东方财富接口需要纯数字代码
                stock_code = symbol.replace('.SH', '').replace('.SZ', '')

                # 根据股票代码前缀确定市场（akshare 默认 sh，必须显式传参）
                if stock_code.startswith('60') or stock_code.startswith('68'):
                    market = 'sh'
                elif stock_code.startswith('8'):
                    market = 'bj'
                else:  # 00, 30 → 深交所
                    market = 'sz'

                logger.info(f"获取 {stock_code} 资金流向数据（market={market}，禁用代理）")

                # 重试机制：最多尝试3次
                max_retries = 3
                retry_delay = 1  # 秒

                for attempt in range(max_retries):
                    try:
                        df = ak.stock_individual_fund_flow(stock=stock_code, market=market)

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
                                'close_price': float(row.get('收盘价', 0)),
                                'change_pct': float(row.get('涨跌幅', 0)),
                                'main_net_inflow': float(row.get('主力净流入-净额', 0)) / 10000,  # 元转万元
                                'main_net_inflow_rate': float(row.get('主力净流入-净占比', 0)),
                                'large_net_inflow': float(row.get('超大单净流入-净额', 0)) / 10000,
                                'large_net_inflow_rate': float(row.get('超大单净流入-净占比', 0)),
                                'big_net_inflow': float(row.get('大单净流入-净额', 0)) / 10000,
                                'big_net_inflow_rate': float(row.get('大单净流入-净占比', 0)),
                                'medium_net_inflow': float(row.get('中单净流入-净额', 0)) / 10000,
                                'medium_net_inflow_rate': float(row.get('中单净流入-净占比', 0)),
                                'small_net_inflow': float(row.get('小单净流入-净额', 0)) / 10000,
                                'small_net_inflow_rate': float(row.get('小单净流入-净占比', 0)),
                            })

                        logger.info(f"成功获取 {stock_code} 资金流向数据，共 {len(result)} 条")
                        return result

                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"获取失败（尝试 {attempt + 1}/{max_retries}），{retry_delay}秒后重试: {e}")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避
                        else:
                            # 最后一次尝试失败，抛出异常
                            raise

        except Exception as e:
            logger.error(f"东方财富数据源获取失败（已重试{max_retries}次）: {e}")
            raise

    # 全市场 A 股范围（沪深京）
    _MARKET_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
    # 金额字段均为元，落库前 /10000 转万元
    _CLIST_FIELDS = "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87"

    def fetch_market_wide_flow(self, page_size: int = 100,
                               page_pause: float = 1.5,
                               max_retries: int = 4) -> List[Dict]:
        """全市场资金流快照（东财 push2 clist 分页扫描）

        约 60 页即可覆盖全部 A 股，比逐股调用 akshare 快两个数量级，
        供每日批量采集任务（scripts/update_fund_flows.py）使用。

        注意：东财 WAF 对本机房 IP 有频率限制（2026-07-22 起观测到
        RemoteDisconnected 式临时封禁，冷却后可恢复），因此：
        - 页间默认 sleep 1.5s（page_pause 可调）
        - 单页连接被断时指数退避重试 max_retries 次，仍失败则整批放弃
          （宁缺毋滥：部分页缺失会让聚合资金流失真，不如显式失败）

        Returns:
            缓存格式记录列表（不含 trade_date，由调用方补上），金额单位：万元
        """
        import time

        import requests

        url = "https://push2.eastmoney.com/api/qt/clist/get"
        headers = {"Referer": "https://data.eastmoney.com/"}
        # 绕过系统代理（ClashX 会导致国内数据源 502），与 kline/tencent.py 同一模式
        no_proxy = {"http": None, "https": None}

        def _fetch_page(page: int) -> dict:
            params = {
                "pn": page,
                "pz": page_size,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f62",
                "fs": self._MARKET_FS,
                "fields": self._CLIST_FIELDS,
            }
            delay = 2.0
            for attempt in range(max_retries):
                try:
                    resp = requests.get(url, params=params, headers=headers,
                                        proxies=no_proxy, timeout=10)
                    resp.raise_for_status()
                    return resp.json()
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"第 {page} 页获取失败（{type(e).__name__}），"
                                   f"{delay:.0f}s 后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    delay *= 3  # WAF 冷却需要较长时间
            return {}

        records: List[Dict] = []
        page = 1
        while True:
            payload = _fetch_page(page)
            diff = (payload.get("data") or {}).get("diff") or []
            if not diff:
                break

            for item in diff:
                def _yi(key):
                    v = item.get(key)
                    return round(v / 10000, 2) if isinstance(v, (int, float)) else None

                records.append({
                    'symbol': item.get('f12'),
                    'close_price': item.get('f2') if isinstance(item.get('f2'), (int, float)) else None,
                    'change_pct': item.get('f3') if isinstance(item.get('f3'), (int, float)) else None,
                    'main_net_inflow': _yi('f62'),
                    'main_net_inflow_rate': item.get('f184') if isinstance(item.get('f184'), (int, float)) else None,
                    'large_net_inflow': _yi('f66'),
                    'large_net_inflow_rate': item.get('f69') if isinstance(item.get('f69'), (int, float)) else None,
                    'big_net_inflow': _yi('f72'),
                    'big_net_inflow_rate': item.get('f75') if isinstance(item.get('f75'), (int, float)) else None,
                    'medium_net_inflow': _yi('f78'),
                    'medium_net_inflow_rate': item.get('f81') if isinstance(item.get('f81'), (int, float)) else None,
                    'small_net_inflow': _yi('f84'),
                    'small_net_inflow_rate': item.get('f87') if isinstance(item.get('f87'), (int, float)) else None,
                    'source': 'eastmoney_clist',
                })

            total = (payload.get("data") or {}).get("total") or 0
            if page * page_size >= total:
                break
            page += 1
            time.sleep(page_pause)

        logger.info(f"全市场资金流扫描完成: {len(records)} 只股票, {page} 页")
        return records


class SinaFundFlowSource:
    """新浪资金流向数据源（全市场分页排行）

    东财 IP 被 WAF 封锁时（2026-07-22 起观测到）的替代源。
    端点：vip.stock.finance.sina.com.cn MoneyFlow.ssl_bkzj_ssggzj
    粒度：r0=超大单（主力）、r3=小单（散户），无大单/中单细分。
    """

    name = "sina"

    _URL = ("https://vip.stock.finance.sina.com.cn/quotes_service/api/"
            "json_v2.php/MoneyFlow.ssl_bkzj_ssggzj")

    def fetch_market_wide_flow(self, page_size: int = 80,
                               page_pause: float = 0.5,
                               max_retries: int = 3) -> List[Dict]:
        """全市场资金流快照（新浪分页扫描）

        Returns:
            缓存格式记录列表（不含 trade_date），金额单位：万元。
            仅 main（r0 超大单）与 small（r3 小单）有值，其余档位为 None。
        """
        import json
        import time

        import requests

        records: List[Dict] = []
        page = 1
        no_proxy = {"http": None, "https": None}

        while True:
            params = {
                "page": page,
                "num": page_size,
                "sort": "symbol",
                "asc": 1,
                "bankuai": "",
                "shichang": "",
            }
            payload = None
            for attempt in range(max_retries):
                try:
                    resp = requests.get(self._URL, params=params,
                                        proxies=no_proxy, timeout=10)
                    resp.raise_for_status()
                    payload = resp.json()
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"新浪第 {page} 页获取失败（{type(e).__name__}），重试 {attempt + 1}/{max_retries}")
                    time.sleep(2 * (attempt + 1))

            if not payload or not isinstance(payload, list):
                break

            for item in payload:
                def _wan(key):
                    v = item.get(key)
                    try:
                        return round(float(v) / 10000, 2)
                    except (TypeError, ValueError):
                        return None

                def _pct(key):
                    v = item.get(key)
                    try:
                        return round(float(v) * 100, 4)
                    except (TypeError, ValueError):
                        return None

                raw_symbol = str(item.get('symbol') or '')  # 形如 sh600519
                symbol = raw_symbol[2:] if len(raw_symbol) > 2 else raw_symbol
                if not symbol:
                    continue

                records.append({
                    'symbol': symbol,
                    'close_price': float(item['trade']) if item.get('trade') not in (None, '') else None,
                    'change_pct': _pct('changeratio'),
                    'main_net_inflow': _wan('r0_net'),
                    'main_net_inflow_rate': _pct('r0_ratio'),
                    'large_net_inflow': None,
                    'large_net_inflow_rate': None,
                    'big_net_inflow': None,
                    'big_net_inflow_rate': None,
                    'medium_net_inflow': None,
                    'medium_net_inflow_rate': None,
                    'small_net_inflow': _wan('r3_net'),
                    'small_net_inflow_rate': _pct('r3_ratio'),
                    'source': 'sina',
                })

            if len(payload) < page_size:
                break
            page += 1
            time.sleep(page_pause)

        logger.info(f"新浪全市场资金流扫描完成: {len(records)} 只股票, {page} 页")
        return records


class DataSourceError(Exception):
    """数据源错误"""
    pass
