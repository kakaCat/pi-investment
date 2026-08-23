"""
风险管理领域 (Risk Domain)

职责：
- 风险指标计算（VaR, CVaR, Sharpe, MaxDrawdown等）
- 风险限额管理
- 风险预警和监控
- 风险归因分析

核心模块：
- attribution: 风险归因分析
- var: Value at Risk 计算
- cvar: Conditional VaR 计算
- drawdown: 回撤分析
- market_risk: 市场风险计算
- stress_test: 压力测试
- stress_testing: 压力测试框架
- backtesting: 风险模型回测
- copula: Copula 模型
- extreme_value: 极值理论
- liquidity_risk: 流动性风险
- counterparty_risk: 交易对手风险
- regulatory: 监管风险指标
- reporting: 风险报告
- aggregation: 风险聚合
- margining: 保证金计算
- risk_monitor: 风险监控

与其他领域的关系：
- 为 domain.backtest 提供风险评估
- 为 domain.strategies 提供风险控制
- 使用 domain.quantlib 的统计计算能力

示例：
    from domain.risk.attribution import RiskAttributionCalculator
    from domain.risk import var, drawdown

    # 风险归因
    calculator = RiskAttributionCalculator()
    attribution = calculator.calculate(returns, factors)
"""

# 暂不导出具体类，避免循环导入和缺失依赖
# 使用时直接从子模块导入：
# from domain.risk.attribution import RiskAttributionCalculator
# from domain.risk.var import HistoricalVaR

__all__ = []
