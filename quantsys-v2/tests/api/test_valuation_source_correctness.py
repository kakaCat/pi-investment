"""估值数据源正确性回归测试（离线，mock requests，不联网）。

覆盖 Lead 实测的两个真实事故点：

1. 新浪 Market_Center.getHQNodeData 会**忽略 symbol 参数**，返回 hs_a 首行
   bj920000（安徽凤凰，trade=13.200 / per=18.333 / pb=1.772）。旧代码直接取
   data[0] 当请求标的返回 —— 本测试要求该源必须判失败，且整体估值绝不返回他股数据。
2. 东财 push2 字段语义 + ×100 定点缩放：f43 价格、f162 PE、f167 PB 必须 /100，
   f116 总市值 / f117 流通市值 单位是元（不缩放）。样例来自 688981 实测响应。

另有新浪 mktcap/nmc「万元 → 元」(*1e4) 单位回归。
"""
from unittest.mock import MagicMock, patch

import pytest

from qs_market_data.adapters.outbound.datasources import manager as ds_manager
from qs_market_data.application.services.valuation_data_service import (
    ValuationDataService,
)

VAL_MODULE = "qs_market_data.application.services.valuation_data_service"

# 新浪对 688981 请求实际返回的首行（北交所 920000 安徽凤凰）
SINA_WRONG_STOCK_ROW = [
    {
        "symbol": "bj920000",
        "code": "920000",
        "name": "安徽凤凰",
        "trade": "13.200",
        "per": 18.333,
        "pb": 1.772,
        "mktcap": 121017.6,
        "nmc": 76023.981,
    }
]

# 东财 688981 实测响应（2026-10-19）
EASTMONEY_688981 = {
    "rc": 0,
    "rt": 4,
    "svr": 183640490,
    "lt": 1,
    "full": 1,
    "dlmkts": "",
    "dsc": "0",
    "data": {
        "f43": 9970,
        "f57": "688981",
        "f58": "中芯国际",
        "f116": 853669476327.3,
        "f117": 199459212727.3,
        "f162": 9554,
        "f167": 498,
    },
}


class _FakeResponse:
    """最小 requests.Response 替身。"""

    def __init__(self, payload=None, text=""):
        self._payload = payload
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.fixture
def service():
    """构造真实实例，但把 DataProviderManager 换成 Mock（避免初始化真实 provider 网格）。"""
    with patch.object(ds_manager, "get_data_provider_manager", return_value=MagicMock()):
        return ValuationDataService()


class TestSinaSourceMustNotReturnWrongStock:
    def test_wrong_row_marks_sina_source_failed(self, service):
        with patch(
            f"{VAL_MODULE}.requests.get",
            return_value=_FakeResponse(SINA_WRONG_STOCK_ROW),
        ):
            result = service._get_from_sina("688981")

        assert result["success"] is False
        assert "不匹配" in result["error"]
        assert "bj920000" in result["error"]

    def test_get_valuation_never_returns_other_stock(self, service):
        """新浪返回他股 + 其余源不可用 → 整体必须失败，绝不返回 13.2 / 12.1 万亿。"""
        import requests as requests_module

        def fake_get(url, *args, **kwargs):
            if "sina" in url:
                return _FakeResponse(SINA_WRONG_STOCK_ROW)
            raise requests_module.ConnectionError("offline: 其余源在本次测试中不可用")

        service.provider_manager.get_market_spot.return_value = {
            "success": False,
            "error": "offline",
            "data": None,
        }

        with patch(f"{VAL_MODULE}.requests.get", side_effect=fake_get):
            result = service.get_valuation("688981")

        assert result["success"] is False
        assert result["data"] is None
        assert "sina" in result["source_errors"]
        assert "不匹配" in result["source_errors"]["sina"]

    def test_sina_mktcap_unit_is_wan_yuan(self, service):
        """新浪 mktcap/nmc 单位是万元，必须 *1e4（而非 *1e8）。"""
        valid_row = [
            {
                "symbol": "sh688981",
                "code": "688981",
                "name": "中芯国际",
                "trade": "99.700",
                "per": 95.54,
                "pb": 4.98,
                "mktcap": 85366947.63273,  # 万元
                "nmc": 19945921.27273,     # 万元
            }
        ]

        with patch(
            f"{VAL_MODULE}.requests.get", return_value=_FakeResponse(valid_row)
        ):
            result = service._get_from_sina("688981")

        assert result["success"] is True
        valuation = result["data"]["valuation"]
        assert valuation["current_price"] == pytest.approx(99.7)
        assert valuation["market_cap"] == pytest.approx(8.536694763273e11)
        assert valuation["circulating_market_cap"] == pytest.approx(1.994592127273e11)


class TestEastmoneyFieldMapping:
    def test_fields_and_scaling(self, service):
        with patch(
            f"{VAL_MODULE}.requests.get",
            return_value=_FakeResponse(EASTMONEY_688981),
        ) as mock_get:
            result = service._get_from_eastmoney("688981")

        assert result["success"] is True
        assert result["data"]["source"] == "eastmoney"
        assert result["data"]["symbol"] == "688981"

        valuation = result["data"]["valuation"]
        assert valuation["current_price"] == pytest.approx(99.7)
        assert valuation["pe"] == pytest.approx(95.54)
        assert valuation["pb"] == pytest.approx(4.98)
        assert valuation["market_cap"] == pytest.approx(8.536694763273e11)
        assert valuation["circulating_market_cap"] == pytest.approx(1.994592127273e11)

        # 请求参数必须是 1.688981（沪市）且包含所需字段
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["secid"] == "1.688981"
        assert "f43" in kwargs["params"]["fields"]
        assert "f116" in kwargs["params"]["fields"]

    def test_mismatched_f57_marks_source_failed(self, service):
        wrong = {
            "rc": 0,
            "data": {
                "f43": 1320,
                "f57": "920000",
                "f58": "安徽凤凰",
                "f116": 1210176000.0,
                "f117": 760239810.0,
                "f162": 1833,
                "f167": 177,
            },
        }
        with patch(
            f"{VAL_MODULE}.requests.get", return_value=_FakeResponse(wrong)
        ):
            result = service._get_from_eastmoney("688981")

        assert result["success"] is False
        assert "不匹配" in result["error"]


class TestSourcePriority:
    def test_eastmoney_is_tried_first(self, service):
        """东财优先：首个请求必须打 push2，成功后立即返回 99.7。"""
        import requests as requests_module

        requested_urls = []

        def fake_get(url, *args, **kwargs):
            requested_urls.append(url)
            if "push2.eastmoney.com" in url:
                return _FakeResponse(EASTMONEY_688981)
            raise requests_module.ConnectionError("不应回退到其它源")

        service.provider_manager.get_market_spot.return_value = {
            "success": False,
            "error": "offline",
            "data": None,
        }

        with patch(f"{VAL_MODULE}.requests.get", side_effect=fake_get):
            result = service.get_valuation("688981")

        assert result["success"] is True
        assert result["data"]["source"] == "eastmoney"
        assert result["data"]["valuation"]["current_price"] == pytest.approx(99.7)
        assert requested_urls and "push2.eastmoney.com" in requested_urls[0]

    def test_eastmoney_failure_fails_over_to_validated_source(self, service):
        """东财失败 → 继续 failover；新浪行若校验通过仍可作为兜底。"""
        import requests as requests_module

        valid_sina_row = [
            {
                "symbol": "sh688981",
                "code": "688981",
                "name": "中芯国际",
                "trade": "99.700",
                "per": 95.54,
                "pb": 4.98,
                "mktcap": 85366947.63273,
                "nmc": 19945921.27273,
            }
        ]

        def fake_get(url, *args, **kwargs):
            if "push2.eastmoney.com" in url:
                raise requests_module.ConnectionError("offline: eastmoney")
            if "sina" in url:
                return _FakeResponse(valid_sina_row)
            raise requests_module.ConnectionError("offline: 其余源")

        with patch(f"{VAL_MODULE}.requests.get", side_effect=fake_get):
            result = service.get_valuation("688981")

        assert result["success"] is True
        assert result["data"]["source"] == "sina"
        assert result["data"]["valuation"]["current_price"] == pytest.approx(99.7)
