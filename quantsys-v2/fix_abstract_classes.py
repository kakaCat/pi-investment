#!/usr/bin/env python3
"""批量修复抽象类实例化问题"""
import re
import sys

files = [
    "application/services/diagnosis_service.py",
    "application/services/signal_execution_scheduler.py",
    "application/services/stock_code_validator.py",
    "application/services/game_alert_service.py",
    "application/services/data_validator.py",
    "application/services/data_gap_detector.py",
    "application/services/chan_knowledge_distiller.py",
    "application/services/strategy_executor.py",
    "application/services/battlefield_assessor.py",
    "application/services/data_backfiller.py",
    "application/services/trading_calendar_service.py",
    "application/services/opponent_behavior_service.py",
    "application/services/swing_point_service.py",
    "application/services/factor_layering_service.py",
    "application/services/strategy_backtest_service.py",
    "application/services/enhanced_risk_assessor.py",
    "application/services/manipulation_detector.py",
    "application/services/data_quality_service.py",
    "application/services/pool_validation_service.py",
    "application/services/data_service_orm.py",
]

replacements = [
    (r'(\s+)self\.kline_repo = kline_repo or IKlineRepository\(\)', r'\1self.kline_repo = kline_repo'),
    (r'(\s+)self\._kline_repo = kline_repo or IKlineRepository\(\)', r'\1self._kline_repo = kline_repo'),
    (r'(\s+)self\.kline = kline_repo or IKlineRepository\(\)', r'\1self.kline = kline_repo'),
    (r'(\s+)self\.strategy_repo = strategy_repo or IStrategyRepository\(\)', r'\1self.strategy_repo = strategy_repo'),
    (r'(\s+)self\._strategy_repo = strategy_repo or IStrategyRepository\(\)', r'\1self._strategy_repo = strategy_repo'),
    (r'(\s+)self\.fund_flow_repo = fund_flow_repo or IFundFlowRepository\(\)', r'\1self.fund_flow_repo = fund_flow_repo'),
    (r'(\s+)self\.financial_repo = financial_repo or IFinancialRepository\(\)', r'\1self.financial_repo = financial_repo'),
]

for filepath in files:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)

        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Fixed: {filepath}")
        else:
            print(f"⏭️  Skipped: {filepath} (no changes)")
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        sys.exit(1)

print("\n🎉 All files processed!")
