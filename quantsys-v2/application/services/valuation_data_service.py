"""
估值数据服务 - 多数据源支持

提供 PE/PB/PS 等估值指标的多数据源获取，自动 failover。
支持的数据源：新浪财经、东方财富、akshare、腾讯财经、网易财经
"""
import structlog
import requests
from typing import Dict, Any, Optional
from datetime import datetime
import pandas as pd
from domain.ports.datasource_ports import IDataProviderManager

logger = structlog.get_logger(__name__)


class ValuationDataService:
    """估值数据服务 - 支持多数据源自动切换"""

    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        self.timeout = 5  # 请求超时时间（秒）
        # 延迟导入避免顶层依赖
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.provider_manager = get_data_provider_manager()

    def get_valuation(self, symbol: str) -> Dict[str, Any]:
        """
        获取估值指标（PE/PB/PS/市值）

        自动尝试多个数据源，按优先级顺序：
        1. 新浪财经（最快，最稳定）
        2. 东方财富（数据全面）
        3. akshare（开源方案）
        4. 腾讯财经（备用）
        5. 网易财经（最后兜底）

        Args:
            symbol: 股票代码（支持 600519 或 600519.SH 格式）

        Returns:
            {
                'success': True/False,
                'data': {
                    'symbol': '600519',
                    'valuation': {
                        'pe': float,           # 市盈率（动态）
                        'pb': float,           # 市净率
                        'ps': float,           # 市销率（可选）
                        'current_price': float,
                        'market_cap': float,   # 总市值
                        'circulating_market_cap': float  # 流通市值（可选）
                    },
                    'source': 'sina/eastmoney/akshare/tencent/netease',
                    'update_time': 'ISO8601 timestamp'
                },
                'error': '错误信息（仅失败时）'
            }
        """
        # 清理股票代码（移除后缀）
        clean_symbol = symbol.replace('.SH', '').replace('.SZ', '').replace('.HK', '')

        # 按优先级尝试各数据源
        sources = [
            ('sina', self._get_from_sina),
            ('eastmoney', self._get_from_eastmoney),
            ('akshare', self._get_from_akshare),
            ('tencent', self._get_from_tencent),
            ('netease', self._get_from_netease),
        ]

        for source_name, fetcher in sources:
            try:
                self.logger.info(f"尝试从 {source_name} 获取 {clean_symbol} 估值数据")
                result = fetcher(clean_symbol)

                if result and result.get('success'):
                    self.logger.info(f"成功从 {source_name} 获取估值数据")
                    return result

            except Exception as e:
                self.logger.warning(f"{source_name} 获取失败: {e}")
                continue

        # 所有数据源都失败
        return {
            'success': False,
            'error': f'无法获取股票 {symbol} 的估值数据（已尝试 5 个数据源均失败）',
            'data': None,
            'suggestion': '请检查股票代码是否正确，或稍后重试'
        }

    def _get_from_sina(self, symbol: str) -> Dict[str, Any]:
        """
        从新浪财经获取估值数据

        API: http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData
        """
        try:
            # 构造市场代码（sh/sz）
            market_code = 'sh' if symbol.startswith('6') else 'sz'
            full_symbol = f"{market_code}{symbol}"

            # 新浪财经详细接口
            url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=1&sort=symbol&asc=1&node=hs_a&symbol={full_symbol}"

            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            if not data or len(data) == 0:
                raise Exception("新浪返回空数据")

            stock = data[0]

            # 提取估值指标
            valuation = {}

            if 'trade' in stock and stock['trade']:
                valuation['current_price'] = float(stock['trade'])

            if 'per' in stock and stock['per']:
                try:
                    valuation['pe'] = float(stock['per'])
                except (ValueError, TypeError):
                    pass

            if 'pb' in stock and stock['pb']:
                try:
                    valuation['pb'] = float(stock['pb'])
                except (ValueError, TypeError):
                    pass

            if 'mktcap' in stock and stock['mktcap']:
                try:
                    valuation['market_cap'] = float(stock['mktcap']) * 100000000  # 转换为元
                except (ValueError, TypeError):
                    pass

            if 'nmc' in stock and stock['nmc']:
                try:
                    valuation['circulating_market_cap'] = float(stock['nmc']) * 100000000
                except (ValueError, TypeError):
                    pass

            if not valuation:
                raise Exception("未能提取到估值数据")

            return {
                'success': True,
                'data': {
                    'symbol': symbol,
                    'valuation': valuation,
                    'source': 'sina',
                    'update_time': datetime.now().isoformat()
                }
            }

        except Exception as e:
            self.logger.debug(f"新浪财经获取失败: {e}")
            return {'success': False, 'error': str(e)}

    def _get_from_eastmoney(self, symbol: str) -> Dict[str, Any]:
        """
        从东方财富获取估值数据

        API: http://push2.eastmoney.com/api/qt/stock/get
        """
        try:
            # 构造证券ID（1=上海，0=深圳）
            market_id = '1' if symbol.startswith('6') else '0'
            secid = f"{market_id}.{symbol}"

            url = "http://push2.eastmoney.com/api/qt/stock/get"
            params = {
                'secid': secid,
                'fields': 'f57,f58,f46,f162,f167'  # PE, PB, 价格, 总市值, 流通市值
            }

            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            if data.get('rc') != 0 or not data.get('data'):
                raise Exception("东方财富返回错误")

            stock = data['data']

            # 提取估值指标
            valuation = {}

            if 'f46' in stock and stock['f46']:
                valuation['current_price'] = float(stock['f46'])

            if 'f57' in stock and stock['f57']:
                valuation['pe'] = float(stock['f57'])

            if 'f58' in stock and stock['f58']:
                valuation['pb'] = float(stock['f58'])

            if 'f162' in stock and stock['f162']:
                valuation['market_cap'] = float(stock['f162'])

            if 'f167' in stock and stock['f167']:
                valuation['circulating_market_cap'] = float(stock['f167'])

            if not valuation:
                raise Exception("未能提取到估值数据")

            return {
                'success': True,
                'data': {
                    'symbol': symbol,
                    'valuation': valuation,
                    'source': 'eastmoney',
                    'update_time': datetime.now().isoformat()
                }
            }

        except Exception as e:
            self.logger.debug(f"东方财富获取失败: {e}")
            return {'success': False, 'error': str(e)}

    def _get_from_akshare(self, symbol: str) -> Dict[str, Any]:
        """从 akshare 获取估值数据"""
        try:
            # 2026-09-05 修复：call_akshare 方法不存在，改走
            # DataProviderManager.get_market_spot() 并 unwrap 数据类载荷。
            resp = self.provider_manager.get_market_spot()
            if not resp.get('success') or resp.get('data') is None:
                raise Exception(f"akshare 返回空数据: {resp.get('error', 'provider 返回空')}")

            records = resp['data'].data.get('records') or []  # MarketData.data = {'records': [...], 'total': n}
            df = pd.DataFrame(records)

            if df.empty:
                raise Exception("akshare 返回空数据")

            stock_data = df[df['代码'] == symbol]

            if stock_data.empty:
                raise Exception(f"未找到股票 {symbol}")

            row = stock_data.iloc[0]

            valuation = {}

            if '最新价' in row and pd.notna(row['最新价']):
                valuation['current_price'] = float(row['最新价'])

            if '市盈率-动态' in row and pd.notna(row['市盈率-动态']):
                valuation['pe'] = float(row['市盈率-动态'])

            if '市净率' in row and pd.notna(row['市净率']):
                valuation['pb'] = float(row['市净率'])

            if '市销率' in row and pd.notna(row['市销率']):
                valuation['ps'] = float(row['市销率'])

            if '总市值' in row and pd.notna(row['总市值']):
                valuation['market_cap'] = float(row['总市值'])

            if '流通市值' in row and pd.notna(row['流通市值']):
                valuation['circulating_market_cap'] = float(row['流通市值'])

            if not valuation:
                raise Exception("未能提取到估值数据")

            return {
                'success': True,
                'data': {
                    'symbol': symbol,
                    'valuation': valuation,
                    'source': 'akshare',
                    'update_time': datetime.now().isoformat()
                }
            }

        except Exception as e:
            self.logger.debug(f"akshare 获取失败: {e}")
            return {'success': False, 'error': str(e)}

    def _get_from_tencent(self, symbol: str) -> Dict[str, Any]:
        """从腾讯财经获取估值数据（降级方案，仅返回价格）"""
        try:
            market_code = 'sh' if symbol.startswith('6') else 'sz'
            full_symbol = f"{market_code}{symbol}"

            url = f"http://qt.gtimg.cn/q=s_{full_symbol}"

            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()

            text = response.text
            if not text or '~' not in text:
                raise Exception("腾讯返回空数据")

            start = text.find('"') + 1
            end = text.rfind('"')
            data_str = text[start:end]
            fields = data_str.split('~')

            if len(fields) < 10:
                raise Exception("腾讯返回数据字段不足")

            valuation = {}

            try:
                valuation['current_price'] = float(fields[3])
            except (IndexError, ValueError):
                pass

            if not valuation:
                raise Exception("未能提取到估值数据")

            return {
                'success': True,
                'data': {
                    'symbol': symbol,
                    'valuation': valuation,
                    'source': 'tencent',
                    'update_time': datetime.now().isoformat(),
                    'note': '腾讯财经简版接口仅包含价格数据'
                }
            }

        except Exception as e:
            self.logger.debug(f"腾讯财经获取失败: {e}")
            return {'success': False, 'error': str(e)}

    def _get_from_netease(self, symbol: str) -> Dict[str, Any]:
        """从网易财经获取估值数据"""
        try:
            prefix = '0' if symbol.startswith('6') else '1'
            full_symbol = f"{prefix}{symbol}"

            url = f"http://api.money.126.net/data/feed/{full_symbol}"

            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()

            text = response.text
            start = text.find('{')
            end = text.rfind('}') + 1

            if start == -1 or end == 0:
                raise Exception("网易返回格式错误")

            import json
            data = json.loads(text[start:end])

            key = full_symbol
            if key not in data:
                raise Exception(f"未找到股票 {symbol}")

            stock = data[key]

            valuation = {}

            if 'price' in stock:
                valuation['current_price'] = float(stock['price'])

            if 'per' in stock and stock['per']:
                try:
                    valuation['pe'] = float(stock['per'])
                except (ValueError, TypeError):
                    pass

            if 'pb' in stock and stock['pb']:
                try:
                    valuation['pb'] = float(stock['pb'])
                except (ValueError, TypeError):
                    pass

            if not valuation:
                raise Exception("未能提取到估值数据")

            return {
                'success': True,
                'data': {
                    'symbol': symbol,
                    'valuation': valuation,
                    'source': 'netease',
                    'update_time': datetime.now().isoformat()
                }
            }

        except Exception as e:
            self.logger.debug(f"网易财经获取失败: {e}")
            return {'success': False, 'error': str(e)}


# 单例模式
_valuation_service = None


def get_valuation_service() -> ValuationDataService:
    """获取估值数据服务单例"""
    global _valuation_service
    if _valuation_service is None:
        _valuation_service = ValuationDataService()
    return _valuation_service
