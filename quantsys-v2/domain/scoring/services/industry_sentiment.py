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
        'keywords': ['半导体', '集成电路', '芯片', '晶圆', '计算机', '通信', '电子设备'],
    },
    
    # 新能源（政策支持）
    '新能源': {
        'score': 8.0,
        'reason': '政策支持，新能源车渗透率提升',
        'keywords': ['新能源', '电池', '光伏', '风电', '储能'],
    },
    
    # 黄金（避险情绪）
    '黄金': {
        'score': 5.0,
        'reason': '国际动乱，避险情绪升温',
        'keywords': ['黄金', '贵金属', '有色金属', '有色'],
    },
    
    # 农产品（涨价预期）
    '农产品': {
        'score': 5.0,
        'reason': '厄尔尼诺影响，农产品涨价预期',
        'keywords': ['农产品', '种植', '粮食', '化肥', '农副', '糖'],
    },
    
    # 白酒（消费低迷）
    '白酒': {
        'score': -5.0,
        'reason': '消费低迷，中报加速出清',
        'keywords': ['白酒', '酒', '饮料', '精制茶'],
    },
    
    # 食品饮料（消费低迷）
    '食品饮料': {
        'score': -3.0,
        'reason': '消费低迷，需求疲软',
        'keywords': ['食品', '饮料', '乳制品'],
    },
    
    # 银行（防守，中性）
    '银行': {
        'score': 0.0,
        'reason': '防守型资产，中性',
        'keywords': ['银行', '金融'],
    },
}


def get_industry_sentiment(industry: str, sector: str = None) -> float:
    """
    获取行业景气度分数
    
    Args:
        industry: 行业名称（如"制造业-计算机、通信和其他电子设备制造业"）
        sector: 大类名称（如"制造业"）
        
    Returns:
        float: 景气度分数（-10 到 +10）
    """
    # 遍历配置，匹配关键词
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


def get_industry_sentiment_detail(industry: str, sector: str = None) -> Dict:
    """
    获取行业景气度详细信息
    
    Args:
        industry: 行业名称
        sector: 大类名称
        
    Returns:
        Dict: 景气度详细信息
    """
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
