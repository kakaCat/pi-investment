"""测试FactorStage - 因子计算"""
import pytest
import pandas as pd
from domain.quantlib.stages.factor_stage import FactorStage


class TestFactorStage:
    """测试因子计算Stage"""

    def test_validate_input_success(self):
        """测试输入验证 - 成功场景"""
        stage = FactorStage()

        data = {
            "symbol": "000001",
            "klines": [
                {"date": "2026-05-01", "close": 100.0, "high": 102.0, "low": 99.0, "open": 100.5, "volume": 1000000},
                {"date": "2026-05-02", "close": 101.0, "high": 103.0, "low": 100.0, "open": 101.5, "volume": 1100000},
            ] * 10  # 20条数据
        }

        assert stage.validate_input(data) == True

    def test_validate_input_missing_symbol(self):
        """测试输入验证 - 缺少symbol"""
        stage = FactorStage()

        data = {
            "klines": [{"date": "2026-05-01", "close": 100.0}]
        }

        with pytest.raises(ValueError, match="Missing required field: symbol"):
            stage.validate_input(data)

    def test_validate_input_missing_klines(self):
        """测试输入验证 - 缺少klines"""
        stage = FactorStage()

        data = {
            "symbol": "000001"
        }

        with pytest.raises(ValueError, match="Missing required field: klines"):
            stage.validate_input(data)

    def test_validate_input_invalid_klines_type(self):
        """测试输入验证 - klines类型错误"""
        stage = FactorStage()

        data = {
            "symbol": "000001",
            "klines": "not a list"
        }

        with pytest.raises(ValueError, match="klines must be a list"):
            stage.validate_input(data)

    def test_process_basic_factors(self):
        """测试基本因子计算"""
        stage = FactorStage()

        # 构造30天的K线数据
        klines = []
        for i in range(30):
            klines.append({
                "date": f"2026-05-{i+1:02d}",
                "close": 100.0 + i * 0.5,  # 递增价格
                "high": 102.0 + i * 0.5,
                "low": 99.0 + i * 0.5,
                "open": 100.5 + i * 0.5,
                "volume": 1000000 + i * 10000
            })

        data = {
            "symbol": "000001",
            "klines": klines
        }

        result = stage.process(data)

        # 验证结果结构
        assert "factors" in result
        assert "symbol" in result
        assert "klines" in result
        assert result["symbol"] == "000001"

        factors = result["factors"]

        # 验证因子存在（使用 FactorRegistry 注册的因子名）
        assert "ma5" in factors
        assert "ma10" in factors
        assert "ma20" in factors
        assert "rsi14" in factors
        assert "macd" in factors
        assert "macd_signal" in factors
        assert "macd_histogram" in factors
        assert "bollinger_upper" in factors
        assert "bollinger_middle" in factors
        assert "bollinger_lower" in factors
        assert "atr14" in factors
        assert "volume_ma5" in factors
        assert "volume_ratio" in factors

    def test_ma_calculation(self):
        """测试移动平均线计算"""
        stage = FactorStage()

        # 构造简单的价格序列: 100, 101, 102, 103, 104, ...
        klines = []
        for i in range(30):
            klines.append({
                "date": f"2026-05-{i+1:02d}",
                "close": 100.0 + i,
                "high": 102.0 + i,
                "low": 99.0 + i,
                "open": 100.5 + i,
                "volume": 1000000
            })

        data = {
            "symbol": "000001",
            "klines": klines
        }

        result = stage.process(data)
        factors = result["factors"]

        # MA5应该是最后5天的平均: (125+126+127+128+129)/5 = 127
        assert abs(factors["ma5"] - 127.0) < 0.01

        # MA10应该是最后10天的平均: (120+...+129)/10 = 124.5
        assert abs(factors["ma10"] - 124.5) < 0.01

        # MA20应该是最后20天的平均: (110+...+129)/20 = 119.5
        assert abs(factors["ma20"] - 119.5) < 0.01

    def test_rsi_calculation(self):
        """测试RSI计算"""
        stage = FactorStage()

        # 构造上涨趋势的数据
        klines = []
        for i in range(30):
            klines.append({
                "date": f"2026-05-{i+1:02d}",
                "close": 100.0 + i * 2,  # 强上涨
                "high": 102.0 + i * 2,
                "low": 99.0 + i * 2,
                "open": 100.5 + i * 2,
                "volume": 1000000
            })

        data = {
            "symbol": "000001",
            "klines": klines
        }

        result = stage.process(data)
        factors = result["factors"]

        # 强上涨趋势，RSI应该接近100
        assert factors["rsi14"] > 80
        assert factors["rsi14"] <= 100

    def test_macd_calculation(self):
        """测试MACD计算"""
        stage = FactorStage()

        klines = []
        for i in range(30):
            klines.append({
                "date": f"2026-05-{i+1:02d}",
                "close": 100.0 + i * 0.5,
                "high": 102.0 + i * 0.5,
                "low": 99.0 + i * 0.5,
                "open": 100.5 + i * 0.5,
                "volume": 1000000
            })

        data = {
            "symbol": "000001",
            "klines": klines
        }

        result = stage.process(data)
        factors = result["factors"]

        # MACD值应该存在且为数值
        assert isinstance(factors["macd"], (int, float))
        assert isinstance(factors["macd_signal"], (int, float))
        assert isinstance(factors["macd_histogram"], (int, float))

        # 上涨趋势，MACD应该为正
        assert factors["macd"] > 0

    def test_bollinger_bands_calculation(self):
        """测试布林带计算"""
        stage = FactorStage()

        klines = []
        for i in range(30):
            klines.append({
                "date": f"2026-05-{i+1:02d}",
                "close": 100.0 + i * 0.5,
                "high": 102.0 + i * 0.5,
                "low": 99.0 + i * 0.5,
                "open": 100.5 + i * 0.5,
                "volume": 1000000
            })

        data = {
            "symbol": "000001",
            "klines": klines
        }

        result = stage.process(data)
        factors = result["factors"]

        # 布林带上轨 > 中轨 > 下轨
        assert factors["bollinger_upper"] > factors["bollinger_middle"]
        assert factors["bollinger_middle"] > factors["bollinger_lower"]

        # 中轨应该接近MA20
        assert abs(factors["bollinger_middle"] - factors["ma20"]) < 0.01

    def test_atr_calculation(self):
        """测试ATR计算"""
        stage = FactorStage()

        klines = []
        for i in range(30):
            klines.append({
                "date": f"2026-05-{i+1:02d}",
                "close": 100.0 + i * 0.5,
                "high": 105.0 + i * 0.5,  # 高波动
                "low": 95.0 + i * 0.5,
                "open": 100.5 + i * 0.5,
                "volume": 1000000
            })

        data = {
            "symbol": "000001",
            "klines": klines
        }

        result = stage.process(data)
        factors = result["factors"]

        # ATR应该大于0（有波动）
        assert factors["atr14"] > 0

        # 高波动情况下，ATR应该接近10（high-low=10）
        assert factors["atr14"] > 5

    def test_volume_ratio_calculation(self):
        """测试成交量比率计算"""
        stage = FactorStage()

        klines = []
        for i in range(30):
            # 最后一天成交量放大
            volume = 1000000 if i < 29 else 2000000
            klines.append({
                "date": f"2026-05-{i+1:02d}",
                "close": 100.0 + i * 0.5,
                "high": 102.0 + i * 0.5,
                "low": 99.0 + i * 0.5,
                "open": 100.5 + i * 0.5,
                "volume": volume
            })

        data = {
            "symbol": "000001",
            "klines": klines
        }

        result = stage.process(data)
        factors = result["factors"]

        # 成交量比率应该接近2（最后一天是前5天平均的2倍）
        assert factors["volume_ratio"] > 1.5
        assert factors["volume_ratio"] < 2.5

    def test_insufficient_data_warning(self):
        """测试数据不足的警告"""
        stage = FactorStage()

        # 只有10条数据（少于20）
        klines = []
        for i in range(10):
            klines.append({
                "date": f"2026-05-{i+1:02d}",
                "close": 100.0 + i,
                "high": 102.0 + i,
                "low": 99.0 + i,
                "open": 100.5 + i,
                "volume": 1000000
            })

        data = {
            "symbol": "000001",
            "klines": klines
        }

        # 应该能够处理，但短周期因子可能返回None
        result = stage.process(data)
        assert "factors" in result

    def test_missing_required_column(self):
        """测试缺少必要列"""
        stage = FactorStage()

        # 缺少 open 列
        klines = []
        for i in range(30):
            klines.append({
                "date": f"2026-05-{i+1:02d}",
                "close": 100.0 + i,
                "high": 102.0 + i,
                "low": 99.0 + i
                # 缺少 open 和 volume
            })

        data = {
            "symbol": "000001",
            "klines": klines
        }

        with pytest.raises(ValueError, match="Missing required column: open"):
            stage.process(data)

    def test_factor_values_are_numeric(self):
        """测试所有因子值都是数值类型"""
        stage = FactorStage()

        klines = []
        for i in range(30):
            klines.append({
                "date": f"2026-05-{i+1:02d}",
                "close": 100.0 + i * 0.5,
                "high": 102.0 + i * 0.5,
                "low": 99.0 + i * 0.5,
                "open": 100.5 + i * 0.5,
                "volume": 1000000 + i * 10000
            })

        data = {
            "symbol": "000001",
            "klines": klines
        }

        result = stage.process(data)
        factors = result["factors"]

        # 所有因子值都应该是数值类型
        for key, value in factors.items():
            assert isinstance(value, (int, float)), (
                f"Factor {key} is not numeric: {type(value)}"
            )
            assert not pd.isna(value), f"Factor {key} is NaN"
