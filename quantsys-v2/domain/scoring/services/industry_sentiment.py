"""
行业景气度配置

根据当前市场情况手动配置的行业景气度分数。
后续可以从数据库或外部 API 读取。

评分范围：-10 到 +10
- +10: 极度景气（如半导体国产替代）
- +5: 景气（如黄金避险）
- 0: 中性
- -5: 低迷（如白酒消费低迷）
- -10: 极度低迷
"""

from typing import Dict
from datetime import datetime


# 行业景气度配置（2026-09-09）
INDUSTRY_SENTIMENT: Dict[str, Dict[str, any]] = {
    # 半导体（国家战略 + 内存涨价 + 国产替代）
    '半导体': {
        'score': 10.0,
        'reason': 'DRAM 价格一年翻 4 倍，国产替代窗口期',
        'keywords': ['半导体', '集成电路', '芯片', '晶圆', '中芯'],
        'symbols': ['688981'],  # 中芯国际
    },
    
    # PCB（AI 服务器需求）
    'PCB': {
        'score': 8.0,
        'reason': 'AI 服务器需求旺盛，年涨幅 163-167%',
        'keywords': ['PCB', '印制电路板', '沪电', '深南'],
        'symbols': ['002463', '002916'],  # 沪电股份、深南电路
    },
    
    # 光模块（AI 算力需求）
    '光模块': {
        'score': 10.0,
        'reason': 'AI 算力需求爆发，年涨幅 168-299%',
        'keywords': ['光模块', '光通信', '中际旭创', '新易盛'],
        'symbols': ['300308', '300502'],  # 中际旭创、新易盛
    },
    
    # 新能源（政策支持）
    '新能源': {
        'score': 8.0,
        'reason': '政策支持，新能源车渗透率提升',
        'keywords': ['新能源', '电池', '光伏', '风电', '储能'],
        'symbols': ['300750'],  # 宁德时代
    },
    
    # 黄金（避险情绪）
    '黄金': {
        'score': 5.0,
        'reason': '国际动乱，避险情绪升温',
        'keywords': ['黄金', '贵金属', '有色金属', '有色'],
        'symbols': ['600489', '600547'],  # 中金黄金、山东黄金
    },
    
    # 农产品（涨价预期）
    '农产品': {
        'score': 5.0,
        'reason': '厄尔尼诺影响，农产品涨价预期',
        'keywords': ['农产品', '种植', '粮食', '化肥', '农副', '糖'],
        'symbols': ['600737'],  # 中粮糖业
    },
    
    # 白酒（消费低迷）
    '白酒': {
        'score': -5.0,
        'reason': '消费低迷，中报加速出清',
        'keywords': ['白酒', '酒', '饮料', '精制茶'],
        'symbols': ['600519', '000858'],  # 贵州茅台、五粮液
    },
    
    # 食品饮料（消费低迷）
    '食品饮料': {
        'score': -3.0,
        'reason': '消费低迷，需求疲软',
        'keywords': ['食品', '饮料', '乳制品'],
        'symbols': ['600887'],  # 伊利股份
    },
    
    # 银行（防守，中性）
    '银行': {
        'score': 0.0,
        'reason': '防守型资产，中性',
        'keywords': ['银行', '金融'],
        'symbols': ['000001', '601398', '601288'],  # 平安银行、工商银行、农业银行
    },
}


def get_industry_sentiment(industry: str, sector: str = None, symbol: str = None, name: str = None) -> float:
    """
    获取行业景气度分数
    
    Args:
        industry: 行业名称（如"制造业-计算机、通信和其他电子设备制造业"）
        sector: 大类名称（如"制造业"）
        symbol: 股票代码（可选，用于精确匹配）
        name: 股票名称（可选，用于精确匹配）
        
    Returns:
        float: 景气度分数（-10 到 +10）
    """
    # 优先使用股票代码匹配（最精确）
    if symbol:
        for sentiment_industry, config in INDUSTRY_SENTIMENT.items():
            symbols = config.get('symbols', [])
            if symbol in symbols:
                return config['score']
    
    # 其次使用股票名称匹配（精确）
    if name:
        for sentiment_industry, config in INDUSTRY_SENTIMENT.items():
            keywords = config.get('keywords', [])
            for keyword in keywords:
                if keyword in name:
                    return config['score']
    
    # 最后使用行业名称匹配（模糊）
    for sentiment_industry, config in INDUSTRY_SENTIMENT.items():
        keywords = config.get('keywords', [])
        
        # 检查 industry 是否包含关键词
        if industry:
            for keyword in keywords:
                if keyword in industry:
                    return config['score']
        
        # 检查 sector 是否包含关键词
        if sector:
            for keyword in keywords:
                if keyword in sector:
                    return config['score']
    
    # 默认返回 0（中性）
    return 0.0


def get_industry_sentiment_detail(industry: str, sector: str = None, symbol: str = None, name: str = None) -> Dict:
    """
    获取行业景气度详细信息
    
    Args:
        industry: 行业名称
        sector: 大类名称
        symbol: 股票代码（可选）
        name: 股票名称（可选）
        
    Returns:
        Dict: 景气度详细信息
    """
    # 优先使用股票代码匹配（最精确）
    if symbol:
        for sentiment_industry, config in INDUSTRY_SENTIMENT.items():
            symbols = config.get('symbols', [])
            if symbol in symbols:
                return {
                    'industry': sentiment_industry,
                    'score': config['score'],
                    'reason': config['reason'],
                    'updated_at': datetime.now().isoformat(),
                }
    
    # 其次使用股票名称匹配（精确）
    if name:
        for sentiment_industry, config in INDUSTRY_SENTIMENT.items():
            keywords = config.get('keywords', [])
            for keyword in keywords:
                if keyword in name:
                    return {
                        'industry': sentiment_industry,
                        'score': config['score'],
                        'reason': config['reason'],
                        'updated_at': datetime.now().isoformat(),
                    }
    
    # 最后使用行业名称匹配（模糊）
    for sentiment_industry, config in INDUSTRY_SENTIMENT.items():
        keywords = config.get('keywords', [])
        
        if industry:
            for keyword in keywords:
                if keyword in industry:
                    return {
                        'industry': sentiment_industry,
                        'score': config['score'],
                        'reason': config['reason'],
                        'updated_at': datetime.now().isoformat(),
                    }
        
        if sector:
            for keyword in keywords:
                if keyword in sector:
                    return {
                        'industry': sentiment_industry,
                        'score': config['score'],
                        'reason': config['reason'],
                        'updated_at': datetime.now().isoformat(),
                    }
    
    return {
        'industry': industry or sector or '未知',
        'score': 0.0,
        'reason': '中性，无特殊景气度',
        'updated_at': datetime.now().isoformat(),
    }
