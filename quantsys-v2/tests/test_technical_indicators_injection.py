"""
Tests for technical indicators injection in strategy code service
"""
import pytest
import math
from application.services.strategy_code_service import StrategyCodeService


class TestTechnicalIndicatorsInjection:
    """Test technical indicators injection"""

    def test_inject_technical_indicators_basic(self):
        """Test basic technical indicators injection"""
        service = StrategyCodeService()

        # Prepare test K-lines (30 days for proper indicator calculation)
        klines = []
        base_price = 100.0
        for i in range(30):
            # Simulate price movement
            price = base_price + (i % 10) - 5
            klines.append({
                'trade_date': f'2026-04-{i+1:02d}',
                'open': price - 1,
                'high': price + 2,
                'low': price - 2,
                'close': price,
                'volume': 1000000 + i * 10000
            })

        # Inject technical indicators
        result = service._inject_technical_indicators(klines)

        # Verify result is not None
        assert result is not None
        assert len(result) == 30

        # Verify technical indicator columns exist
        expected_indicators = [
            'rsi', 'macd', 'macd_signal', 'macd_hist',
            'bollinger_upper', 'bollinger_middle', 'bollinger_lower',
            'ma5', 'ma10', 'ma20', 'ma60'
        ]

        for indicator in expected_indicators:
            assert indicator in result[0], f"Missing indicator: {indicator}"

        # Verify some indicators have valid values (not all NaN)
        # Check last row (should have most indicators calculated)
        last_row = result[-1]
        assert not math.isnan(last_row['ma5']), "MA5 should have value"
        assert not math.isnan(last_row['ma10']), "MA10 should have value"
        assert not math.isnan(last_row['ma20']), "MA20 should have value"
        assert not math.isnan(last_row['rsi']), "RSI should have value"
        assert not math.isnan(last_row['macd']), "MACD should have value"

    def test_inject_technical_indicators_rsi_range(self):
        """Test RSI values are in valid range (0-100)"""
        service = StrategyCodeService()

        # Create K-lines with clear trend
        klines = []
        for i in range(30):
            klines.append({
                'trade_date': f'2026-04-{i+1:02d}',
                'open': 100 + i,
                'high': 102 + i,
                'low': 99 + i,
                'close': 100 + i,
                'volume': 1000000
            })

        result = service._inject_technical_indicators(klines)

        # Check RSI values are in valid range
        for row in result:
            rsi = row['rsi']
            if not math.isnan(rsi):
                assert 0 <= rsi <= 100, f"RSI out of range: {rsi}"

    def test_inject_technical_indicators_bollinger_bands(self):
        """Test Bollinger Bands relationship (lower < middle < upper)"""
        service = StrategyCodeService()

        klines = []
        for i in range(30):
            klines.append({
                'trade_date': f'2026-04-{i+1:02d}',
                'open': 100,
                'high': 105,
                'low': 95,
                'close': 100 + (i % 5),
                'volume': 1000000
            })

        result = service._inject_technical_indicators(klines)

        # Check Bollinger Bands relationship
        for row in result:
            lower = row['bollinger_lower']
            middle = row['bollinger_middle']
            upper = row['bollinger_upper']

            if not (math.isnan(lower) or math.isnan(middle) or math.isnan(upper)):
                assert lower <= middle <= upper, \
                    f"Bollinger bands invalid: lower={lower}, middle={middle}, upper={upper}"

    def test_inject_technical_indicators_macd_components(self):
        """Test MACD components relationship"""
        service = StrategyCodeService()

        klines = []
        for i in range(30):
            klines.append({
                'trade_date': f'2026-04-{i+1:02d}',
                'open': 100,
                'high': 105,
                'low': 95,
                'close': 100 + i * 0.5,
                'volume': 1000000
            })

        result = service._inject_technical_indicators(klines)

        # Check MACD histogram = MACD - Signal
        for row in result:
            macd = row['macd']
            signal = row['macd_signal']
            hist = row['macd_hist']

            if not (math.isnan(macd) or math.isnan(signal) or math.isnan(hist)):
                expected_hist = macd - signal
                assert abs(hist - expected_hist) < 0.01, \
                    f"MACD histogram mismatch: {hist} vs {expected_hist}"

    def test_inject_technical_indicators_moving_averages(self):
        """Test moving averages relationship (shorter MA more responsive)"""
        service = StrategyCodeService()

        # Create uptrend
        klines = []
        for i in range(70):
            klines.append({
                'trade_date': f'2026-04-{i+1:02d}',
                'open': 100 + i,
                'high': 102 + i,
                'low': 99 + i,
                'close': 100 + i,
                'volume': 1000000
            })

        result = service._inject_technical_indicators(klines)

        # In uptrend, shorter MA should be above longer MA
        last_row = result[-1]
        ma5 = last_row['ma5']
        ma10 = last_row['ma10']
        ma20 = last_row['ma20']
        ma60 = last_row['ma60']

        assert ma5 > ma10, "In uptrend, MA5 should be > MA10"
        assert ma10 > ma20, "In uptrend, MA10 should be > MA20"
        assert ma20 > ma60, "In uptrend, MA20 should be > MA60"

    def test_inject_technical_indicators_insufficient_data(self):
        """Test handling of insufficient data"""
        service = StrategyCodeService()

        # Only 1 K-line
        klines = [{
            'trade_date': '2026-04-01',
            'open': 100,
            'high': 105,
            'low': 95,
            'close': 100,
            'volume': 1000000
        }]

        result = service._inject_technical_indicators(klines)

        # Should return original data without crashing
        assert result is not None
        assert len(result) == 1

    def test_inject_technical_indicators_missing_columns(self):
        """Test handling of missing required columns"""
        service = StrategyCodeService()

        # K-lines without close column
        klines = [{
            'trade_date': '2026-04-01',
            'open': 100,
            'volume': 1000000
        }]

        result = service._inject_technical_indicators(klines)

        # Should return original data without crashing
        assert result is not None
        assert len(result) == 1

    def test_inject_technical_indicators_with_strategy_execution(self):
        """Test technical indicators work with strategy execution"""
        service = StrategyCodeService()

        # Create K-lines
        klines = []
        for i in range(30):
            price = 100 + (i % 10) - 5
            klines.append({
                'trade_date': f'2026-04-{i+1:02d}',
                'open': price - 1,
                'high': price + 2,
                'low': price - 2,
                'close': price,
                'volume': 1000000
            })

        # Inject technical indicators
        klines_with_indicators = service._inject_technical_indicators(klines)

        # Create a strategy that uses technical indicators
        strategy_code = """
# Test strategy using technical indicators
df['oversold'] = df['rsi'] < 30
df['overbought'] = df['rsi'] > 70
df['ma_cross'] = (df['ma5'] > df['ma20']) & (df['ma5'].shift(1) <= df['ma20'].shift(1))

df['buy'] = df['oversold'] | df['ma_cross']
df['sell'] = df['overbought']
"""

        # Execute strategy
        from domain.quantlib.engine.indicator_strategy_executor import IndicatorStrategyExecutor
        executor = IndicatorStrategyExecutor()

        result = executor.execute(
            code=strategy_code,
            klines=klines_with_indicators,
            params={}
        )

        # Verify execution succeeded
        assert result is not None
        assert result.signals is not None
        assert 'buy' in result.signals.columns
        assert 'sell' in result.signals.columns
        assert len(result.signals) == 30

    def test_inject_technical_indicators_preserves_existing_columns(self):
        """Test that injection preserves existing columns"""
        service = StrategyCodeService()

        klines = []
        for i in range(30):
            klines.append({
                'trade_date': f'2026-04-{i+1:02d}',
                'open': 100,
                'high': 105,
                'low': 95,
                'close': 100,
                'volume': 1000000,
                'custom_field': f'value_{i}'  # Custom field
            })

        result = service._inject_technical_indicators(klines)

        # Verify original columns are preserved
        assert 'trade_date' in result[0]
        assert 'open' in result[0]
        assert 'high' in result[0]
        assert 'low' in result[0]
        assert 'close' in result[0]
        assert 'volume' in result[0]
        assert 'custom_field' in result[0]

        # Verify custom field values are preserved
        for i, row in enumerate(result):
            assert row['custom_field'] == f'value_{i}'
