#!/usr/bin/env python3
"""
诊断 AkShare 数据源问题
测试各个接口的响应时间和可用性
"""
import time
import sys
import json

def test_function(name, func, timeout=10):
    """测试单个函数的响应时间"""
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"{'='*60}")

    start = time.time()
    try:
        result = func()
        elapsed = time.time() - start

        if isinstance(result, dict) and "error" in result:
            print(f"❌ 失败: {result['error']}")
            print(f"⏱️  耗时: {elapsed:.2f}秒")
            return {"name": name, "status": "error", "time": elapsed, "error": result['error']}
        else:
            print(f"✅ 成功")
            print(f"⏱️  耗时: {elapsed:.2f}秒")
            if elapsed > timeout:
                print(f"⚠️  警告: 响应时间超过 {timeout} 秒")
            return {"name": name, "status": "success", "time": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ 异常: {str(e)}")
        print(f"⏱️  耗时: {elapsed:.2f}秒")
        return {"name": name, "status": "exception", "time": elapsed, "error": str(e)}

def main():
    results = []

    # 测试 1: 宏观数据
    def test_macro():
        import akshare as ak
        # PMI
        pmi = ak.macro_china_pmi()
        # CPI
        cpi = ak.macro_china_cpi_yearly()
        # GDP
        gdp = ak.macro_china_gdp()
        return {"pmi": len(pmi), "cpi": len(cpi), "gdp": len(gdp)}

    results.append(test_function("宏观数据 (PMI/CPI/GDP)", test_macro, timeout=15))

    # 测试 2: 北向资金
    def test_north_flow():
        import akshare as ak
        df = ak.stock_em_hsgt_north_net_flow_in(symbol="沪股通")
        return {"rows": len(df)}

    results.append(test_function("北向资金流向", test_north_flow, timeout=10))

    # 测试 3: 融资融券
    def test_margin():
        import akshare as ak
        df = ak.stock_margin_underlying_info_szse(date="20240816")
        return {"rows": len(df)}

    results.append(test_function("融资融券数据", test_margin, timeout=10))

    # 测试 4: 市场新闻（最可能超时的）
    def test_news():
        import akshare as ak
        df = ak.stock_news_em(symbol="全部")
        return {"rows": len(df)}

    results.append(test_function("市场新闻 (东方财富)", test_news, timeout=15))

    # 测试 5: 龙虎榜
    def test_lhb():
        import akshare as ak
        from datetime import datetime, timedelta
        date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        df = ak.stock_lhb_detail_em(start_date=date, end_date=date)
        return {"rows": len(df)}

    results.append(test_function("龙虎榜数据", test_lhb, timeout=10))

    # 测试 6: 实时行情
    def test_realtime():
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        return {"rows": len(df)}

    results.append(test_function("实时行情 (东方财富)", test_realtime, timeout=10))

    # 汇总报告
    print(f"\n\n{'='*60}")
    print("诊断报告汇总")
    print(f"{'='*60}\n")

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    exception_count = sum(1 for r in results if r["status"] == "exception")
    slow_count = sum(1 for r in results if r["time"] > 10)

    print(f"总测试数: {len(results)}")
    print(f"✅ 成功: {success_count}")
    print(f"❌ 失败: {error_count}")
    print(f"💥 异常: {exception_count}")
    print(f"🐌 慢响应 (>10s): {slow_count}\n")

    print("详细结果:")
    for r in results:
        status_icon = {"success": "✅", "error": "❌", "exception": "💥"}[r["status"]]
        time_str = f"{r['time']:.2f}s"
        if r['time'] > 10:
            time_str = f"🐌 {time_str}"
        print(f"  {status_icon} {r['name']:<30} {time_str:>10}")
        if "error" in r:
            print(f"     错误: {r['error'][:80]}")

    # 输出 JSON 供程序读取
    print(f"\n\n{'='*60}")
    print("JSON 输出:")
    print(f"{'='*60}")
    print(json.dumps(results, ensure_ascii=False, indent=2))

    # 返回状态码
    if exception_count > 0 or error_count > len(results) / 2:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    print("AkShare 数据源诊断工具")
    print("=" * 60)
    main()
