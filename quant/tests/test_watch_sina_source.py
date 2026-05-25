from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from quantsys.watch.quote_sources import SinaRealtimeQuoteSource


class FakeResponse:
    def __init__(self, text: str):
        self.text = text
        self.encoding = None


class FakeHttpClient:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.calls = []

    def get(self, url: str, params=None, headers=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return FakeResponse(self.response_text)


def test_sina_realtime_quote_source_parses_price_and_metadata():
    http = FakeHttpClient(
        'var hq_str_sh600036="招商银行,35.20,35.00,35.25,35.40,34.80,35.20,0.20,1000000,35000000,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2026-05-19,10:30:00";'
    )
    source = SinaRealtimeQuoteSource(http_client=http)

    quote = source.fetch_realtime_quote("600036")

    assert http.calls[0]["url"] == "https://hq.sinajs.cn/list=sh600036"
    assert quote["symbol"] == "600036"
    assert quote["name"] == "招商银行"
    assert quote["price"] == 35.25
    assert quote["source"] == "sina"
    assert quote["latency_ms"] >= 0
    assert quote["stale"] is False


def test_sina_realtime_quote_source_raises_on_invalid_payload():
    http = FakeHttpClient('var hq_str_sh600036="";')
    source = SinaRealtimeQuoteSource(http_client=http)

    try:
        source.fetch_realtime_quote("600036")
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected RuntimeError")

    assert "未找到" in message
