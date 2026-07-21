"""Test EastMoney adapter and source."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Direct import to avoid __init__.py issues
import importlib.util

def load_module(name, path):
    """Load module directly from file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_eastmoney_adapter():
    """Test EastMoneyAdapter directly."""
    print("=" * 60)
    print("Testing EastMoneyAdapter")
    print("=" * 60)

    # Load adapter
    adapter_module = load_module('eastmoney_adapter', 'quantlib/adapters/eastmoney_adapter.py')
    EastMoneyAdapter = adapter_module.EastMoneyAdapter

    adapter = EastMoneyAdapter()

    # Test real-time quotes
    print("\n1. Testing real-time quotes...")
    symbols = ["600000.SH", "000001.SZ"]
    quotes = adapter.get_realtime_quote(symbols)

    if quotes:
        print(f"✓ Got {len(quotes)} quotes")
        for symbol, quote in quotes.items():
            print(f"  {symbol}: {quote.get('name')} - ¥{quote.get('price')} ({quote.get('change_pct')}%)")
    else:
        print("✗ No quotes returned")

    # Test stock info
    print("\n2. Testing stock info...")
    info = adapter.get_stock_info("600000.SH")
    if info:
        print(f"✓ Stock info: {info}")
    else:
        print("✗ No stock info")

    # Test sector list
    print("\n3. Testing sector list...")
    sectors = adapter.get_sector_list()
    if sectors:
        print(f"✓ Got {len(sectors)} sectors")
        for sector in sectors[:5]:
            print(f"  {sector.get('code')}: {sector.get('name')}")
    else:
        print("✗ No sectors returned")


def test_eastmoney_http():
    """Test EastMoney API directly via HTTP."""
    print("\n" + "=" * 60)
    print("Testing EastMoney API (HTTP)")
    print("=" * 60)

    import requests

    # Test quote API
    print("\n1. Testing quote API...")
    url = "http://push2.eastmoney.com/api/qt/stock/get"
    params = {
        'secid': '1.600000',  # 浦发银行
        'fields': 'f57,f58,f43,f44,f45,f46,f47,f48,f60,f169,f170',
        'ut': 'fa5fd1943c7b386f172d6893dbfba10b'
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Response: {data}")
            if data.get('rc') == 0:
                print("  ✓ API is accessible")
            else:
                print(f"  ✗ API returned error code: {data.get('rc')}")
        else:
            print(f"  ✗ HTTP error: {response.status_code}")
    except Exception as e:
        print(f"  ✗ Request failed: {e}")

    # Test sector API
    print("\n2. Testing sector API...")
    url = "http://push2.eastmoney.com/api/qt/clist/get"
    params = {
        'pn': '1',
        'pz': '10',
        'po': '1',
        'np': '1',
        'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
        'fltt': '2',
        'invt': '2',
        'fid': 'f3',
        'fs': 'm:90+t:2+f:!50',
        'fields': 'f12,f14,f3'
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if data.get('rc') == 0 and data.get('data'):
                sectors = data['data'].get('diff', [])
                print(f"  ✓ Got {len(sectors)} sectors")
                for sector in sectors[:3]:
                    print(f"    {sector.get('f12')}: {sector.get('f14')}")
            else:
                print(f"  ✗ No sector data")
        else:
            print(f"  ✗ HTTP error: {response.status_code}")
    except Exception as e:
        print(f"  ✗ Request failed: {e}")


if __name__ == "__main__":
    try:
        test_eastmoney_http()
        test_eastmoney_adapter()

        print("\n" + "=" * 60)
        print("✓ EastMoney tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
