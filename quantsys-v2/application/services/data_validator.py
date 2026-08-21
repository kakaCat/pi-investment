"""
数据验证器

验证K线数据质量，检测异常值、重复数据等问题。
"""
import structlog
from typing import List, Dict, Optional, Tuple
from datetime import datetime

logger = structlog.get_logger(__name__)


class DataValidator:
    """数据验证器

    验证K线数据质量，包括：
    - 价格范围验证
    - 涨跌幅限制检查
    - 成交量验证
    - 重复数据检测
    - 异常值检测
    """

    def __init__(self, kline_repo=None):
        """初始化数据验证器

        Args:
            kline_repo: K线数据仓库实例
        """
        from domain.ports import IKlineRepository
        self.kline_repo = kline_repo or IKlineRepository()

    def validate_klines(self, klines: List[Dict]) -> Dict:
        """验证K线数据列表

        Args:
            klines: K线数据列表

        Returns:
            验证结果:
            {
                'valid': True/False,
                'total_records': 100,
                'valid_records': 98,
                'invalid_records': 2,
                'errors': [
                    {'index': 5, 'date': '2026-01-15', 'error': 'high < low'},
                    ...
                ]
            }
        """
        # klines is a Polars DataFrame, check if empty using .is_empty()
        if klines.is_empty():
            return {
                'valid': True,
                'total_records': 0,
                'valid_records': 0,
                'invalid_records': 0,
                'errors': []
            }

        # Convert to list of dicts for validation
        klines_list = klines.to_dicts()
        errors = []
        valid_count = 0

        for i, kline in enumerate(klines_list):
            validation_errors = []

            # 1. 价格范围验证
            price_errors = self._validate_price_range(kline)
            validation_errors.extend(price_errors)

            # 2. 成交量验证
            volume_errors = self._validate_volume(kline)
            validation_errors.extend(volume_errors)

            # 3. 涨跌幅验证（需要前一天的收盘价）
            if i > 0:
                limit_errors = self._validate_price_limit(kline, klines[i-1])
                validation_errors.extend(limit_errors)

            if validation_errors:
                errors.append({
                    'index': i,
                    'date': kline.get('trade_date'),
                    'symbol': kline.get('symbol'),
                    'errors': validation_errors
                })
            else:
                valid_count += 1

        return {
            'valid': len(errors) == 0,
            'total_records': len(klines),
            'valid_records': valid_count,
            'invalid_records': len(errors),
            'errors': errors
        }

    def _validate_price_range(self, kline: Dict) -> List[str]:
        """验证价格范围

        规则:
        - high >= low
        - high >= close >= low
        - high >= open >= low
        - 所有价格 > 0

        Args:
            kline: K线数据

        Returns:
            错误列表
        """
        errors = []

        try:
            open_price = float(kline.get('open', 0))
            high = float(kline.get('high', 0))
            low = float(kline.get('low', 0))
            close = float(kline.get('close', 0))

            # 价格必须 > 0
            if open_price <= 0:
                errors.append('open <= 0')
            if high <= 0:
                errors.append('high <= 0')
            if low <= 0:
                errors.append('low <= 0')
            if close <= 0:
                errors.append('close <= 0')

            # high >= low
            if high < low:
                errors.append(f'high ({high}) < low ({low})')

            # high >= close >= low
            if close > high:
                errors.append(f'close ({close}) > high ({high})')
            if close < low:
                errors.append(f'close ({close}) < low ({low})')

            # high >= open >= low
            if open_price > high:
                errors.append(f'open ({open_price}) > high ({high})')
            if open_price < low:
                errors.append(f'open ({open_price}) < low ({low})')

        except (ValueError, TypeError) as e:
            errors.append(f'价格格式错误: {e}')

        return errors

    def _validate_volume(self, kline: Dict) -> List[str]:
        """验证成交量

        规则:
        - volume >= 0
        - amount >= 0
        - 0 <= turnover_rate <= 100

        Args:
            kline: K线数据

        Returns:
            错误列表
        """
        errors = []

        try:
            volume = float(kline.get('volume', 0))
            amount = float(kline.get('amount', 0))
            turnover_rate = float(kline.get('turnover_rate', 0))

            if volume < 0:
                errors.append(f'volume < 0 ({volume})')

            if amount < 0:
                errors.append(f'amount < 0 ({amount})')

            if turnover_rate < 0 or turnover_rate > 100:
                errors.append(f'turnover_rate 超出范围 ({turnover_rate})')

        except (ValueError, TypeError) as e:
            errors.append(f'成交量格式错误: {e}')

        return errors

    def _validate_price_limit(self, current: Dict, previous: Dict) -> List[str]:
        """验证涨跌幅限制

        A股规则:
        - 普通股票: ±10%
        - ST股票: ±5%
        - 科创板/创业板: ±20%
        - 新股首日: 无限制

        Args:
            current: 当前K线
            previous: 前一天K线

        Returns:
            错误列表
        """
        errors = []

        try:
            current_close = float(current.get('close', 0))
            prev_close = float(previous.get('close', 0))

            if prev_close <= 0:
                return errors

            # 计算涨跌幅
            change_pct = abs((current_close - prev_close) / prev_close)

            # 简化判断：统一使用 20% 限制（科创板/创业板标准）
            # 实际应用中应根据股票代码判断板块
            if change_pct > 0.20:
                symbol = current.get('symbol', '')

                # 排除特殊情况（这里可以扩展）
                # 例如：新股首日、停牌复牌等
                if not self._is_special_case(symbol, current):
                    errors.append(f'涨跌幅超限 ({change_pct*100:.2f}%)')

        except (ValueError, TypeError) as e:
            errors.append(f'涨跌幅计算错误: {e}')

        return errors

    def _is_special_case(self, symbol: str, kline: Dict) -> bool:
        """判断是否为特殊情况（新股首日、复牌等）

        Args:
            symbol: 股票代码
            kline: K线数据

        Returns:
            True if 特殊情况
        """
        # TODO: 实现特殊情况判断逻辑
        # 例如查询股票上市日期、停牌记录等
        return False

    def detect_duplicates(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """检测重复数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            重复数据信息:
            {
                'has_duplicates': True/False,
                'duplicate_dates': ['2026-01-15', '2026-02-20'],
                'duplicate_count': 2
            }
        """
        try:
            query = """
                SELECT trade_date, COUNT(*) as cnt
                FROM quant.daily_klines
                WHERE symbol = %s
                  AND trade_date >= %s
                  AND trade_date <= %s
                GROUP BY trade_date
                HAVING COUNT(*) > 1
                ORDER BY trade_date
            """

            cursor = self.kline_repo._get_cursor()
            cursor.execute(query, (symbol, start_date, end_date))
            results = cursor.fetchall()
            cursor.close()

            # Handle both dict and tuple results
            if results and isinstance(results[0], dict):
                duplicate_dates = [str(row['trade_date']) for row in results]
            elif results:
                duplicate_dates = [str(row[0]) for row in results]
            else:
                duplicate_dates = []

            return {
                'has_duplicates': len(duplicate_dates) > 0,
                'duplicate_dates': duplicate_dates,
                'duplicate_count': len(duplicate_dates)
            }

        except Exception as e:
            logger.error(f"检测重复数据失败: {e}")
            return {
                'has_duplicates': False,
                'duplicate_dates': [],
                'duplicate_count': 0,
                'error': str(e)
            }

    def detect_anomalies(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        threshold: float = 3.0
    ) -> Dict:
        """检测异常值（使用统计方法）

        使用 Z-score 方法检测价格和成交量异常：
        Z = (x - mean) / std
        |Z| > threshold 视为异常值

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            threshold: Z-score 阈值（默认3.0，即3倍标准差）

        Returns:
            异常值信息:
            {
                'has_anomalies': True/False,
                'price_anomalies': [
                    {'date': '2026-01-15', 'close': 100.5, 'z_score': 3.5},
                    ...
                ],
                'volume_anomalies': [...],
                'total_anomalies': 5
            }
        """
        try:
            # 获取K线数据
            klines = self.kline_repo.get_daily_klines(symbol, start_date, end_date)

            # klines is a Polars DataFrame, check if empty using .is_empty()
            if klines.is_empty() or len(klines) < 30:
                return {
                    'has_anomalies': False,
                    'price_anomalies': [],
                    'volume_anomalies': [],
                    'total_anomalies': 0,
                    'message': 'Insufficient data for anomaly detection'
                }

            # Convert to list of dicts for processing
            klines_list = klines.to_dicts()

            # 提取价格和成交量
            closes = [float(k['close']) for k in klines_list]
            volumes = [float(k['volume']) for k in klines_list if float(k['volume']) > 0]

            # 计算统计量
            import statistics
            close_mean = statistics.mean(closes)
            close_std = statistics.stdev(closes)
            volume_mean = statistics.mean(volumes) if volumes else 0
            volume_std = statistics.stdev(volumes) if len(volumes) > 1 else 0

            # 检测价格异常
            price_anomalies = []
            for kline in klines_list:
                close = float(kline['close'])
                if close_std > 0:
                    z_score = abs((close - close_mean) / close_std)
                    if z_score > threshold:
                        price_anomalies.append({
                            'date': str(kline['trade_date']),
                            'close': close,
                            'z_score': round(z_score, 2)
                        })

            # 检测成交量异常
            volume_anomalies = []
            for kline in klines:
                volume = float(kline['volume'])
                if volume > 0 and volume_std > 0:
                    z_score = abs((volume - volume_mean) / volume_std)
                    if z_score > threshold:
                        volume_anomalies.append({
                            'date': str(kline['trade_date']),
                            'volume': volume,
                            'z_score': round(z_score, 2)
                        })

            total_anomalies = len(price_anomalies) + len(volume_anomalies)

            return {
                'has_anomalies': total_anomalies > 0,
                'price_anomalies': price_anomalies[:10],  # 最多返回10个
                'volume_anomalies': volume_anomalies[:10],
                'total_anomalies': total_anomalies
            }

        except Exception as e:
            logger.error(f"检测异常值失败: {e}")
            return {
                'has_anomalies': False,
                'price_anomalies': [],
                'volume_anomalies': [],
                'total_anomalies': 0,
                'error': str(e)
            }

    def get_data_quality_score(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        coverage_rate: float
    ) -> float:
        """计算数据质量评分 (0-100)

        综合考虑：
        - 覆盖率 (60%)
        - 重复率 (20%)
        - 异常率 (20%)

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            coverage_rate: 覆盖率 (0-100)

        Returns:
            质量评分 (0-100)
        """
        try:
            # 1. 覆盖率得分 (60%)
            coverage_score = coverage_rate * 0.6

            # 2. 重复率得分 (20%)
            dup_info = self.detect_duplicates(symbol, start_date, end_date)
            duplicate_rate = dup_info['duplicate_count'] / max(1, len(
                self.kline_repo.get_daily_klines(symbol, start_date, end_date)
            )) * 100
            duplicate_score = max(0, 20 - duplicate_rate * 2)  # 每1%重复扣2分

            # 3. 异常率得分 (20%)
            anomaly_info = self.detect_anomalies(symbol, start_date, end_date)
            total_records = len(self.kline_repo.get_daily_klines(symbol, start_date, end_date))
            anomaly_rate = anomaly_info['total_anomalies'] / max(1, total_records) * 100
            anomaly_score = max(0, 20 - anomaly_rate * 4)  # 每1%异常扣4分

            total_score = coverage_score + duplicate_score + anomaly_score

            return round(min(100, max(0, total_score)), 2)

        except Exception as e:
            logger.error(f"计算数据质量评分失败: {e}")
            return 0.0
