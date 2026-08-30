"""
市场数据服务 - v2 原生实现
提供融资融券,行业资金流向等市场数据
"""
import structlog
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
from domain.ports.datasource_ports import IDataProviderManager, INorthFlowDataSource

logger = structlog.get_logger(__name__)

class DataSourceTimeoutError(Exception):
    """数据源超时异常"""
    pass

class MarketDataService:
    """市场数据服务"""

    def __init__(self, kline_repo=None):
        self.logger = structlog.get_logger(__name__)
        # 延迟导入避免循环依赖
        self._data_source_manager = None
        self._kline_repo = kline_repo
        # TODO: Phase 3 future work - migrate methods to use provider_manager
        # 延迟导入避免顶层依赖
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.provider_manager = get_data_provider_manager()
        # 初始化缓存
        from infrastructure.utils.simple_cache import SimpleCache
        self.cache = SimpleCache()

    @property
    def data_source_manager(self):
        """延迟初始化 DataSourceManager"""
        if self._data_source_manager is None:
            self._data_source_manager = get_data_source_manager()
        return self._data_source_manager

    def get_market_margin(self) -> Dict[str, Any]:
        """
        获取全市场融资融券余额趋势

        Returns:
            包含融资融券数据的字典
        """
        try:

            self.logger.info("获取融资融券数据")

            # 获取上交所数据(无需参数,返回历史数据)
            try:
                df_sh = self.provider_manager.call_akshare('stock_margin_sse')
                self.logger.info(f"上交所数据: {len(df_sh)} 行")
            except Exception as e:
                self.logger.warning(f"上交所数据获取失败: {e}")
                df_sh = pd.DataFrame()

            # 获取深交所数据(需要指定日期)
            try:
                today = datetime.now().strftime("%Y%m%d")
                df_sz = self.provider_manager.call_akshare('stock_margin_szse', date=today)
                self.logger.info(f"深交所数据: {len(df_sz)} 行")
            except Exception as e:
                self.logger.warning(f"深交所数据获取失败: {e}")
                df_sz = pd.DataFrame()

            # 如果都失败,返回友好错误
            if df_sh.empty and df_sz.empty:
                return {
                    'success': False,
                    'error': '暂时无法获取融资融券数据,请稍后重试',
                    'data': None
                }

            # 合并数据(上交所返回最近30条,深交所返回当日汇总)
            result = {
                'success': True,
                'data': {
                    'sh': df_sh.tail(30).to_dict('records') if not df_sh.empty else [],
                    'sz': df_sz.to_dict('records') if not df_sz.empty else [],
                    'update_time': datetime.now().isoformat()
                }
            }

            return result

        
        except Exception as e:
            self.logger.error(f"获取融资融券数据失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def get_sector_fund_flow(self, period: str = "即时", limit: int = 50) -> Dict[str, Any]:
        """
        获取行业资金流向排行(直接调用第三方 API)

        Args:
            period: 时间周期("即时","今日","5日","10日")
            limit: 返回行业数量

        Returns:
            包含行业资金流向数据的字典
        """
        try:

            import os

            self.logger.info(f"获取行业资金流向排行(第三方 API): period={period}, limit={limit}")

            # 禁用代理(避免网络问题)
            old_http_proxy = os.environ.get('HTTP_PROXY')
            old_https_proxy = os.environ.get('HTTPS_PROXY')
            if old_http_proxy:
                del os.environ['HTTP_PROXY']
            if old_https_proxy:
                del os.environ['HTTPS_PROXY']

            try:
                # 映射周期参数
                indicator_map = {
                    "即时": "今日",
                    "今日": "今日",
                    "5日": "5日",
                    "10日": "10日"
                }
                indicator = indicator_map.get(period, "今日")

                # 调用 akshare 接口
                df = self.provider_manager.call_akshare('stock_sector_fund_flow_rank', indicator=indicator)

                if df is None or df.empty:
                    return {
                        'success': False,
                        'error': '暂无行业资金流向数据',
                        'data': None
                    }

                # 转换数据格式
                industries = []
                for idx, row in df.head(limit).iterrows():
                    # 安全获取涨跌幅,处理异常值
                    raw_change_pct = row.get('涨跌幅', 0)
                    try:
                        change_pct = float(raw_change_pct)
                        # 验证数据合理性:A股单日涨跌幅限制约 ±20%,异常值设为 0
                        if abs(change_pct) > 30:
                            self.logger.warning(f"板块 {row.get('名称', 'Unknown')} 涨跌幅异常: {change_pct}%, 已重置为 0")
                            change_pct = 0.0
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"板块 {row.get('名称', 'Unknown')} 涨跌幅解析失败: {raw_change_pct}, error: {e}")
                        change_pct = 0.0

                    industries.append({
                        'name': str(row.get('名称', '')),
                        'code': str(row.get('代码', '')),
                        'rank': idx + 1,
                        'changePct': change_pct,
                        'momentum': change_pct,
                        'flow': float(row.get('主力净流入-净额', 0)) / 100000000,  # 转换为亿元
                        'flowPct': float(row.get('主力净流入-净占比', 0)),
                        'relativeStrength': change_pct,
                        'compositeScore': 0.0,
                    })

                return {
                    'success': True,
                    'data': {
                        'period': period,
                        'industries': industries,
                        'total': len(industries),
                        'update_time': datetime.now().isoformat(),
                        'source': 'eastmoney_api'
                    }
                }

            finally:
                # 恢复代理设置
                if old_http_proxy:
                    os.environ['HTTP_PROXY'] = old_http_proxy
                if old_https_proxy:
                    os.environ['HTTPS_PROXY'] = old_https_proxy

        
        except Exception as e:
            self.logger.error(f"获取行业资金流向失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def get_north_flow(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        获取北向资金流向(沪港通/深港通)- 缓存优先

        Args:
            start_date: 开始日期,格式 YYYYMMDD,默认最近30天
            end_date: 结束日期,格式 YYYYMMDD,默认今天

        Returns:
            包含北向资金流向数据的字典

        Data source strategy (due to East Money API issues since 2024-08-17):
        1. Historical data: Combine 沪股通 + 深股通 (valid until 2024-08-16)
        2. Today's data: Use stock_hsgt_fund_flow_summary_em
        """
        # 生成缓存键
        cache_key = f"north_flow_{start_date or 'default'}_{end_date or 'default'}"

        # 1. 优先返回缓存(30分钟有效期)
        cached_data = self.cache.get(cache_key, max_age_seconds=1800)
        if cached_data:
            self.logger.info(f"北向资金使用缓存")
            return cached_data

        # 2. 缓存未命中,尝试从数据源获取(带超时)
        # 使用线程安全的超时实现
        result = [None]
        error = [None]

        def fetch_data():
            try:
                result[0] = self._fetch_north_flow_data(start_date, end_date)
            except Exception as e:
                error[0] = e

        thread = threading.Thread(target=fetch_data)
        thread.daemon = True
        thread.start()
        thread.join(timeout=60)  # CCASS 首次抓取需 4 次 POST(约 4MB),给足 60 秒

        if thread.is_alive():
            self.logger.warning("北向资金数据源超时 (15秒),尝试使用旧缓存")
            # 超时,尝试返回旧缓存
            stale_cache = self.cache.get_stale(cache_key)
            if stale_cache:
                self.logger.warning(f"使用旧缓存数据: {cache_key}")
                stale_cache['stale'] = True
                return stale_cache

            return {
                'success': False,
                'error': '数据正在加载中,请稍等片刻后重试.提示:可以等待10-20秒后再次调用此接口.',
                'data': None,
                'retry_suggested': True
            }

        if error[0]:
            # 发生错误,尝试返回旧缓存
            self.logger.error(f"获取北向资金失败: {error[0]},尝试使用旧缓存")
            stale_cache = self.cache.get_stale(cache_key)
            if stale_cache:
                self.logger.warning(f"使用旧缓存数据: {cache_key}")
                stale_cache['stale'] = True
                return stale_cache
            raise error[0]

        # 3. 成功获取,保存到缓存
        if result[0] and result[0].get('success'):
            self.cache.set(cache_key, result[0])

        return result[0]

    def _fetch_north_flow_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        北向资金估算(港交所 CCASS 持股变化法)

        【重要通知】2024-08-17 起交易所停止披露北向每日净买入,所有第三方接口已失效.
        原 CCASS 持股变化法也因港交所加强数据访问控制而无法继续使用.

        替代方案:
        1. 使用 Wind/东财付费终端获取北向资金数据
        2. 通过沪深港通官方网站手动查询
        3. 使用第三方金融数据服务商(如聚宽,Tushare Pro)

        返回契约(与 TS fetch-north-flow-tool.ts 对齐):
            {success, data: [{trade_date, net_flow, sh_net_flow, sz_net_flow}],
             summary: {total_net_flow, latest_date, method, estimated,
                       top_inflows, top_outflows, coverage}}
        """
        # 2026-08-29: NorthHoldingsCCASSSource 已被禁止访问,返回替代方案提示
        # 原实现依赖的类无法导入,直接返回错误信息和替代方案
        return {
            'success': False,
            'error': '北向资金数据源已不可用.替代方案:1) 使用 Wind/东财付费终端 2) 沪深港通官网手动查询 3) 第三方数据服务商(聚宽/Tushare Pro)',
            'data': None,
            'summary': {
                'method': 'unavailable',
                'message': '港交所 CCASS 数据访问已受限,请使用商业数据源',
                'alternatives': [
                    'Wind 终端 - 北向资金实时监控',
                    '东方财富 Choice 终端',
                    '聚宽 JQData API - https://www.joinquant.com/help/api/help#name:Stock',
                    'Tushare Pro API - https://tushare.pro/document/2',
                    '沪深港通官网 - http://sc.hkex.com.hk'
                ]
            }
        }

        # 原实现已注释(保留用于参考,依赖 NorthHoldingsCCASSSource 类)
        """
        try:
            from domain.ports import IKlineRepository
            from adapters.outbound.datasources.north_flow_ccass import NorthHoldingsCCASSSource

            source = NorthHoldingsCCASSSource()

            # 1. 找最近两个实际披露日(2024-08 起北向持股改为季度披露)
            dates = source.find_latest_two_disclosures()
            if len(dates) < 2:
                return {
                    'success': False,
                    'error': 'CCASS 北向持股披露数据不可用',
                    'data': None
                }

            latest_date, prev_date = dates[0], dates[1]
            self.logger.info(f"北向持股对比(季度): {prev_date} -> {latest_date}")

            # 2. 拉两个日期的沪深持股快照
            snapshots = {}
            for d in (latest_date, prev_date):
                snapshots[d] = (
                    source.fetch_holdings(d, 'sh') + source.fetch_holdings(d, 'sz')
                )

            # 3. 收盘价(用对比日的最新 K 线)
            if self._kline_repo is None:
                from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
                from domain.ports import IKlineRepository
                kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)
            else:
                kline_repo = self._kline_repo
            symbols = list({r['symbol'] for r in snapshots[latest_date]}
                           | {r['symbol'] for r in snapshots[prev_date]})
            klines = kline_repo.get_latest_daily_klines_batch(symbols)
            prices = {s: (k.get('close') if k else None) for s, k in klines.items()}

            # 4. 持股变化 × 收盘价 = 估算净买入
            prev_map = {r['symbol']: r for r in snapshots[prev_date]}
            latest_map = {r['symbol']: r for r in snapshots[latest_date]}

            sh_net = 0.0
            sz_net = 0.0
            priced_count = 0
            changes = []
            for symbol, cur in latest_map.items():
                prev_shares = prev_map.get(symbol, {}).get('shares_held', 0)
                delta = cur['shares_held'] - prev_shares
                if delta == 0:
                    continue
                price = prices.get(symbol)
                if not price:
                    continue
                value = delta * price
                priced_count += 1
                if symbol.startswith('6'):
                    sh_net += value
                else:
                    sz_net += value
                changes.append({
                    'symbol': symbol,
                    'name': cur.get('name'),
                    'delta_shares': delta,
                    'close': price,
                    'estimated_value': round(value, 2),
                })

            total_net = sh_net + sz_net
            changes.sort(key=lambda x: x['estimated_value'], reverse=True)
            coverage = priced_count / len(latest_map) if latest_map else 0

            flow_data = [{
                'trade_date': latest_date,
                'net_flow': round(total_net, 2),
                'sh_net_flow': round(sh_net, 2),
                'sz_net_flow': round(sz_net, 2),
            }]

            return {
                'success': True,
                'data': flow_data,
                'summary': {
                    'total_net_flow': round(total_net, 2),
                    'latest_date': latest_date,
                    'prev_date': prev_date,
                    'days': 1,
                    'method': 'ccass_holdings_change',
                    'disclosure_frequency': 'quarterly',
                    'estimated': True,
                    'note': '北向每日净买入已于 2024-08 停止披露(交易所规则变更);'
                            '此为港交所 CCASS 季度持股变化 × 收盘价的估算值,'
                            '反映外资季度级调仓方向,不代表每日资金流',
                    'coverage': round(coverage, 3),
                    'top_inflows': changes[:10],
                    'top_outflows': changes[-10:][::-1],
                },
                'update_time': datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"北向资金估算失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'北向资金估算失败: {str(e)}',
                'data': None
            }
        """

    def get_sectors(self) -> Dict[str, Any]:
        """
        获取 A 股行业板块列表 - 使用 DataProviderManager 多数据源 failover

        Returns:
            包含行业板块列表的字典
        """
        self.logger.info("获取 A 股行业板块列表(多数据源)")

        try:
            # 使用统一数据源层(支持多 provider failover)
            result = self.provider_manager.get_sector_list()

            if not result.get('success'):
                error_msg = result.get('error', 'Unknown error')
                attempted = result.get('attempted_sources', [])
                self.logger.warning(f"行业板块数据获取失败: {error_msg} (尝试: {attempted})")
                return {
                    'success': False,
                    'error': f'暂时无法获取行业板块数据: {error_msg}',
                    'data': None
                }

            data = result.get('data')
            # 2026-08-25 修复(sectors 500 根因):provider 可能返回 MarketData 对象
            # (其 .data 属性才是 dict),直接把对象当 dict 用会
            # AttributeError: 'MarketData' object has no attribute 'get'
            if data is not None and not isinstance(data, dict) and hasattr(data, 'data'):
                data = data.data
            if not data:
                return {
                    'success': False,
                    'error': '行业板块数据为空',
                    'data': None
                }

            # 统一输出格式(兼容旧接口)
            industries = data.get('industries', [])
            concepts = data.get('concepts', [])

            # 转换为与旧 akshare 输出兼容的格式
            sectors = []
            for item in industries + concepts:
                sectors.append({
                    '板块名称': item.get('name', ''),
                    '板块代码': item.get('code', ''),
                    '涨跌幅': item.get('change_pct', 0),
                    '涨跌额': item.get('change_amount', 0),
                    '总市值': item.get('market_cap', 0),
                    '类型': '行业' if item in industries else '概念',
                })

            self.logger.info(f"行业板块数据: {len(industries)} 行业 + {len(concepts)} 概念")

            return {
                'success': True,
                'data': {
                    'sectors': sectors,
                    'industries': industries,
                    'concepts': concepts,
                    'total': len(sectors),
                    'source': result.get('source', 'unknown'),
                    'update_time': datetime.now().isoformat()
                }
            }

        except Exception as e:
            self.logger.error(f"获取行业板块列表失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def get_concepts(self, keyword: Optional[str] = None) -> Dict[str, Any]:
        """
        获取 A 股概念板块列表

        Args:
            keyword: 概念关键词(可选,用于筛选)

        Returns:
            包含概念板块列表的字典
        """
        self.logger.info(f"获取 A 股概念板块列表: keyword={keyword}")

        # 使用 DataSourceManager 获取数据(支持多数据源 failover)
        response = self.data_source_manager.get_concept_list()

        if not response.success:
            return {
                'success': False,
                'error': f'暂时无法获取概念板块数据: {response.error}',
                'data': None
            }

        concepts = response.data
        self.logger.info(f"概念板块数据: {len(concepts)} 个")

        # 如果提供了关键词,进行筛选
        if keyword and concepts:
            # 尝试多个可能的列名
            name_columns = ['板块名称', 'name', '名称', 'concept_name']
            filtered = []

            for concept in concepts:
                for col in name_columns:
                    if col in concept and keyword in str(concept[col]):
                        filtered.append(concept)
                        break

            concepts = filtered
            self.logger.info(f"筛选后概念板块数据: {len(concepts)} 个")

        return {
            'success': True,
            'data': {
                'concepts': concepts,
                'total': len(concepts),
                'keyword': keyword,
                'update_time': datetime.now().isoformat(),
                'source': response.source  # 记录数据来源
            }
        }

    def get_concept_stocks(self, concept: str) -> Dict[str, Any]:
        """
        获取指定概念板块的成分股

        Args:
            concept: 概念板块名称

        Returns:
            包含成分股列表的字典
        """
        self.logger.info(f"获取概念板块成分股: concept={concept}")

        # 使用 DataSourceManager 获取数据(支持多数据源 failover)
        response = self.data_source_manager.get_concept_stocks(concept)

        if not response.success:
            return {
                'success': False,
                'error': (
                    f'暂时无法获取概念板块"{concept}"的成分股数据: {response.error}\n\n'
                    f'💡 提示:请先调用 market.concepts 获取所有可用的概念板块列表,然后从中选择一个概念名称.'
                ),
                'data': None
            }

        stocks = response.data
        self.logger.info(f"概念板块成分股数据: {len(stocks)} 只")

        return {
            'success': True,
            'data': {
                'concept': concept,
                'stocks': stocks,
                'total': len(stocks),
                'update_time': datetime.now().isoformat(),
                'source': response.source  # 记录数据来源
            }
        }

    def get_macro_data(self) -> Dict[str, Any]:
        """
        获取宏观经济数据

        Returns:
            包含宏观经济数据的字典
        """
        try:

            self.logger.info("获取宏观经济数据")

            # 获取主要宏观指标
            try:
                # GDP 数据
                gdp_df = self.provider_manager.call_akshare('macro_china_gdp')
                # CPI 数据
                cpi_df = self.provider_manager.call_akshare('macro_china_cpi_yearly')
                # PMI 数据
                pmi_df = self.provider_manager.call_akshare('macro_china_pmi_yearly')

                # GDP数据是倒序的(最新在前),使用head获取最新数据
                # CPI和PMI数据是正序的(最新在后),使用tail获取最新数据
                result = {
                    'gdp': gdp_df.head(5).to_dict('records') if not gdp_df.empty else [],
                    'cpi': cpi_df.tail(5).to_dict('records') if not cpi_df.empty else [],
                    'pmi': pmi_df.tail(5).to_dict('records') if not pmi_df.empty else [],
                }

                return {
                    'success': True,
                    'data': {
                        **result,
                        'update_time': datetime.now().isoformat()
                    }
                }

            except Exception as e:
                self.logger.warning(f"宏观数据获取失败: {e}")
                return {
                    'success': False,
                    'error': f'暂时无法获取宏观经济数据: {str(e)}',
                    'data': None
                }

        
        except Exception as e:
            self.logger.error(f"获取宏观经济数据失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def get_market_news(self, limit: int = 20) -> Dict[str, Any]:
        """
        获取市场新闻

        Args:
            limit: 返回新闻数量

        Returns:
            包含市场新闻的字典
        """
        try:

            self.logger.info(f"获取市场新闻: limit={limit}")

            try:
                # 东方财富财经新闻
                df = self.provider_manager.call_akshare('stock_news_em')

                if df is None or df.empty:
                    return {
                        'success': False,
                        'error': '暂无市场新闻数据',
                        'data': None
                    }

                self.logger.info(f"市场新闻数据: {len(df)} 条")

                news_list = df.head(limit).to_dict('records')

                return {
                    'success': True,
                    'data': {
                        'news': news_list,
                        'total': len(news_list),
                        'update_time': datetime.now().isoformat()
                    }
                }

            except Exception as e:
                self.logger.warning(f"市场新闻获取失败: {e}")
                return {
                    'success': False,
                    'error': f'暂时无法获取市场新闻: {str(e)}',
                    'data': None
                }

        
        except Exception as e:
            self.logger.error(f"获取市场新闻失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

    def get_index_history(
        self,
        symbol: str = "sh000300",
        start_date: str = "",
        end_date: str = ""
    ) -> Dict[str, Any]:
        """
        获取指数历史K线数据

        Args:
            symbol: 指数代码(如 sh000300 沪深300)
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            包含指数K线数据的字典
        """
        try:

            self.logger.info(f"获取指数历史: symbol={symbol}, start={start_date}, end={end_date}")

            try:
                # 获取指数历史数据
                df = self.provider_manager.call_akshare('stock_zh_index_daily', symbol=symbol)

                if df is None or df.empty:
                    return {
                        'success': False,
                        'error': f'暂无指数 {symbol} 的历史数据',
                        'data': None
                    }

                # 日期过滤(akshare 返回的 date 列是 datetime.date,先归一为字符串再与 str 参数比较)
                df['date'] = df['date'].astype(str)
                if start_date:
                    df = df[df['date'] >= start_date]
                if end_date:
                    df = df[df['date'] <= end_date]

                self.logger.info(f"指数历史数据: {len(df)} 条")

                klines = df.to_dict('records')

                return {
                    'success': True,
                    'data': {
                        'symbol': symbol,
                        'klines': klines,
                        'total': len(klines),
                        'start_date': start_date,
                        'end_date': end_date,
                        'update_time': datetime.now().isoformat()
                    }
                }

            except Exception as e:
                self.logger.warning(f"指数历史数据获取失败: {e}")
                return {
                    'success': False,
                    'error': f'暂时无法获取指数历史数据: {str(e)}',
                    'data': None
                }

        
        except Exception as e:
            self.logger.error(f"获取指数历史数据失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'数据获取失败: {str(e)}',
                'data': None
            }

# 全局实例
market_data_service = MarketDataService()
