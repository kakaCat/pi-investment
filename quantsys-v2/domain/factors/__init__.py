"""
因子领域 (Factors Domain)

职责：
- 因子计算和管理
- 因子分析（IC, IR, 分层回测）
- 因子模型（Fama-French, Barra）
- 另类因子（情绪、事件、另类数据）

核心概念：
- FactorLibrary: 因子库，包含各类技术、基本面、另类因子
- FactorAnalyzer: 因子分析器，评估因子有效性
- FactorModel: 因子模型，如 Fama-French 三因子模型

因子分类：
1. 技术因子：动量、反转、波动率、成交量、移动均线、趋势
2. 基本面因子：价值、成长、质量、盈利能力
3. 另类因子：情绪、事件驱动、另类数据
4. 高级因子：周期、模式识别、复合因子

因子分析方法：
- IC分析：信息系数，衡量因子预测能力
- 分层回测：按因子值分组回测
- 因子归因：识别收益来源

与其他领域的关系：
- 为 domain.strategies 提供因子信号
- 为 domain.backtest 提供因子计算
- 使用 domain.quantlib 的统计和技术指标

示例：
    from domain.factors.library import MomentumFactor, ValueFactor
    from domain.factors.analysis import ICAnalyzer
    
    momentum = MomentumFactor()
    signals = momentum.calculate(klines)
    
    analyzer = ICAnalyzer()
    ic = analyzer.calculate_ic(factor_values, future_returns)
"""

# 子模块会在后续完善导出
__all__ = []
