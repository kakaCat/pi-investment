"""
高级交易策略参数说明文档

本文档详细说明了7个新增高级交易策略的参数配置、使用场景和注意事项。
"""
import structlog
logger = structlog.get_logger(__name__)

# ==================== 策略概览 ====================

STRATEGY_OVERVIEW = {
    'turtle': {
        'name': '海龟交易策略',
        'type': '趋势跟踪',
        'description': '经典的唐奇安通道突破策略，基于海龟交易法则',
        '适用市场': '趋势明显的市场',
        '风险等级': '中高',
    },
    'donchian_channel': {
        'name': '唐奇安通道策略',
        'type': '趋势跟踪',
        'description': '基于价格通道的突破策略',
        '适用市场': '波动较大的市场',
        '风险等级': '中',
    },
    'momentum': {
        'name': 'ROC动量策略',
        'type': '动量策略',
        'description': '基于价格变化率的动量策略',
        '适用市场': '趋势市场',
        '风险等级': '中',
    },
    'breakout': {
        'name': '突破策略',
        'type': '动量策略',
        'description': '价格突破配合成交量确认',
        '适用市场': '整理后突破的市场',
        '风险等级': '中',
    },
    'mean_reversion': {
        'name': '均值回归策略',
        'type': '均值回归',
        'description': '基于布林带的超买超卖策略',
        '适用市场': '震荡市场',
        '风险等级': '中低',
    },
    'volatility_breakout': {
        'name': 'ATR波动率突破策略',
        'type': '波动率策略',
        'description': '基于ATR的自适应突破策略',
        '适用市场': '波动率变化的市场',
        '风险等级': '中',
    },
    'pairs_correlation': {
        'name': '配对交易策略',
        'type': '统计套利',
        'description': '基于相关性的价差交易',
        '适用市场': '相关性稳定的资产对',
        '风险等级': '低',
    },
}


# ==================== 详细参数说明 ====================

# 1. 海龟交易策略 (TurtleStrategy)
TURTLE_PARAMS = {
    'strategy_type': 'turtle',
    'parameters': {
        'entry_period': {
            'type': 'int',
            'default': 20,
            'range': [10, 60],
            'description': '入场突破周期（天）',
            '说明': '价格突破N日最高价时买入',
            '调优建议': '短期交易用10-20，长期交易用30-60',
        },
        'exit_period': {
            'type': 'int',
            'default': 10,
            'range': [5, 30],
            'description': '出场突破周期（天）',
            '说明': '价格跌破N日最低价时卖出（止损）',
            '调优建议': '通常为entry_period的一半',
        },
    },
    '使用示例': {
        'parameters': {
            'entry_period': 20,
            'exit_period': 10,
        }
    },
    '信号说明': {
        'buy': '突破20日高点，趋势启动',
        'sell': '跌破10日低点，止损离场',
        'hold': '在通道内，等待突破',
    },
    '注意事项': [
        '适合趋势明显的市场，震荡市会频繁止损',
        '需要配合仓位管理，单次风险不超过2%',
        '假突破较多时可增加entry_period',
    ],
}


# 2. 唐奇安通道策略 (DonchianChannelStrategy)
DONCHIAN_PARAMS = {
    'strategy_type': 'donchian_channel',
    'parameters': {
        'period': {
            'type': 'int',
            'default': 20,
            'range': [10, 60],
            'description': '通道周期（天）',
            '说明': '计算N日最高价和最低价形成通道',
            '调优建议': '周期越长，信号越稳定但滞后',
        },
    },
    '使用示例': {
        'parameters': {
            'period': 20,
        }
    },
    '信号说明': {
        'buy': '突破通道上轨，强势信号',
        'sell': '跌破通道下轨，弱势信号',
        'hold': '在通道内，观察位置',
    },
    '注意事项': [
        '通道宽度反映波动率，窄通道突破更有效',
        '可与成交量配合使用提高准确率',
        '适合波动较大的股票',
    ],
}


# 3. ROC动量策略 (MomentumStrategy)
MOMENTUM_PARAMS = {
    'strategy_type': 'momentum',
    'parameters': {
        'roc_period': {
            'type': 'int',
            'default': 12,
            'range': [5, 30],
            'description': 'ROC计算周期（天）',
            '说明': '计算当前价格相对N日前的变化率',
            '调优建议': '短期用5-10，中期用12-20',
        },
        'ma_period': {
            'type': 'int',
            'default': 5,
            'range': [3, 10],
            'description': 'ROC均线周期（天）',
            '说明': '对ROC进行平滑处理，减少噪音',
            '调优建议': '通常为roc_period的1/3到1/2',
        },
    },
    '使用示例': {
        'parameters': {
            'roc_period': 12,
            'ma_period': 5,
        }
    },
    '信号说明': {
        'buy': 'ROC上穿零线，动量转正',
        'sell': 'ROC下穿零线，动量转负',
        'hold': 'ROC在零线上方/下方，趋势延续',
    },
    '注意事项': [
        '适合捕捉趋势转折点',
        '震荡市会产生较多假信号',
        'ROC绝对值越大，动量越强',
    ],
}


# 4. 突破策略 (BreakoutStrategy)
BREAKOUT_PARAMS = {
    'strategy_type': 'breakout',
    'parameters': {
        'lookback_period': {
            'type': 'int',
            'default': 20,
            'range': [10, 60],
            'description': '回溯周期（天）',
            '说明': '确定阻力位和支撑位的周期',
            '调优建议': '周期越长，突破越有效',
        },
        'volume_ma_period': {
            'type': 'int',
            'default': 10,
            'range': [5, 30],
            'description': '成交量均线周期（天）',
            '说明': '计算成交量基准',
            '调优建议': '通常为lookback_period的一半',
        },
        'volume_threshold': {
            'type': 'float',
            'default': 1.5,
            'range': [1.2, 3.0],
            'description': '成交量放大倍数',
            '说明': '突破时成交量需达到均值的N倍',
            '调优建议': '1.5-2.0为常用值，要求越高信号越可靠',
        },
    },
    '使用示例': {
        'parameters': {
            'lookback_period': 20,
            'volume_ma_period': 10,
            'volume_threshold': 1.5,
        }
    },
    '信号说明': {
        'buy': '突破阻力位且成交量放大',
        'sell': '跌破支撑位且成交量放大',
        'hold': '突破但成交量不足，等待确认',
    },
    '注意事项': [
        '成交量确认可有效过滤假突破',
        '适合整理后的突破行情',
        '成交量不足的突破不建议跟进',
    ],
}


# 5. 均值回归策略 (MeanReversionStrategy)
MEAN_REVERSION_PARAMS = {
    'strategy_type': 'mean_reversion',
    'parameters': {
        'period': {
            'type': 'int',
            'default': 20,
            'range': [10, 60],
            'description': '布林带周期（天）',
            '说明': '计算移动平均和标准差的周期',
            '调优建议': '20是经典参数，震荡市可用10-15',
        },
        'num_std': {
            'type': 'float',
            'default': 2.0,
            'range': [1.5, 3.0],
            'description': '标准差倍数',
            '说明': '布林带宽度 = 均线 ± N倍标准差',
            '调优建议': '2.0为标准值，波动大时用2.5-3.0',
        },
        'threshold': {
            'type': 'float',
            'default': 0.02,
            'range': [0.01, 0.05],
            'description': '触及阈值',
            '说明': '价格距离上下轨N%以内算触及',
            '调优建议': '0.02-0.03为常用值',
        },
    },
    '使用示例': {
        'parameters': {
            'period': 20,
            'num_std': 2.0,
            'threshold': 0.02,
        }
    },
    '信号说明': {
        'buy': '触及下轨，超卖反弹',
        'sell': '触及上轨，超买回落',
        'hold': '在中轨附近，等待极值',
    },
    '注意事项': [
        '适合震荡市，趋势市会持续亏损',
        '可结合RSI确认超买超卖',
        '强趋势时不要逆势交易',
    ],
}


# 6. ATR波动率突破策略 (VolatilityBreakoutStrategy)
VOLATILITY_BREAKOUT_PARAMS = {
    'strategy_type': 'volatility_breakout',
    'parameters': {
        'atr_period': {
            'type': 'int',
            'default': 14,
            'range': [7, 30],
            'description': 'ATR计算周期（天）',
            '说明': '计算平均真实波动幅度',
            '调优建议': '14是经典参数，短期用7-10',
        },
        'atr_multiplier': {
            'type': 'float',
            'default': 2.0,
            'range': [1.0, 4.0],
            'description': 'ATR倍数',
            '说明': '突破阈值 = 昨收 ± N倍ATR',
            '调优建议': '2.0为标准值，激进用1.5，保守用3.0',
        },
    },
    '使用示例': {
        'parameters': {
            'atr_period': 14,
            'atr_multiplier': 2.0,
        }
    },
    '信号说明': {
        'buy': '突破昨收+2ATR，强势突破',
        'sell': '跌破昨收-2ATR，弱势突破',
        'hold': '在波动区间内，等待突破',
    },
    '注意事项': [
        'ATR自适应波动率，适合不同波动环境',
        '波动率低时阈值小，容易触发',
        '波动率高时阈值大，过滤噪音',
    ],
}


# 7. 配对交易策略 (PairsCorrelationStrategy)
PAIRS_CORRELATION_PARAMS = {
    'strategy_type': 'pairs_correlation',
    'parameters': {
        'lookback_period': {
            'type': 'int',
            'default': 60,
            'range': [30, 120],
            'description': '回溯周期（天）',
            '说明': '计算价差均值和标准差的周期',
            '调优建议': '60-90天为常用值，需要足够样本',
        },
        'entry_threshold': {
            'type': 'float',
            'default': 2.0,
            'range': [1.5, 3.0],
            'description': '入场Z-score阈值',
            '说明': '价差偏离均值N个标准差时入场',
            '调优建议': '2.0为标准值，保守用2.5',
        },
        'exit_threshold': {
            'type': 'float',
            'default': 0.5,
            'range': [0.0, 1.0],
            'description': '出场Z-score阈值',
            '说明': '价差回归到N个标准差内时出场',
            '调优建议': '0.5为常用值，可根据回归速度调整',
        },
        'klines_b': {
            'type': 'List[Dict]',
            'required': True,
            'description': '第二个股票的K线数据',
            '说明': '配对交易需要两个股票的数据',
        },
        'symbol_a': {
            'type': 'str',
            'description': '第一个股票代码（用于日志）',
        },
        'symbol_b': {
            'type': 'str',
            'description': '第二个股票代码（用于日志）',
        },
    },
    '使用示例': {
        'parameters': {
            'lookback_period': 60,
            'entry_threshold': 2.0,
            'exit_threshold': 0.5,
            'klines_b': [],  # 需要传入实际数据
            'symbol_a': '000001.SZ',
            'symbol_b': '000002.SZ',
        }
    },
    '信号说明': {
        'buy': '价差过低，买A卖B',
        'sell': '价差过高，卖A买B',
        'hold': '价差正常或相关性不足',
    },
    '注意事项': [
        '需要选择高度相关的资产对（相关系数>0.7）',
        '相关性会随时间变化，需定期检查',
        '适合市场中性策略，风险较低',
        '需要同时操作两个标的',
    ],
}


# ==================== 策略组合建议 ====================

STRATEGY_COMBINATIONS = {
    '趋势市组合': {
        'strategies': ['turtle', 'donchian_channel', 'momentum'],
        'description': '适合趋势明显的市场环境',
        'combine_mode': 'majority',
        'weights': [0.4, 0.3, 0.3],
    },
    '震荡市组合': {
        'strategies': ['mean_reversion', 'pairs_correlation'],
        'description': '适合横盘震荡的市场环境',
        'combine_mode': 'weighted',
        'weights': [0.6, 0.4],
    },
    '突破确认组合': {
        'strategies': ['breakout', 'volatility_breakout'],
        'description': '双重确认突破信号',
        'combine_mode': 'and',
        'weights': [0.5, 0.5],
    },
    '全天候组合': {
        'strategies': ['turtle', 'mean_reversion', 'momentum', 'breakout'],
        'description': '适应不同市场环境',
        'combine_mode': 'weighted',
        'weights': [0.3, 0.3, 0.2, 0.2],
    },
}


# ==================== 参数调优指南 ====================

TUNING_GUIDE = {
    '趋势跟踪策略': {
        '市场特征': '趋势明显，波动较大',
        '参数调整': {
            '周期参数': '趋势越强，周期可越长（减少噪音）',
            '止损参数': '波动越大，止损周期应越短',
        },
        '适用策略': ['turtle', 'donchian_channel', 'momentum'],
    },
    '均值回归策略': {
        '市场特征': '横盘震荡，波动有限',
        '参数调整': {
            '周期参数': '震荡越规律，周期可越短',
            '阈值参数': '波动越小，阈值应越小',
        },
        '适用策略': ['mean_reversion', 'pairs_correlation'],
    },
    '突破策略': {
        '市场特征': '整理后突破',
        '参数调整': {
            '周期参数': '整理时间越长，周期应越长',
            '成交量参数': '假突破多时，提高成交量要求',
        },
        '适用策略': ['breakout', 'volatility_breakout'],
    },
}


# ==================== 风险提示 ====================

RISK_WARNINGS = {
    '通用风险': [
        '所有策略都有失效期，需定期回测和调整',
        '历史表现不代表未来收益',
        '建议组合使用多个策略分散风险',
        '严格执行止损，单次风险不超过2%',
    ],
    '趋势策略风险': [
        '震荡市会频繁止损',
        '趋势反转时可能损失较大',
        '需要较大的资金容忍度',
    ],
    '均值回归风险': [
        '趋势市会持续亏损',
        '极端行情下可能失效',
        '需要及时识别市场环境变化',
    ],
    '配对交易风险': [
        '相关性破裂风险',
        '需要同时操作两个标的',
        '流动性风险',
    ],
}


if __name__ == '__main__':
    """打印策略参数说明"""
    logger.info('=' * 80)
    logger.info('高级交易策略参数说明')
    logger.info('=' * 80)

    for strategy_type, overview in STRATEGY_OVERVIEW.items():
        logger.info(f"\n【{overview['name']}】")
        logger.info(f"  类型: {overview['type']}")
        logger.info(f"  描述: {overview['description']}")
        logger.info(f"  适用市场: {overview['适用市场']}")
        logger.info(f"  风险等级: {overview['风险等级']}")

    logger.info('\n' + '=' * 80)
    logger.info('详细参数请查看各策略的 PARAMS 字典')
    logger.info('=' * 80)
