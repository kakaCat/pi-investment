#!/usr/bin/env python
"""竞争分析功能端到端测试脚本

直接调用 service 层进行功能验证，无需启动 FastAPI 服务器。
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from adapters.outbound.repositories.competition_repository import CompetitionRepository
from domain.competition.service import CompetitionAnalysisService
import json


def test_competition_analysis(symbol: str):
    """测试竞争分析功能"""
    print(f"\n{'='*60}")
    print(f"测试竞争分析：{symbol}")
    print(f"{'='*60}\n")

    # 创建服务实例
    repo = CompetitionRepository()
    service = CompetitionAnalysisService(repo)

    # 执行分析
    result = service.analyze(symbol, include_financial=True)

    # 输出结果
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 验证结果
    if "error" in result:
        print(f"\n❌ 分析失败: {result['error']}")
        return False

    print(f"\n✅ 分析成功")
    print(f"公司: {result['company_name']}")
    print(f"行业: {result['industry']['level2']}")
    print(f"行业排名: {result['market_size']['industry_rank']}")
    print(f"市占率: {result['market_size']['market_share']:.2f}%")
    print(f"竞争对手数: {len(result['competitors'])}")
    print(f"竞争优势: {len(result['competitive_advantages'])} 条")
    print(f"竞争劣势: {len(result['competitive_disadvantages'])} 条")
    print(f"\n摘要: {result['summary']}")

    return True


if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "600519",  # 贵州茅台（白酒龙头）
        "000858",  # 五粮液（白酒第二）
        "601398",  # 工商银行（银行龙头）
    ]

    success_count = 0
    for symbol in test_cases:
        try:
            if test_competition_analysis(symbol):
                success_count += 1
        except Exception as e:
            print(f"\n❌ 测试 {symbol} 出现异常: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"测试完成: {success_count}/{len(test_cases)} 通过")
    print(f"{'='*60}")

    sys.exit(0 if success_count == len(test_cases) else 1)
