#!/usr/bin/env python3
"""
M3-2 策略回测矩阵执行脚本
==========================

目标：5 策略 × 3 环境 = 15 次回测，筛选生产策略池（样本外夏普>1）

策略池：
  1. V13 XGBoost Multi-Factor（ML多因子，5日调仓）
  2. V14 XGBoost Multi-Factor Optimized（ML多因子，30日调仓，牛市优化）
  3. Strategy 272（技术指标突破-严格）
  4. Strategy 273（技术指标突破-宽松）
  5. Strategy 274 ML（Random Forest 预测）

环境定义：
  - 牛市：2023-01-01 ~ 2023-06-30（上证指数预期 +5%）
  - 熊市：2022-04-01 ~ 2022-10-31（上证指数预期 -15%）
  - 震荡：2021-07-01 ~ 2021-12-31（上证指数预期 ±5%）

依赖：
  - quantsys-v2 后端运行（5001端口）
  - 数据库包含目标区间的 K 线数据（需提前回填）

输出：
  - 15 次回测结果 JSON
  - 策略排名表（Markdown）
  - 生产策略池建议

作者：PI 投资顾问·投资脑
日期：2026-08-26
"""

import sys
import json
import requests
from typing import Dict, List, Any
from datetime import datetime
from pathlib import Path

# ============ 配置 ============

QUANTSYS_V2_BASE_URL = "http://localhost:5001"

# 策略配置（从 quantsys-v2 代码库提取）
STRATEGIES = [
    {
        "id": 13,
        "name": "V13 XGBoost Multi-Factor",
        "code": "v13_strategy",
        "type": "ML多因子",
        "适用": "通用环境"
    },
    {
        "id": 14,
        "name": "V14 XGBoost Multi-Factor Optimized",
        "code": "v14_strategy",
        "type": "ML多因子",
        "适用": "牛市"
    },
    {
        "id": 272,
        "name": "Strategy 272",
        "code": "strategy_272",
        "type": "技术指标-严格",
        "适用": "震荡/弱势"
    },
    {
        "id": 273,
        "name": "Strategy 273",
        "code": "strategy_273",
        "type": "技术指标-宽松",
        "适用": "牛市"
    },
    {
        "id": 274,
        "name": "Strategy 274 ML",
        "code": "strategy_274_ml",
        "type": "ML预测",
        "适用": "通用环境"
    },
]

# 环境配置
ENVIRONMENTS = [
    {"name": "牛市", "start": "2023-01-01", "end": "2023-06-30", "expected_return": 5.0},
    {"name": "熊市", "start": "2022-04-01", "end": "2022-10-31", "expected_return": -15.0},
    {"name": "震荡", "start": "2021-07-01", "end": "2021-12-31", "expected_return": 0.0},
]

INITIAL_CAPITAL = 100000  # 初始资金 10万
OUTPUT_DIR = Path(__file__).parent.parent / "output" / "m3-2"


# ============ 核心函数 ============

def validate_environment(env: Dict) -> Dict[str, Any]:
    """验证环境定义：检查 K 线数据覆盖 + 计算实际收益率"""
    print(f"\n验证环境：{env['name']} ({env['start']} ~ {env['end']})")
    
    # 获取上证指数 K 线
    url = f"{QUANTSYS_V2_BASE_URL}/api/stock/000001/klines"
    params = {
        "start_date": env['start'],
        "end_date": env['end'],
        "period": "daily"
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        if not data.get('klines') or len(data['klines']) == 0:
            return {"valid": False, "error": "无 K 线数据"}
        
        klines = data['klines']
        first_price = klines[0]['close']
        last_price = klines[-1]['close']
        actual_return = ((last_price - first_price) / first_price) * 100
        
        result = {
            "valid": True,
            "bars": len(klines),
            "期间": f"{klines[0]['trade_date']} ~ {klines[-1]['trade_date']}",
            "指数收益": round(actual_return, 2),
            "符合定义": abs(actual_return - env['expected_return']) < 10,  # 允许 ±10% 偏差
        }
        
        print(f"  ✅ {result['bars']} 根K线 | 收益: {result['指数收益']}% (预期 {env['expected_return']}%)")
        return result
        
    except Exception as e:
        print(f"  ❌ 验证失败: {e}")
        return {"valid": False, "error": str(e)}


def run_backtest(strategy: Dict, env: Dict) -> Dict[str, Any]:
    """执行单次回测"""
    print(f"\n回测: {strategy['name']} × {env['name']}")
    
    url = f"{QUANTSYS_V2_BASE_URL}/api/strategies/{strategy['id']}/backtest"
    payload = {
        "start_date": env['start'],
        "end_date": env['end'],
        "initial_capital": INITIAL_CAPITAL,
        "mode": "backtest"
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=600)  # 10分钟超时
        result = resp.json()
        
        if not result.get('success', False):
            error = result.get('error', '未知错误')
            print(f"  ❌ 回测失败: {error}")
            return {
                "success": False,
                "strategy": strategy['name'],
                "environment": env['name'],
                "error": error
            }
        
        # 提取关键指标
        metrics = result.get('result', {})
        output = {
            "success": True,
            "strategy": strategy['name'],
            "strategy_id": strategy['id'],
            "environment": env['name'],
            "收益率": round(metrics.get('total_return_pct', 0), 2),
            "最大回撤": round(metrics.get('max_drawdown_pct', 0), 2),
            "夏普比率": round(metrics.get('sharpe_ratio', 0), 2),
            "胜率": round(metrics.get('win_rate', 0) * 100, 1),
            "交易次数": metrics.get('trade_count', 0),
        }
        
        print(f"  ✅ 收益: {output['收益率']}% | 回撤: {output['最大回撤']}% | 夏普: {output['夏普比率']} | 胜率: {output['胜率']}%")
        return output
        
    except requests.Timeout:
        print(f"  ❌ 回测超时（>10分钟）")
        return {"success": False, "strategy": strategy['name'], "environment": env['name'], "error": "超时"}
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return {"success": False, "strategy": strategy['name'], "environment": env['name'], "error": str(e)}


def generate_matrix_report(results: List[Dict]) -> str:
    """生成回测矩阵 Markdown 报告"""
    # 按策略分组
    strategy_results = {}
    for r in results:
        if not r['success']:
            continue
        s_name = r['strategy']
        if s_name not in strategy_results:
            strategy_results[s_name] = {}
        strategy_results[s_name][r['environment']] = r
    
    # 计算跨环境平均指标
    rankings = []
    for s_name, envs in strategy_results.items():
        avg_sharpe = sum(e['夏普比率'] for e in envs.values()) / len(envs)
        avg_return = sum(e['收益率'] for e in envs.values()) / len(envs)
        max_drawdown = max(e['最大回撤'] for e in envs.values())
        
        rankings.append({
            "策略": s_name,
            "平均夏普": round(avg_sharpe, 2),
            "平均收益": round(avg_return, 2),
            "最大回撤": round(max_drawdown, 2),
            "环境数": len(envs),
        })
    
    # 按夏普排序
    rankings.sort(key=lambda x: x['平均夏普'], reverse=True)
    
    # 生成 Markdown
    report = ["# M3-2 策略回测矩阵报告", ""]
    report.append(f"**执行时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**策略数量**: {len(STRATEGIES)}")
    report.append(f"**环境数量**: {len(ENVIRONMENTS)}")
    report.append(f"**回测总数**: {len(results)} (成功: {sum(1 for r in results if r['success'])})")
    report.append("")
    
    # 策略排名表
    report.append("## 策略排名（按平均夏普比率）")
    report.append("")
    report.append("| 排名 | 策略 | 平均夏普 | 平均收益(%) | 最大回撤(%) | 生产级 |")
    report.append("|------|------|----------|------------|------------|--------|")
    
    for i, r in enumerate(rankings, 1):
        production_ready = "✅" if r['平均夏普'] > 1.0 and r['最大回撤'] < 20 else "❌"
        report.append(f"| {i} | {r['策略']} | {r['平均夏普']} | {r['平均收益']} | {r['最大回撤']} | {production_ready} |")
    
    report.append("")
    
    # 详细矩阵
    report.append("## 详细回测矩阵")
    report.append("")
    
    for s_name, envs in strategy_results.items():
        report.append(f"### {s_name}")
        report.append("")
        report.append("| 环境 | 收益率 | 最大回撤 | 夏普比率 | 胜率 | 交易次数 |")
        report.append("|------|--------|----------|----------|------|----------|")
        
        for env_name in ["牛市", "熊市", "震荡"]:
            if env_name in envs:
                e = envs[env_name]
                report.append(f"| {env_name} | {e['收益率']}% | {e['最大回撤']}% | {e['夏普比率']} | {e['胜率']}% | {e['交易次数']} |")
            else:
                report.append(f"| {env_name} | - | - | - | - | - |")
        
        report.append("")
    
    # 生产策略池建议
    report.append("## 生产策略池建议")
    report.append("")
    prod_strategies = [r for r in rankings if r['平均夏普'] > 1.0 and r['最大回撤'] < 20]
    
    if len(prod_strategies) >= 3:
        report.append(f"✅ **筛选出 {len(prod_strategies)} 个生产策略**（夏普>1 且回撤<20%）：")
        report.append("")
        for s in prod_strategies:
            report.append(f"- **{s['策略']}**: 夏普 {s['平均夏普']}, 收益 {s['平均收益']}%, 回撤 {s['最大回撤']}%")
    else:
        report.append(f"⚠️ **仅筛选出 {len(prod_strategies)} 个生产策略**（目标 ≥3）")
        report.append("")
        report.append("**建议**:")
        report.append("- 放宽筛选标准（如夏普>0.8 或回撤<25%）")
        report.append("- 优化现有策略参数")
        report.append("- 增加新策略候选")
    
    return "\n".join(report)


# ============ 主流程 ============

def main():
    print("=" * 60)
    print("M3-2 策略回测矩阵执行")
    print("=" * 60)
    
    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 步骤 1: 验证环境
    print("\n【步骤 1/3】验证市场环境定义")
    env_validations = {}
    for env in ENVIRONMENTS:
        env_validations[env['name']] = validate_environment(env)
    
    invalid_envs = [name for name, v in env_validations.items() if not v['valid']]
    if invalid_envs:
        print(f"\n❌ 以下环境数据不足，无法回测: {', '.join(invalid_envs)}")
        print("请先运行数据回填脚本补充 K 线数据")
        sys.exit(1)
    
    # 步骤 2: 执行回测矩阵
    print("\n【步骤 2/3】执行回测矩阵 (15 次回测)")
    results = []
    
    for strategy in STRATEGIES:
        for env in ENVIRONMENTS:
            result = run_backtest(strategy, env)
            results.append(result)
            
            # 保存中间结果（防止中途失败丢失）
            interim_file = OUTPUT_DIR / f"interim_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(interim_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
    
    # 步骤 3: 生成报告
    print("\n【步骤 3/3】生成报告")
    
    # 保存完整结果 JSON
    results_file = OUTPUT_DIR / f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  结果已保存: {results_file}")
    
    # 生成 Markdown 报告
    report = generate_matrix_report(results)
    report_file = OUTPUT_DIR / f"backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  报告已保存: {report_file}")
    
    # 打印摘要
    print("\n" + "=" * 60)
    print("执行完成！")
    print(f"成功: {sum(1 for r in results if r['success'])}/{len(results)}")
    print(f"报告: {report_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
