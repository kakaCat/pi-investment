"""
端到端测试：分红数据 API

测试所有三种模式的完整流程
"""
import requests
import time
import json


BASE_URL = "http://127.0.0.1:5001"


def test_single_mode():
    """测试单股查询模式"""
    print("\n=== Test 1: Single Mode ===")

    start = time.time()
    response = requests.get(f"{BASE_URL}/api/stock/000001.SH/dividends?years=5")
    elapsed = time.time() - start

    print(f"Status: {response.status_code}")
    print(f"Response Time: {elapsed:.2f}s")

    if response.status_code == 200:
        data = response.json()
        print(f"Success: {data.get('success')}")
        print(f"Symbol: {data.get('symbol')}")
        print(f"Name: {data.get('name')}")
        print(f"Total Records: {data.get('total_records')}")

        if data.get('summary'):
            summary = data['summary']
            print(f"Consecutive Years: {summary.get('consecutive_years')}")
            print(f"Avg Yield: {summary.get('avg_yield')}%")
            print(f"Total Cash Dividend: {summary.get('total_cash_dividend')}")

        if data.get('dividends'):
            print(f"First Dividend: {data['dividends'][0].get('fiscal_year')} - {data['dividends'][0].get('cash_per_share')}元")

        # 验证
        assert data['success'] is True
        assert data['symbol'] == '000001.SH'
        assert 'dividends' in data
        assert elapsed < 5.0, f"Response time {elapsed:.2f}s exceeds 5s threshold"

        print("✅ PASS")
        return True
    else:
        print(f"❌ FAIL: {response.text}")
        return False


def test_screen_mode():
    """测试筛选模式"""
    print("\n=== Test 2: Screen Mode ===")

    payload = {
        "min_yield": 3.0,
        "min_years": 3,
        "limit": 10
    }

    start = time.time()
    response = requests.post(
        f"{BASE_URL}/api/dividends/screen",
        json=payload
    )
    elapsed = time.time() - start

    print(f"Status: {response.status_code}")
    print(f"Response Time: {elapsed:.2f}s")

    if response.status_code == 200:
        data = response.json()
        print(f"Success: {data.get('success')}")
        print(f"Total: {data.get('total')}")

        if data.get('stocks'):
            print(f"Stocks Count: {len(data['stocks'])}")
            if data['stocks']:
                first = data['stocks'][0]
                print(f"Top Stock: {first.get('name')} ({first.get('symbol')})")
                print(f"  Yield: {first.get('latest_yield')}%")
                print(f"  Consecutive Years: {first.get('consecutive_years')}")

        # 验证
        assert data['success'] is True
        assert 'stocks' in data
        assert len(data['stocks']) <= 10
        assert elapsed < 35.0, f"Response time {elapsed:.2f}s exceeds 35s threshold"

        # 验证排序（按股息率降序）
        if len(data['stocks']) > 1:
            yields = [s['latest_yield'] for s in data['stocks']]
            assert yields == sorted(yields, reverse=True), "Stocks not sorted by yield"

        print("✅ PASS")
        return True
    else:
        print(f"❌ FAIL: {response.text}")
        return False


def test_calendar_mode():
    """测试日历模式"""
    print("\n=== Test 3: Calendar Mode ===")

    start = time.time()
    response = requests.get(
        f"{BASE_URL}/api/dividends/calendar",
        params={
            "start_date": "2026-06-01",
            "end_date": "2026-06-30",
            "event": "ex_dividend"
        }
    )
    elapsed = time.time() - start

    print(f"Status: {response.status_code}")
    print(f"Response Time: {elapsed:.2f}s")

    if response.status_code == 200:
        data = response.json()
        print(f"Success: {data.get('success')}")
        print(f"Period: {data.get('period')}")
        print(f"Event Type: {data.get('event_type')}")
        print(f"Total Events: {data.get('total')}")

        if data.get('events'):
            print(f"Events Count: {len(data['events'])}")
            if data['events']:
                first = data['events'][0]
                print(f"First Event: {first.get('date')} - {first.get('name')}")

        # 验证
        assert data['success'] is True
        assert data['event_type'] == '除权除息日'
        assert 'events' in data
        assert elapsed < 25.0, f"Response time {elapsed:.2f}s exceeds 25s threshold"

        # 验证日期排序
        if len(data['events']) > 1:
            dates = [e['date'] for e in data['events']]
            assert dates == sorted(dates), "Events not sorted by date"

        print("✅ PASS")
        return True
    else:
        print(f"❌ FAIL: {response.text}")
        return False


def test_error_handling_invalid_symbol():
    """测试错误处理：无效股票代码"""
    print("\n=== Test 4: Error Handling - Invalid Symbol ===")

    response = requests.get(f"{BASE_URL}/api/stock/INVALID/dividends")

    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"Success: {data.get('success')}")
        print(f"Error: {data.get('error')}")

        # 验证
        assert data['success'] is False
        assert 'error' in data

        print("✅ PASS")
        return True
    else:
        print(f"❌ FAIL: Unexpected status code")
        return False


def test_error_handling_missing_params():
    """测试错误处理：缺少必需参数"""
    print("\n=== Test 5: Error Handling - Missing Parameters ===")

    response = requests.get(f"{BASE_URL}/api/dividends/calendar")

    print(f"Status: {response.status_code}")

    # 应该返回 400
    if response.status_code == 400:
        data = response.json()
        print(f"Success: {data.get('success')}")
        print(f"Error: {data.get('error')}")

        # 验证
        assert data['success'] is False
        assert 'error' in data

        print("✅ PASS")
        return True
    else:
        print(f"❌ FAIL: Expected 400, got {response.status_code}")
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Dividend Data API - End-to-End Tests")
    print("=" * 60)

    results = []

    # 运行所有测试
    results.append(("Single Mode", test_single_mode()))
    results.append(("Screen Mode", test_screen_mode()))
    results.append(("Calendar Mode", test_calendar_mode()))
    results.append(("Error Handling - Invalid Symbol", test_error_handling_invalid_symbol()))
    results.append(("Error Handling - Missing Params", test_error_handling_missing_params()))

    # 汇总结果
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name}: {status}")

    print(f"\nTotal: {passed}/{total} passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
