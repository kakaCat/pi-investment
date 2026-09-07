"""M6-2 周报生成服务

功能：
- 汇总本周交易表现
- 信号质量统计
- 规则归因分析
- Regime 变化记录
- 自动生成周报并推送

用于：每周复盘、经验沉淀、持续改进
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import structlog

logger = structlog.get_logger(__name__)


class WeeklyReportService:
    """周报生成服务"""
    
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
    
    def generate_weekly_report(
        self,
        week_start: Optional[str] = None,
        week_end: Optional[str] = None
    ) -> Dict[str, Any]:
        """生成周报
        
        Args:
            week_start: 周开始日期 YYYY-MM-DD（默认上周一）
            week_end: 周结束日期 YYYY-MM-DD（默认上周日）
        
        Returns:
            {
                "period": {
                    "start": "2026-08-18",
                    "end": "2026-08-24",
                    "week_num": 34
                },
                "summary": {
                    "total_signals": 20,
                    "trades_executed": 15,
                    "win_rate": 0.6,
                    "total_return": 0.05
                },
                "signals": {...},
                "attribution": {...},
                "regime_changes": [...],
                "highlights": [...],
                "recommendations": [...]
            }
        """
        # 默认时间范围：上周一到上周日
        if not week_start or not week_end:
            today = datetime.now()
            last_monday = today - timedelta(days=today.weekday() + 7)
            last_sunday = last_monday + timedelta(days=6)
            week_start = last_monday.strftime('%Y-%m-%d')
            week_end = last_sunday.strftime('%Y-%m-%d')
        
        logger.info("generating_weekly_report", week_start=week_start, week_end=week_end)
        
        # 1. 信号统计
        signals_stats = self._get_signals_stats(week_start, week_end)
        
        # 2. 规则归因
        from application.services.attribution_service import AttributionService
        attribution_service = AttributionService(self.db)
        attribution = attribution_service.analyze_rule_performance(
            start_date=week_start,
            end_date=week_end,
            min_samples=3
        )
        
        # 3. Regime 变化
        regime_changes = self._get_regime_changes(week_start, week_end)
        
        # 4. 生成亮点
        highlights = self._generate_highlights(signals_stats, attribution, regime_changes)
        
        # 5. 生成建议
        recommendations = self._generate_recommendations(attribution)
        
        # 6. 汇总
        week_num = datetime.strptime(week_start, '%Y-%m-%d').isocalendar()[1]
        
        report = {
            'period': {
                'start': week_start,
                'end': week_end,
                'week_num': week_num,
                'year': datetime.strptime(week_start, '%Y-%m-%d').year
            },
            'summary': {
                'total_signals': signals_stats['total'],
                'signals_with_performance': signals_stats['with_performance'],
                'avg_win_rate_5d': signals_stats['avg_win_rate_5d'],
                'avg_return_5d': signals_stats['avg_return_5d']
            },
            'signals': signals_stats,
            'attribution': {
                'unique_rules': attribution['summary']['unique_rules'],
                'top_rules': attribution['rule_stats'][:3] if attribution['rule_stats'] else [],
                'recommendations': attribution['recommendations']
            },
            'regime_changes': regime_changes,
            'highlights': highlights,
            'recommendations': recommendations
        }
        
        logger.info(
            "weekly_report_generated",
            week_start=week_start,
            total_signals=signals_stats['total'],
            unique_rules=attribution['summary']['unique_rules']
        )
        
        return report
    
    def _get_signals_stats(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """获取信号统计"""
        cursor = self.db.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN return_5d IS NOT NULL THEN 1 END) as with_performance,
                    AVG(CASE WHEN hit_5d = true THEN 1.0 ELSE 0.0 END) as avg_win_rate_5d,
                    AVG(return_5d) as avg_return_5d,
                    COUNT(CASE WHEN grade = 'A' THEN 1 END) as grade_a,
                    COUNT(CASE WHEN grade = 'B' THEN 1 END) as grade_b,
                    COUNT(CASE WHEN grade = 'C' THEN 1 END) as grade_c
                FROM quant.signal_tracking
                WHERE signal_date >= %s AND signal_date <= %s
            """, (start_date, end_date))
            
            row = cursor.fetchone()
            
            return {
                'total': row[0] or 0,
                'with_performance': row[1] or 0,
                'avg_win_rate_5d': round(float(row[2] or 0), 3),
                'avg_return_5d': round(float(row[3] or 0), 4),
                'grade_a': row[4] or 0,
                'grade_b': row[5] or 0,
                'grade_c': row[6] or 0
            }
        
        finally:
            cursor.close()
    
    def _get_regime_changes(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """获取 Regime 变化记录
        
        TODO: 需要实现 regime 历史表后才能查询
        当前返回空列表
        """
        return []
    
    def _generate_highlights(
        self,
        signals_stats: Dict,
        attribution: Dict,
        regime_changes: List
    ) -> List[str]:
        """生成周度亮点"""
        highlights = []
        
        # 信号质量亮点
        if signals_stats['total'] > 0:
            win_rate = signals_stats['avg_win_rate_5d']
            if win_rate > 0.7:
                highlights.append(f"✅ 本周信号质量优秀：5日胜率 {win_rate*100:.1f}%")
            elif win_rate < 0.4:
                highlights.append(f"⚠️  本周信号质量偏低：5日胜率 {win_rate*100:.1f}%")
        
        # 规则表现亮点
        if attribution['rule_stats']:
            top_rule = attribution['rule_stats'][0]
            if top_rule.get('avg_return_5d') and top_rule['avg_return_5d'] > 0.05:
                highlights.append(
                    f"🏆 最佳规则：{top_rule['rule_id']} "
                    f"(胜率 {top_rule.get('win_rate_5d', 0)*100:.0f}%, "
                    f"平均收益 {top_rule['avg_return_5d']*100:.2f}%)"
                )
        
        # Regime 变化
        if regime_changes:
            highlights.append(f"📊 Regime 变化 {len(regime_changes)} 次")
        
        return highlights
    
    def _generate_recommendations(self, attribution: Dict) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        recs = attribution.get('recommendations', {})
        
        # 强化建议
        if recs.get('strengthen'):
            recommendations.append(
                f"💪 建议强化规则：{', '.join(recs['strengthen'][:3])} "
                f"（高胜率高收益）"
            )
        
        # 淘汰建议
        if recs.get('deprecate'):
            recommendations.append(
                f"🗑️  建议淘汰规则：{', '.join(recs['deprecate'])} "
                f"（持续亏损）"
            )
        
        # 观察建议
        if recs.get('observe'):
            recommendations.append(
                f"👀 继续观察规则：{', '.join(recs['observe'][:3])} "
                f"（样本不足）"
            )
        
        return recommendations
    
    def format_markdown(self, report: Dict[str, Any]) -> str:
        """格式化为 Markdown"""
        md = f"""# 投资周报 - 第{report['period']['week_num']}周

**时间范围**: {report['period']['start']} ~ {report['period']['end']}

---

## 📊 本周概览

- **信号数量**: {report['summary']['total_signals']}
- **已回填表现**: {report['summary']['signals_with_performance']}
- **5日胜率**: {report['summary']['avg_win_rate_5d']*100:.1f}%
- **5日平均收益**: {report['summary']['avg_return_5d']*100:.2f}%

### 信号分级分布
- A级（标准仓）: {report['signals']['grade_a']}
- B级（半仓）: {report['signals']['grade_b']}
- C级（观察）: {report['signals']['grade_c']}

---

## 🎯 规则归因

**本周活跃规则**: {report['attribution']['unique_rules']} 条

### Top 3 规则
"""
        
        for i, rule in enumerate(report['attribution']['top_rules'], 1):
            win_rate = rule.get('win_rate_5d', 0)
            avg_return = rule.get('avg_return_5d', 0)
            md += f"\n{i}. **{rule['rule_id']}** - "
            md += f"引用 {rule['count']} 次, "
            md += f"胜率 {win_rate*100 if win_rate else 'N/A'}%, "
            md += f"平均收益 {avg_return*100 if avg_return else 'N/A'}%"
        
        md += "\n\n---\n\n## ✨ 本周亮点\n\n"
        for highlight in report['highlights']:
            md += f"- {highlight}\n"
        
        md += "\n---\n\n## 💡 改进建议\n\n"
        for rec in report['recommendations']:
            md += f"- {rec}\n"
        
        md += "\n---\n\n*本报告由 M6 学习飞轮自动生成*"
        
        return md
    
    def generate_and_push(
        self,
        week_start: Optional[str] = None,
        week_end: Optional[str] = None,
        feishu_webhook: Optional[str] = None
    ) -> Dict[str, Any]:
        """生成周报并推送到飞书
        
        Args:
            week_start: 周开始日期（默认上周一）
            week_end: 周结束日期（默认上周日）
            feishu_webhook: 飞书 webhook URL（如不提供则仅生成不推送）
        
        Returns:
            {
                "success": true,
                "report": {...},
                "push_result": {...}
            }
        """
        # 1. 生成周报
        report = self.generate_weekly_report(week_start, week_end)
        markdown = self.format_markdown(report)
        
        result = {
            'success': True,
            'report': report,
            'markdown': markdown,
            'push_result': None
        }
        
        # 2. 推送到飞书
        if feishu_webhook:
            try:
                import requests
                
                # 构建飞书卡片消息
                card_content = {
                    "msg_type": "interactive",
                    "card": {
                        "header": {
                            "title": {
                                "tag": "plain_text",
                                "content": f"📊 投资周报 - 第{report['period']['week_num']}周"
                            },
                            "template": "blue"
                        },
                        "elements": [
                            {
                                "tag": "div",
                                "text": {
                                    "tag": "lark_md",
                                    "content": markdown
                                }
                            }
                        ]
                    }
                }
                
                response = requests.post(
                    feishu_webhook,
                    json=card_content,
                    timeout=10
                )
                
                response_data = response.json()
                
                if response.ok and response_data.get('code') == 0:
                    result['push_result'] = {
                        'success': True,
                        'message': '飞书推送成功',
                        'feishu_code': response_data.get('code')
                    }
                    logger.info(
                        "weekly_report_pushed_to_feishu",
                        week=report['period']['week_num'],
                        webhook=feishu_webhook[:50] + "..."
                    )
                else:
                    result['push_result'] = {
                        'success': False,
                        'error': f"飞书返回错误: {response_data}",
                        'http_status': response.status_code
                    }
                    logger.error(
                        "feishu_push_failed",
                        error=response_data,
                        status=response.status_code
                    )
                    result['success'] = False
                    
            except Exception as e:
                result['push_result'] = {
                    'success': False,
                    'error': str(e)
                }
                logger.error("feishu_push_exception", error=str(e), exc_info=True)
                result['success'] = False
        
        return result
