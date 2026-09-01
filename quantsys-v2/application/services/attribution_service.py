"""M6-1 归因分析服务

功能：
- 统计各规则（R-xxx）的引用次数
- 计算每条规则关联交易的胜率和平均收益
- 识别高价值规则和失效规则

用于：经验飞轮、规则进化、周报生成
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import re
import structlog

logger = structlog.get_logger(__name__)


class AttributionService:
    """归因分析服务"""
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        if not self.db:
            import psycopg2
            self.db = psycopg2.connect(
                dbname="quant_investment",
                user="yunpeng",
                host="localhost"
            )
            self._owns_connection = True
        else:
            self._owns_connection = False
    
    def analyze_rule_performance(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_samples: int = 3
    ) -> Dict[str, Any]:
        """分析规则表现
        
        基于 signal_tracking 表的信号记录进行归因分析
        
        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            min_samples: 最小样本数（低于此数的规则标记为"样本不足"）
        
        Returns:
            {
                "summary": {
                    "total_signals": 100,
                    "signals_with_rules": 80,
                    "unique_rules": 10
                },
                "rule_stats": [
                    {
                        "rule_id": "R-001",
                        "count": 20,
                        "win_rate_5d": 0.75,
                        "avg_return_5d": 0.08,
                        "recommendation": "keep"
                    },
                    ...
                ],
                "unattributed_signals": 20
            }
        """
        cursor = self.db.cursor()
        
        try:
            # 默认时间范围：最近30天
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            
            # 1. 从 signal_tracking 获取信号记录
            cursor.execute("""
                SELECT 
                    id,
                    signal_date,
                    symbol,
                    grade,
                    source,
                    price,
                    reason,
                    return_5d,
                    return_10d,
                    return_20d,
                    hit_5d,
                    hit_10d,
                    hit_20d
                FROM signal_tracking
                WHERE signal_date >= %s AND signal_date <= %s
                ORDER BY signal_date DESC
            """, (start_date, end_date))
            
            signals = []
            columns = [desc[0] for desc in cursor.description]
            for row in cursor.fetchall():
                signals.append(dict(zip(columns, row)))
            
            # 2. 提取规则引用并统计
            rule_stats = {}
            unattributed_count = 0
            
            for signal in signals:
                reason = signal.get('reason', '') or ''
                
                # 提取规则 ID
                rule_ids = self._extract_rule_ids(reason)
                
                if not rule_ids:
                    unattributed_count += 1
                    continue
                
                # 为每个引用的规则记录统计
                for rule_id in rule_ids:
                    if rule_id not in rule_stats:
                        rule_stats[rule_id] = {
                            'rule_id': rule_id,
                            'count': 0,
                            'hits_5d': 0,
                            'hits_10d': 0,
                            'hits_20d': 0,
                            'total_return_5d': 0.0,
                            'total_return_10d': 0.0,
                            'total_return_20d': 0.0,
                            'samples_5d': 0,
                            'samples_10d': 0,
                            'samples_20d': 0,
                            'signals': []
                        }
                    
                    stats = rule_stats[rule_id]
                    stats['count'] += 1
                    stats['signals'].append(signal)
                    
                    # 5日表现
                    if signal.get('return_5d') is not None:
                        stats['samples_5d'] += 1
                        stats['total_return_5d'] += signal['return_5d']
                        if signal.get('hit_5d'):
                            stats['hits_5d'] += 1
                    
                    # 10日表现
                    if signal.get('return_10d') is not None:
                        stats['samples_10d'] += 1
                        stats['total_return_10d'] += signal['return_10d']
                        if signal.get('hit_10d'):
                            stats['hits_10d'] += 1
                    
                    # 20日表现
                    if signal.get('return_20d') is not None:
                        stats['samples_20d'] += 1
                        stats['total_return_20d'] += signal['return_20d']
                        if signal.get('hit_20d'):
                            stats['hits_20d'] += 1
            
            # 3. 计算派生指标并生成建议
            rule_list = []
            for rule_id, stats in rule_stats.items():
                count = stats['count']
                
                # 5日指标
                win_rate_5d = stats['hits_5d'] / stats['samples_5d'] if stats['samples_5d'] > 0 else None
                avg_return_5d = stats['total_return_5d'] / stats['samples_5d'] if stats['samples_5d'] > 0 else None
                
                # 10日指标
                win_rate_10d = stats['hits_10d'] / stats['samples_10d'] if stats['samples_10d'] > 0 else None
                avg_return_10d = stats['total_return_10d'] / stats['samples_10d'] if stats['samples_10d'] > 0 else None
                
                # 20日指标
                win_rate_20d = stats['hits_20d'] / stats['samples_20d'] if stats['samples_20d'] > 0 else None
                avg_return_20d = stats['total_return_20d'] / stats['samples_20d'] if stats['samples_20d'] > 0 else None
                
                # 生成建议（基于 5 日表现）
                recommendation = self._generate_recommendation(
                    stats['samples_5d'], 
                    win_rate_5d or 0, 
                    avg_return_5d or 0, 
                    min_samples
                )
                
                rule_list.append({
                    'rule_id': rule_id,
                    'count': count,
                    'samples_5d': stats['samples_5d'],
                    'win_rate_5d': round(win_rate_5d, 3) if win_rate_5d is not None else None,
                    'avg_return_5d': round(avg_return_5d, 4) if avg_return_5d is not None else None,
                    'win_rate_10d': round(win_rate_10d, 3) if win_rate_10d is not None else None,
                    'avg_return_10d': round(avg_return_10d, 4) if avg_return_10d is not None else None,
                    'win_rate_20d': round(win_rate_20d, 3) if win_rate_20d is not None else None,
                    'avg_return_20d': round(avg_return_20d, 4) if avg_return_20d is not None else None,
                    'recommendation': recommendation
                })
            
            # 按 5 日平均收益排序
            rule_list.sort(key=lambda x: x['avg_return_5d'] if x['avg_return_5d'] is not None else -999, reverse=True)
            
            # 4. 生成摘要
            total_signals = len(signals)
            signals_with_rules = total_signals - unattributed_count
            unique_rules = len(rule_stats)
            
            result = {
                'date_range': {
                    'start': start_date,
                    'end': end_date
                },
                'summary': {
                    'total_signals': total_signals,
                    'signals_with_rules': signals_with_rules,
                    'unattributed_signals': unattributed_count,
                    'unique_rules': unique_rules,
                    'attribution_rate': round(signals_with_rules / total_signals, 3) if total_signals > 0 else 0
                },
                'rule_stats': rule_list,
                'recommendations': self._summarize_recommendations(rule_list)
            }
            
            logger.info(
                "attribution_analysis_complete",
                total_signals=total_signals,
                unique_rules=unique_rules,
                attribution_rate=result['summary']['attribution_rate']
            )
            
            return result
        
        finally:
            cursor.close()
    
    def _extract_rule_ids(self, reason: str) -> List[str]:
        """从 reason 字段提取规则 ID
        
        支持格式：
        - R-001
        - R001
        - 规则R-001
        - 引用R-001和R-002
        """
        if not reason:
            return []
        
        # 正则匹配 R-xxx 或 Rxxx
        pattern = r'R-?\d{3,}'
        matches = re.findall(pattern, reason, re.IGNORECASE)
        
        # 标准化为 R-xxx 格式
        rule_ids = []
        for match in matches:
            if '-' in match:
                rule_ids.append(match.upper())
            else:
                # R001 -> R-001
                num = match[1:]
                rule_ids.append(f'R-{num}')
        
        return list(set(rule_ids))  # 去重
    
    def _generate_recommendation(
        self,
        count: int,
        win_rate: float,
        avg_pnl_pct: float,
        min_samples: int
    ) -> str:
        """生成规则建议
        
        逻辑：
        - 样本不足（<min_samples）：observe
        - 持续亏损（win_rate<0.3 且 avg_pnl_pct<-0.05）：deprecate
        - 优秀表现（win_rate>0.7 且 avg_pnl_pct>0.05）：strengthen
        - 一般表现：keep
        """
        if count < min_samples:
            return 'observe'  # 样本不足，继续观察
        
        if win_rate < 0.3 and avg_pnl_pct < -0.05:
            return 'deprecate'  # 建议淘汰
        
        if win_rate > 0.7 and avg_pnl_pct > 0.05:
            return 'strengthen'  # 建议强化
        
        return 'keep'  # 保持
    
    def _summarize_recommendations(self, rule_list: List[Dict]) -> Dict[str, List[str]]:
        """汇总建议
        
        Returns:
            {
                "strengthen": ["R-001", "R-005"],
                "keep": ["R-002", "R-003"],
                "observe": ["R-010"],
                "deprecate": ["R-008"]
            }
        """
        result = {
            'strengthen': [],
            'keep': [],
            'observe': [],
            'deprecate': []
        }
        
        for rule in rule_list:
            rec = rule['recommendation']
            result[rec].append(rule['rule_id'])
        
        return result
