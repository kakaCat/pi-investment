"""
数据库查询优化分析

分析 quantsys-v2 中的 SQL 查询，识别性能瓶颈和优化机会。
"""
from typing import List, Dict, Tuple


class QueryOptimizationAnalyzer:
    """数据库查询优化分析器"""

    def __init__(self):
        self.findings: List[Dict] = []
        self.index_recommendations: List[Dict] = []

    def analyze_kline_repository(self):
        """分析 KlineRepository 的查询"""

        # 1. get_daily_klines - 范围查询
        self.findings.append({
            'repository': 'KlineRepository',
            'method': 'get_daily_klines',
            'query': 'SELECT * FROM quant.daily_klines WHERE symbol = %s AND trade_date >= %s AND trade_date <= %s',
            'issue': '频繁的范围查询，需要复合索引',
            'impact': 'HIGH',
            'frequency': 'VERY_HIGH',
        })

        self.index_recommendations.append({
            'table': 'quant.daily_klines',
            'index_name': 'idx_daily_klines_symbol_date',
            'columns': ['symbol', 'trade_date'],
            'type': 'BTREE',
            'reason': '优化按股票代码和日期范围查询',
            'sql': 'CREATE INDEX IF NOT EXISTS idx_daily_klines_symbol_date ON quant.daily_klines(symbol, trade_date);',
        })

        # 2. get_daily_klines_batch - IN查询
        self.findings.append({
            'repository': 'KlineRepository',
            'method': 'get_daily_klines_batch',
            'query': 'SELECT * FROM quant.daily_klines WHERE symbol = ANY(%s) AND trade_date >= %s AND trade_date <= %s',
            'issue': '批量查询多个股票，可能导致全表扫描',
            'impact': 'HIGH',
            'frequency': 'HIGH',
            'optimization': '使用复合索引 + 考虑分区表',
        })

        # 3. get_latest_daily_kline - ORDER BY + LIMIT
        self.findings.append({
            'repository': 'KlineRepository',
            'method': 'get_latest_daily_kline',
            'query': 'SELECT * FROM quant.daily_klines WHERE symbol = %s ORDER BY trade_date DESC LIMIT 1',
            'issue': '每次都需要排序，即使只取一条',
            'impact': 'MEDIUM',
            'frequency': 'VERY_HIGH',
            'optimization': '复合索引 (symbol, trade_date DESC) 可避免排序',
        })

        self.index_recommendations.append({
            'table': 'quant.daily_klines',
            'index_name': 'idx_daily_klines_symbol_date_desc',
            'columns': ['symbol', 'trade_date DESC'],
            'type': 'BTREE',
            'reason': '优化获取最新K线，避免排序',
            'sql': 'CREATE INDEX IF NOT EXISTS idx_daily_klines_symbol_date_desc ON quant.daily_klines(symbol, trade_date DESC);',
        })

        # 4. get_trading_days - DISTINCT查询
        self.findings.append({
            'repository': 'KlineRepository',
            'method': 'get_trading_days',
            'query': 'SELECT DISTINCT trade_date FROM quant.daily_klines WHERE trade_date >= %s AND trade_date <= %s',
            'issue': 'DISTINCT 需要排序和去重，成本较高',
            'impact': 'MEDIUM',
            'frequency': 'MEDIUM',
            'optimization': '考虑维护单独的交易日历表',
        })

    def analyze_factor_repository(self):
        """分析 FactorRepository 的查询"""

        # 1. get_factors - 多行转字典
        self.findings.append({
            'repository': 'FactorRepository',
            'method': 'get_factors',
            'query': 'SELECT factor_name, factor_value FROM quant.factor_values WHERE symbol = %s AND factor_date = %s',
            'issue': '每次查询返回多行，需要在应用层聚合',
            'impact': 'MEDIUM',
            'frequency': 'VERY_HIGH',
        })

        self.index_recommendations.append({
            'table': 'quant.factor_values',
            'index_name': 'idx_factor_values_symbol_date',
            'columns': ['symbol', 'factor_date'],
            'type': 'BTREE',
            'reason': '优化按股票和日期查询因子',
            'sql': 'CREATE INDEX IF NOT EXISTS idx_factor_values_symbol_date ON quant.factor_values(symbol, factor_date);',
        })

        # 2. get_latest_factors - 子查询
        self.findings.append({
            'repository': 'FactorRepository',
            'method': 'get_latest_factors',
            'query': '''SELECT factor_name, factor_value FROM quant.factor_values
                        WHERE symbol = %s AND factor_date = (SELECT MAX(factor_date) FROM quant.factor_values WHERE symbol = %s)''',
            'issue': '子查询执行两次，且子查询可能不使用索引',
            'impact': 'HIGH',
            'frequency': 'VERY_HIGH',
            'optimization': '使用窗口函数或JOIN优化',
        })

        # 优化建议
        self.findings.append({
            'repository': 'FactorRepository',
            'method': 'get_latest_factors (优化)',
            'query': '''WITH latest AS (
                            SELECT symbol, MAX(factor_date) as max_date
                            FROM quant.factor_values
                            WHERE symbol = %s
                            GROUP BY symbol
                        )
                        SELECT fv.factor_name, fv.factor_value
                        FROM quant.factor_values fv
                        JOIN latest l ON fv.symbol = l.symbol AND fv.factor_date = l.max_date''',
            'issue': None,
            'impact': 'OPTIMIZATION',
            'frequency': 'VERY_HIGH',
        })

        # 3. get_factors_batch - N+1问题
        self.findings.append({
            'repository': 'FactorRepository',
            'method': 'get_factors_batch',
            'query': 'SELECT symbol, factor_name, factor_value FROM quant.factor_values WHERE symbol = ANY(%s) AND factor_date = %s',
            'issue': '批量查询，但返回大量行需要应用层分组',
            'impact': 'MEDIUM',
            'frequency': 'HIGH',
            'optimization': '已经是批量查询，主要优化在索引',
        })

        # 4. get_factor_history - 时间序列查询
        self.findings.append({
            'repository': 'FactorRepository',
            'method': 'get_factor_history',
            'query': '''SELECT factor_date, factor_value FROM quant.factor_values
                        WHERE symbol = %s AND factor_name = %s AND factor_date >= %s AND factor_date <= %s''',
            'issue': '需要复合索引支持',
            'impact': 'MEDIUM',
            'frequency': 'MEDIUM',
        })

        self.index_recommendations.append({
            'table': 'quant.factor_values',
            'index_name': 'idx_factor_values_symbol_name_date',
            'columns': ['symbol', 'factor_name', 'factor_date'],
            'type': 'BTREE',
            'reason': '优化因子历史查询',
            'sql': 'CREATE INDEX IF NOT EXISTS idx_factor_values_symbol_name_date ON quant.factor_values(symbol, factor_name, factor_date);',
        })

        # 5. get_factor_coverage - 聚合查询
        self.findings.append({
            'repository': 'FactorRepository',
            'method': 'get_factor_coverage',
            'query': '''SELECT (SELECT COUNT(DISTINCT symbol) FROM quant.stocks) as total_stocks,
                               COUNT(DISTINCT symbol) as covered_stocks
                        FROM quant.factor_values WHERE factor_name = %s AND factor_date = %s''',
            'issue': '子查询每次都扫描stocks表',
            'impact': 'LOW',
            'frequency': 'LOW',
            'optimization': '缓存total_stocks或使用物化视图',
        })

    def analyze_data_service(self):
        """分析 DataService 的查询模式"""

        # 1. get_stock_full_data - 多次查询
        self.findings.append({
            'repository': 'DataService',
            'method': 'get_stock_full_data',
            'query': 'Multiple sequential queries',
            'issue': '顺序执行多个查询：stock_info, klines, factors, signals, stats',
            'impact': 'HIGH',
            'frequency': 'HIGH',
            'optimization': '使用缓存 + 考虑并行查询（连接池）',
        })

        # 2. batch_get_latest_factors - 循环查询
        self.findings.append({
            'repository': 'DataService',
            'method': 'batch_get_latest_factors',
            'query': 'Loop calling factor.get_latest_factors',
            'issue': 'N+1查询问题：循环调用get_latest_factors',
            'impact': 'CRITICAL',
            'frequency': 'HIGH',
            'optimization': '改为单次批量查询',
        })

        # 优化建议
        self.findings.append({
            'repository': 'DataService',
            'method': 'batch_get_latest_factors (优化)',
            'query': '''WITH latest_dates AS (
                            SELECT symbol, MAX(factor_date) as max_date
                            FROM quant.factor_values
                            WHERE symbol = ANY(%s)
                            GROUP BY symbol
                        )
                        SELECT fv.symbol, fv.factor_name, fv.factor_value
                        FROM quant.factor_values fv
                        JOIN latest_dates ld ON fv.symbol = ld.symbol AND fv.factor_date = ld.max_date''',
            'issue': None,
            'impact': 'OPTIMIZATION',
            'frequency': 'HIGH',
        })

    def analyze_portfolio_repository(self):
        """分析 PortfolioRepository 的查询"""

        self.findings.append({
            'repository': 'PortfolioRepository',
            'method': 'get_trades_by_symbol',
            'query': 'SELECT * FROM quant.trades WHERE symbol = %s ORDER BY trade_time DESC',
            'issue': '需要索引支持排序',
            'impact': 'MEDIUM',
            'frequency': 'MEDIUM',
        })

        self.index_recommendations.append({
            'table': 'quant.trades',
            'index_name': 'idx_trades_symbol_time',
            'columns': ['symbol', 'trade_time DESC'],
            'type': 'BTREE',
            'reason': '优化按股票查询交易记录',
            'sql': 'CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON quant.trades(symbol, trade_time DESC);',
        })

    def generate_report(self) -> str:
        """生成优化报告"""
        report = []

        report.append("=" * 80)
        report.append("数据库查询优化分析报告")
        report.append("=" * 80)
        report.append("")

        # 执行分析
        self.analyze_kline_repository()
        self.analyze_factor_repository()
        self.analyze_data_service()
        self.analyze_portfolio_repository()

        # 按影响程度分组
        critical = [f for f in self.findings if f.get('impact') == 'CRITICAL']
        high = [f for f in self.findings if f.get('impact') == 'HIGH']
        medium = [f for f in self.findings if f.get('impact') == 'MEDIUM']
        low = [f for f in self.findings if f.get('impact') == 'LOW']
        optimizations = [f for f in self.findings if f.get('impact') == 'OPTIMIZATION']

        # 关键问题
        if critical:
            report.append("## 🔴 关键问题 (CRITICAL)")
            report.append("")
            for finding in critical:
                report.append(f"### {finding['repository']}.{finding['method']}")
                report.append(f"- **问题**: {finding['issue']}")
                report.append(f"- **频率**: {finding['frequency']}")
                if 'optimization' in finding:
                    report.append(f"- **优化建议**: {finding['optimization']}")
                report.append("")

        # 高影响问题
        if high:
            report.append("## 🟠 高影响问题 (HIGH)")
            report.append("")
            for finding in high:
                report.append(f"### {finding['repository']}.{finding['method']}")
                report.append(f"- **问题**: {finding['issue']}")
                report.append(f"- **频率**: {finding['frequency']}")
                if 'optimization' in finding:
                    report.append(f"- **优化建议**: {finding['optimization']}")
                report.append("")

        # 中等影响问题
        if medium:
            report.append("## 🟡 中等影响问题 (MEDIUM)")
            report.append("")
            for finding in medium:
                report.append(f"### {finding['repository']}.{finding['method']}")
                report.append(f"- **问题**: {finding['issue']}")
                report.append(f"- **频率**: {finding['frequency']}")
                if 'optimization' in finding:
                    report.append(f"- **优化建议**: {finding['optimization']}")
                report.append("")

        # 索引建议
        report.append("## 📊 索引建议")
        report.append("")
        report.append("以下索引可以显著提升查询性能：")
        report.append("")

        for idx, rec in enumerate(self.index_recommendations, 1):
            report.append(f"### {idx}. {rec['index_name']}")
            report.append(f"- **表**: {rec['table']}")
            report.append(f"- **列**: {', '.join(rec['columns'])}")
            report.append(f"- **原因**: {rec['reason']}")
            report.append(f"- **SQL**:")
            report.append(f"```sql")
            report.append(rec['sql'])
            report.append(f"```")
            report.append("")

        # 优化查询示例
        if optimizations:
            report.append("## ✅ 优化查询示例")
            report.append("")
            for opt in optimizations:
                report.append(f"### {opt['repository']}.{opt['method']}")
                report.append(f"```sql")
                report.append(opt['query'])
                report.append(f"```")
                report.append("")

        # 通用优化建议
        report.append("## 💡 通用优化建议")
        report.append("")
        report.append("1. **连接池配置**")
        report.append("   - 增加连接池大小以支持并发查询")
        report.append("   - 配置合理的连接超时和空闲超时")
        report.append("")
        report.append("2. **查询日志**")
        report.append("   - 启用慢查询日志 (log_min_duration_statement = 100ms)")
        report.append("   - 定期分析慢查询并优化")
        report.append("")
        report.append("3. **批量操作**")
        report.append("   - 使用 execute_batch 替代循环插入")
        report.append("   - 批量查询时使用 ANY(%s) 或 IN 子句")
        report.append("")
        report.append("4. **缓存策略**")
        report.append("   - 对频繁查询的数据使用缓存（如最新K线、因子值）")
        report.append("   - 设置合理的TTL避免数据过期")
        report.append("")
        report.append("5. **分区表**")
        report.append("   - 对大表（如daily_klines）考虑按日期分区")
        report.append("   - 提升范围查询和数据维护性能")
        report.append("")
        report.append("6. **物化视图**")
        report.append("   - 对复杂聚合查询使用物化视图")
        report.append("   - 定期刷新以保持数据新鲜度")
        report.append("")

        # 性能监控
        report.append("## 📈 性能监控建议")
        report.append("")
        report.append("```sql")
        report.append("-- 查看表大小")
        report.append("SELECT schemaname, tablename, ")
        report.append("       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size")
        report.append("FROM pg_tables")
        report.append("WHERE schemaname = 'quant'")
        report.append("ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;")
        report.append("")
        report.append("-- 查看索引使用情况")
        report.append("SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch")
        report.append("FROM pg_stat_user_indexes")
        report.append("WHERE schemaname = 'quant'")
        report.append("ORDER BY idx_scan DESC;")
        report.append("")
        report.append("-- 查看未使用的索引")
        report.append("SELECT schemaname, tablename, indexname")
        report.append("FROM pg_stat_user_indexes")
        report.append("WHERE schemaname = 'quant' AND idx_scan = 0;")
        report.append("```")
        report.append("")

        return "\n".join(report)


def main():
    """生成优化分析报告"""
    analyzer = QueryOptimizationAnalyzer()
    report = analyzer.generate_report()
    print(report)

    # 保存到文件
    output_file = "/Users/mac/Documents/ai/pi-investment/quantsys-v2/docs/database-optimization-analysis.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n报告已保存到: {output_file}")


if __name__ == '__main__':
    main()
