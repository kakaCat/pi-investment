"""
股票评分配置

可以通过修改此配置文件来调整评分权重和规则，无需修改代码
"""

# ==================== 评分维度权重 ====================

SCORING_WEIGHTS = {
    'technical': 0.40,      # 技术面权重
    'fundamental': 0.30,    # 基本面权重
    'momentum': 0.20,       # 动量权重
    'quality': 0.10,        # 质量权重
}

# ==================== 技术面评分规则 ====================

TECHNICAL_SCORING = {
    # RSI 指标权重（总30分）
    'rsi': {
        'weight': 30,
        'rules': [
            {'range': (30, 40), 'score': 30, 'desc': '弱超卖，机会'},
            {'range': (40, 60), 'score': 20, 'desc': '中性'},
            {'range': (60, 70), 'score': 15, 'desc': '偏强'},
            {'range': (0, 30), 'score': 25, 'desc': '超卖'},
            {'range': (70, 100), 'score': 5, 'desc': '超买'},
        ]
    },

    # MACD 指标权重（总30分）
    'macd': {
        'weight': 30,
        'rules': {
            'golden_cross_rising': 30,  # 金叉且柱状图上升
            'golden_cross': 20,          # 仅金叉
            'death_cross_falling': 5,    # 死叉且柱状图下降
            'neutral': 10,               # 其他情况
        }
    },

    # 均线权重（总25分）
    'ma': {
        'weight': 25,
        'rules': {
            'full_bullish': 25,    # close > ma5 > ma20 > ma60
            'partial_bullish': 20, # close > ma20 > ma60
            'above_ma60': 15,      # close > ma60
            'other': 5,            # 其他
        }
    },

    # 布林带权重（总15分）
    'bollinger': {
        'weight': 15,
        'rules': [
            {'range': (0.2, 0.4), 'score': 15, 'desc': '下轨附近，支撑'},
            {'range': (0.4, 0.6), 'score': 10, 'desc': '中轨附近'},
            {'range': (0.6, 0.8), 'score': 8, 'desc': '上轨附近'},
            {'range': (0.0, 0.2), 'score': 5, 'desc': '极端下轨'},
            {'range': (0.8, 1.0), 'score': 5, 'desc': '极端上轨'},
        ]
    },
}

# ==================== 基本面评分规则 ====================

FUNDAMENTAL_SCORING = {
    # PE 估值权重（总30分）
    'pe': {
        'weight': 30,
        'rules': [
            {'range': (0, 15), 'score': 30, 'desc': '低估'},
            {'range': (15, 25), 'score': 25, 'desc': '合理'},
            {'range': (25, 40), 'score': 15, 'desc': '偏高'},
            {'range': (40, 60), 'score': 5, 'desc': '较高'},
            {'range': (60, 9999), 'score': 0, 'desc': '极高'},
        ]
    },

    # ROE 盈利能力权重（总30分）
    'roe': {
        'weight': 30,
        'rules': [
            {'range': (0.20, 999), 'score': 30, 'desc': '优秀'},
            {'range': (0.15, 0.20), 'score': 25, 'desc': '良好'},
            {'range': (0.10, 0.15), 'score': 15, 'desc': '一般'},
            {'range': (0.05, 0.10), 'score': 5, 'desc': '较差'},
            {'range': (0, 0.05), 'score': 0, 'desc': '很差'},
        ]
    },

    # 负债率权重（总25分）
    'debt_ratio': {
        'weight': 25,
        'rules': [
            {'range': (0, 0.30), 'score': 25, 'desc': '低负债'},
            {'range': (0.30, 0.50), 'score': 20, 'desc': '中等负债'},
            {'range': (0.50, 0.70), 'score': 10, 'desc': '偏高负债'},
            {'range': (0.70, 999), 'score': 0, 'desc': '高负债'},
        ]
    },

    # PB 估值权重（总15分）
    'pb': {
        'weight': 15,
        'rules': [
            {'range': (0, 1.5), 'score': 15, 'desc': '低估'},
            {'range': (1.5, 3.0), 'score': 10, 'desc': '合理'},
            {'range': (3.0, 5.0), 'score': 5, 'desc': '偏高'},
            {'range': (5.0, 9999), 'score': 0, 'desc': '极高'},
        ]
    },
}

# ==================== 动量评分规则 ====================

MOMENTUM_SCORING = {
    'base_score': 50,  # 基准分

    # 5日涨跌幅
    'change_5d': {
        'weight': 25,
        'rules': [
            {'threshold': 10, 'score': 25, 'desc': '强劲上涨'},
            {'threshold': 5, 'score': 20, 'desc': '上涨'},
            {'threshold': 0, 'score': 10, 'desc': '小涨'},
            {'threshold': -5, 'score': -5, 'desc': '小跌'},
            {'threshold': -999, 'score': -15, 'desc': '大跌'},
        ]
    },

    # 20日涨跌幅
    'change_20d': {
        'weight': 25,
        'rules': [
            {'threshold': 20, 'score': 25, 'desc': '强劲上涨'},
            {'threshold': 10, 'score': 15, 'desc': '上涨'},
            {'threshold': 0, 'score': 5, 'desc': '小涨'},
            {'threshold': -999, 'score': -10, 'desc': '下跌'},
        ]
    },

    # 成交量比率
    'volume_ratio': {
        'weight': 30,
        'rules': [
            {'threshold': 2.0, 'score': 30, 'desc': '放量2倍+'},
            {'threshold': 1.5, 'score': 20, 'desc': '放量1.5倍+'},
            {'threshold': 1.0, 'score': 10, 'desc': '正常'},
            {'threshold': 0, 'score': 0, 'desc': '缩量'},
        ]
    },

    # 连续上涨天数
    'consecutive_up': {
        'weight': 20,
        'rules': [
            {'threshold': 5, 'score': 20, 'desc': '连续5天+'},
            {'threshold': 3, 'score': 15, 'desc': '连续3天+'},
            {'threshold': 1, 'score': 10, 'desc': '连续1天+'},
            {'threshold': 0, 'score': 0, 'desc': '未连续'},
        ]
    },
}

# ==================== 质量评分规则 ====================

QUALITY_SCORING = {
    'base_score': 50,  # 基准分

    # 毛利率
    'gross_margin': {
        'weight': 40,
        'rules': [
            {'threshold': 0.50, 'score': 40, 'desc': '优秀'},
            {'threshold': 0.30, 'score': 30, 'desc': '良好'},
            {'threshold': 0.20, 'score': 20, 'desc': '一般'},
            {'threshold': 0.10, 'score': 10, 'desc': '较差'},
            {'threshold': 0, 'score': 0, 'desc': '很差'},
        ]
    },

    # 净利率
    'net_margin': {
        'weight': 40,
        'rules': [
            {'threshold': 0.20, 'score': 40, 'desc': '优秀'},
            {'threshold': 0.10, 'score': 30, 'desc': '良好'},
            {'threshold': 0.05, 'score': 20, 'desc': '一般'},
            {'threshold': 0, 'score': 10, 'desc': '较差'},
        ]
    },

    # 经营现金流/净利润
    'ocf_ratio': {
        'weight': 20,
        'rules': [
            {'threshold': 1.2, 'score': 20, 'desc': '现金流优于利润'},
            {'threshold': 1.0, 'score': 15, 'desc': '现金流正常'},
            {'threshold': 0.8, 'score': 10, 'desc': '现金流一般'},
            {'threshold': 0, 'score': 0, 'desc': '现金流较差'},
        ]
    },
}

# ==================== 等级划分 ====================

GRADE_THRESHOLDS = [
    (90, 'A+'),
    (80, 'A'),
    (70, 'B+'),
    (60, 'B'),
    (50, 'C'),
    (0, 'D'),
]

# ==================== 信号生成规则 ====================

SIGNAL_RULES = {
    'strong_buy': {
        'condition': lambda score: score >= 80,
        'message': '综合评分优秀，强烈推荐关注',
        'priority': 'high',
    },
    'buy': {
        'condition': lambda score: score >= 70,
        'message': '综合评分良好，可考虑买入',
        'priority': 'medium',
    },
    'avoid': {
        'condition': lambda score: score <= 40,
        'message': '综合评分较低，建议回避',
        'priority': 'high',
    },
}

# ==================== 使用示例 ====================
"""
# 修改权重示例：
SCORING_WEIGHTS['technical'] = 0.50  # 提高技术面权重到50%
SCORING_WEIGHTS['fundamental'] = 0.25  # 降低基本面权重到25%

# 修改评分规则示例：
TECHNICAL_SCORING['rsi']['rules'][0]['score'] = 35  # 提高RSI超卖得分

# 修改等级划分示例：
GRADE_THRESHOLDS[0] = (85, 'A+')  # 提高A+的门槛到85分
"""
