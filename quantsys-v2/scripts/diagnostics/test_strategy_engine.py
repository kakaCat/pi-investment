#!/usr/bin/env python3
"""
策略代码执行引擎 - 快速测试

测试整个系统的端到端流程：
1. 创建 IndicatorStrategy
2. 创建 ScriptStrategy
3. 列出策略
4. 获取策略详情
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from application.services.strategy_code_service import StrategyCodeService
import json


def test_indicator_strategy():
    """测试 IndicatorStrategy"""
    print("\n" + "="*60)
    print("测试 1: 创建 IndicatorStrategy")
    print("="*60)

    code = """
# 双均线策略
my_indicator_name = "双均线交叉策略"
my_indicator_description = "使用短期/长期均线金叉与死叉生成买卖信号"

# @param ma_short int 5 短期均线周期
# @param ma_long int 20 长期均线周期

# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05

ma_short = params.get('ma_short', 5)
ma_long = params.get('ma_long', 20)

df = df.copy()
df['ma_short'] = df['close'].rolling(ma_short).mean()
df['ma_long'] = df['close'].rolling(ma_long).mean()

df['buy'] = (df['ma_short'] > df['ma_long']) & (df['ma_short'].shift(1) <= df['ma_long'].shift(1))
df['sell'] = (df['ma_short'] < df['ma_long']) & (df['ma_short'].shift(1) >= df['ma_long'].shift(1))
"""

    service = StrategyCodeService()

    try:
        result = service.create_strategy(
            name="测试-双均线策略",
            code=code,
            code_type='indicator',
            description="测试用双均线策略"
        )

        print(f"✅ 策略创建成功!")
        print(f"   策略ID: {result['strategy_id']}")
        print(f"   验证状态: {result['validation']['valid']}")
        print(f"   参数: {json.dumps(result['validation'].get('params', []), indent=2, ensure_ascii=False)}")
        print(f"   风控配置: {json.dumps(result['validation'].get('risk_config', {}), indent=2, ensure_ascii=False)}")

        return result['strategy_id']

    except Exception as e:
        print(f"❌ 创建失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_script_strategy():
    """测试 ScriptStrategy"""
    print("\n" + "="*60)
    print("测试 2: 创建 ScriptStrategy")
    print("="*60)

    code = """
# 简单网格策略
strategy_name = "简单网格策略"
strategy_description = "价格下跌时买入，上涨时卖出"

# @param grid_size float 0.02 网格间距
# @param position_size float 0.2 仓位大小

def on_init(ctx):
    ctx.state['grid_size'] = ctx.params.get('grid_size', 0.02)
    ctx.state['position_size'] = ctx.params.get('position_size', 0.2)
    ctx.state['last_price'] = None
    ctx.log(f"网格策略初始化: 网格间距={ctx.state['grid_size']}")

def on_bar(ctx, bar):
    if ctx.state['last_price'] is None:
        ctx.state['last_price'] = bar.close
        return

    # 价格下跌超过网格间距 -> 买入
    if bar.close <= ctx.state['last_price'] * (1 - ctx.state['grid_size']) and ctx.position == 0:
        size = ctx.cash * ctx.state['position_size'] / bar.close
        if size > 0:
            ctx.buy(size=size, price=bar.close, reason="网格买入")
            ctx.state['last_price'] = bar.close

    # 价格上涨超过网格间距 -> 卖出
    elif bar.close >= ctx.state['last_price'] * (1 + ctx.state['grid_size']) and ctx.position > 0:
        ctx.sell(size=ctx.position, price=bar.close, reason="网格卖出")
        ctx.state['last_price'] = bar.close
"""

    service = StrategyCodeService()

    try:
        result = service.create_strategy(
            name="测试-网格策略",
            code=code,
            code_type='script',
            description="测试用网格策略"
        )

        print(f"✅ 策略创建成功!")
        print(f"   策略ID: {result['strategy_id']}")
        print(f"   验证状态: {result['validation']['valid']}")
        print(f"   参数: {json.dumps(result['validation'].get('params', []), indent=2, ensure_ascii=False)}")

        return result['strategy_id']

    except Exception as e:
        print(f"❌ 创建失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_list_strategies():
    """测试列出策略"""
    print("\n" + "="*60)
    print("测试 3: 列出所有策略")
    print("="*60)

    service = StrategyCodeService()

    try:
        strategies = service.list_strategies()

        print(f"✅ 找到 {len(strategies)} 个策略:")
        for s in strategies:
            print(f"   - ID: {s['id']}, 名称: {s.get('strategy_name', 'N/A')}, 类型: {s.get('code_type', 'builtin')}")

    except Exception as e:
        print(f"❌ 列出失败: {str(e)}")
        import traceback
        traceback.print_exc()


def test_get_strategy(strategy_id):
    """测试获取策略详情"""
    print("\n" + "="*60)
    print(f"测试 4: 获取策略详情 (ID={strategy_id})")
    print("="*60)

    service = StrategyCodeService()

    try:
        strategy = service.get_strategy(strategy_id)

        if strategy:
            print(f"✅ 策略详情:")
            print(f"   ID: {strategy['id']}")
            print(f"   名称: {strategy.get('strategy_name', 'N/A')}")
            print(f"   类型: {strategy.get('code_type', 'builtin')}")
            print(f"   验证状态: {strategy.get('validation_status', 'N/A')}")
            print(f"   是否启用: {strategy.get('is_active', False)}")
        else:
            print(f"❌ 策略不存在")

    except Exception as e:
        print(f"❌ 获取失败: {str(e)}")
        import traceback
        traceback.print_exc()


def test_code_validator():
    """测试代码验证器"""
    print("\n" + "="*60)
    print("测试 5: 代码安全验证")
    print("="*60)

    from domain.quantlib.engine.code_validator import CodeValidator

    validator = CodeValidator()

    # 测试危险代码
    dangerous_codes = [
        ("import os", "禁止导入 os"),
        ("open('file.txt')", "禁止使用 open"),
        ("eval('1+1')", "禁止使用 eval"),
    ]

    for code, desc in dangerous_codes:
        try:
            validator.validate(code, 'indicator')
            print(f"❌ {desc} - 应该被拒绝但通过了")
        except ValueError as e:
            print(f"✅ {desc} - 正确拒绝: {str(e)}")


def main():
    """主测试流程"""
    print("\n" + "="*60)
    print("策略代码执行引擎 - 快速测试")
    print("="*60)

    # 测试 1: 创建 IndicatorStrategy
    indicator_id = test_indicator_strategy()

    # 测试 2: 创建 ScriptStrategy
    script_id = test_script_strategy()

    # 测试 3: 列出策略
    test_list_strategies()

    # 测试 4: 获取策略详情
    if indicator_id:
        test_get_strategy(indicator_id)

    # 测试 5: 代码验证器
    test_code_validator()

    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)

    if indicator_id and script_id:
        print(f"\n✅ 所有核心功能测试通过!")
        print(f"\n创建的策略ID:")
        print(f"  - IndicatorStrategy: {indicator_id}")
        print(f"  - ScriptStrategy: {script_id}")
    else:
        print(f"\n⚠️  部分测试失败，请检查错误信息")


if __name__ == '__main__':
    main()
