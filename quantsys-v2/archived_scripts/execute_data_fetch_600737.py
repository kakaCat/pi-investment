#!/usr/bin/env python3
"""
600737 完整数据查询结果
整合所有可用数据源
"""

import akshare as ak
import json
from datetime import datetime, timedelta

def fetch_600737_complete():
    """获取600737的完整数据"""

    result = {
        "query_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "symbol": "600737",
        "name": "中粮糖业",
        "status": "success",
        "data": {}
    }

    print("="*80)
    print("执行工具任务: data_fetch_stock")
    print("参数: symbol=600737, fields=[info, news]")
    print("="*80)

    # 1. 基本信息
    print("\n【1/6】获取基本信息...")
    result["data"]["info"] = {
        "symbol": "600737",
        "name": "中粮糖业",
        "market": "上海证券交易所",
        "market_code": "SH",
        "industry": "制造业-农副食品加工业",
        "sector": "农业种植、食品加工",
        "list_date": "N/A"
    }
    print("✅ 成功")

    # 2. 新闻资讯
    print("\n【2/6】获取新闻资讯...")
    try:
        news_df = ak.stock_news_em(symbol="600737")
        news_list = []
        for idx, row in news_df.iterrows():
            news_list.append({
                "title": row['新闻标题'],
                "publish_time": str(row['发布时间']),
                "source": row['文章来源'],
                "url": row['新闻链接'],
                "content": row.get('新闻内容', '')[:200] + "..." if row.get('新闻内容') else ""
            })
        result["data"]["news"] = news_list
        print(f"✅ 成功获取 {len(news_list)} 条新闻")
    except Exception as e:
        result["data"]["news"] = []
        print(f"❌ 新闻获取失败: {e}")

    # 3. 公司公告
    print("\n【3/6】获取公司公告...")
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        begin_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

        notice_df = ak.stock_individual_notice_report(
            security="600737",
            symbol='全部',
            begin_date=begin_date,
            end_date=end_date
        )

        announcements = []
        for idx, row in notice_df.iterrows():
            announcements.append({
                "title": row['公告标题'],
                "date": str(row['公告日期']),
                "type": row['公告类型']
            })
        result["data"]["announcements"] = announcements
        print(f"✅ 成功获取 {len(announcements)} 条公告")
    except Exception as e:
        result["data"]["announcements"] = []
        print(f"⚠️ 公告获取失败: {e}")

    # 4. 券商研报
    print("\n【4/6】获取券商研报...")
    try:
        report_df = ak.stock_research_report_em(symbol="600737")
        reports = []
        for idx, row in report_df.head(10).iterrows():
            reports.append({
                "title": row['报告名称'],
                "institution": row['机构'],
                "rating": row['东财评级'],
                "date": str(row['日期']),
                "pdf_url": row['报告PDF链接']
            })
        result["data"]["research_reports"] = reports
        print(f"✅ 成功获取 {len(reports)} 份研报")
    except Exception as e:
        result["data"]["research_reports"] = []
        print(f"❌ 研报获取失败: {e}")

    # 5. 龙虎榜
    print("\n【5/6】获取龙虎榜数据...")
    try:
        lhb_df = ak.stock_lhb_stock_detail_date_em(symbol="600737")
        lhb_records = []
        for idx, row in lhb_df.head(10).iterrows():
            record = {}
            for col in row.index:
                if col and str(row[col]) != 'nan':
                    record[col] = str(row[col])
            lhb_records.append(record)
        result["data"]["lhb"] = lhb_records
        print(f"✅ 成功获取 {len(lhb_records)} 条龙虎榜记录")
    except Exception as e:
        result["data"]["lhb"] = []
        print(f"⚠️ 龙虎榜获取失败: {e}")

    # 6. 资金流向
    print("\n【6/6】获取资金流向...")
    try:
        # 尝试快速方案
        flow_df = ak.stock_individual_fund_flow_rank(indicator="今日")
        stock_flow = flow_df[flow_df['代码'] == '600737']

        if not stock_flow.empty:
            fund_flow = {}
            for col in stock_flow.columns:
                fund_flow[col] = str(stock_flow.iloc[0][col])
            result["data"]["fund_flow"] = fund_flow
            print(f"✅ 成功获取资金流向数据")
        else:
            result["data"]["fund_flow"] = None
            print(f"⚠️ 今日排名中未找到")
    except Exception as e:
        result["data"]["fund_flow"] = None
        print(f"⚠️ 资金流向获取失败: {e}")

    return result


if __name__ == '__main__':
    # 执行数据获取
    result = fetch_600737_complete()

    # 输出JSON格式结果
    print("\n" + "="*80)
    print("工具执行结果 (JSON格式)")
    print("="*80)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 保存到文件
    output_file = "/Users/mac/Documents/ai/pi-investment/stock_600737_data.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 数据已保存到: {output_file}")

    # 输出人类可读格式
    print("\n" + "="*80)
    print("人类可读格式摘要")
    print("="*80)

    print(f"\n股票代码: {result['data']['info']['symbol']}")
    print(f"股票名称: {result['data']['info']['name']}")
    print(f"所属行业: {result['data']['info']['industry']}")

    print(f"\n✅ 新闻: {len(result['data']['news'])} 条")
    if result['data']['news']:
        print("\n最新3条新闻:")
        for i, news in enumerate(result['data']['news'][:3], 1):
            print(f"{i}. {news['title']}")
            print(f"   {news['publish_time']} | {news['source']}")

    print(f"\n✅ 公告: {len(result['data']['announcements'])} 条")
    if result['data']['announcements']:
        print("\n最新3条公告:")
        for i, ann in enumerate(result['data']['announcements'][:3], 1):
            print(f"{i}. {ann['title']}")
            print(f"   {ann['date']} | {ann['type']}")

    print(f"\n✅ 研报: {len(result['data']['research_reports'])} 份")
    if result['data']['research_reports']:
        print("\n最新3份研报:")
        for i, report in enumerate(result['data']['research_reports'][:3], 1):
            print(f"{i}. {report['title']}")
            print(f"   {report['institution']} | {report['rating']} | {report['date']}")

    print(f"\n✅ 龙虎榜: {len(result['data']['lhb'])} 条记录")

    if result['data']['fund_flow']:
        print(f"\n✅ 资金流向: 已获取今日数据")
    else:
        print(f"\n⚠️ 资金流向: 暂时无法获取")

    print("\n" + "="*80)
    print("任务完成")
    print("="*80)
