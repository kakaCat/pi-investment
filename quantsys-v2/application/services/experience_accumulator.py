"""
经验自动积累服务

从策略表现统计中自动生成经验条目，写入经验库供 Agent 查询
"""
import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import date
from pathlib import Path
import structlog

from application.services.signal_test_log import SignalTestLog
from domain.ports import IStrategyPerformanceRepository

logger = structlog.get_logger(__name__)


class ExperienceAccumulator:
    """经验积累器"""

    def __init__(self):
        self.signal_log = SignalTestLog()
        self.perf_repo = IStrategyPerformanceRepository()

    def accumulate_from_performance(
        self,
        strategy_name: str,
        symbol: Optional[str] = None,
        min_samples: int = 10,
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        从策略表现统计中积累经验

        Args:
            strategy_name: 策略名称
            symbol: 股票代码（可选）
            min_samples: 最小样本数
            output_file: 输出文件路径（可选）

        Returns:
            {
                'success': bool,
                'experience_created': bool,
                'experience_id': str (if created),
                'experience': dict (if created),
                'reason': str (if not created)
            }
        """
        # 获取纸面测试统计
        paper_stats = self._get_paper_stats(strategy_name, symbol)

        # 获取实盘统计
        live_stats = self.perf_repo.get_statistics(
            strategy_name=strategy_name,
            symbol=symbol,
            source='live'
        )

        # 计算总样本数
        total_samples = paper_stats.get('verified_trades', 0)
        if live_stats:
            total_samples += live_stats.get('total_trades', 0)

        # 检查样本数是否足够
        if total_samples < min_samples:
            return {
                'success': True,
                'experience_created': False,
                'reason': f'Insufficient samples: {total_samples} < {min_samples}'
            }

        # 生成经验条目
        experience = self._create_experience_entry(
            strategy_name=strategy_name,
            symbol=symbol,
            paper_stats=paper_stats,
            live_stats=live_stats
        )

        # 保存到文件（如果指定）
        if output_file:
            self._save_to_file(experience, output_file)

        return {
            'success': True,
            'experience_created': True,
            'experience_id': experience['id'],
            'experience': experience
        }

    def accumulate_all(
        self,
        min_samples: int = 10,
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        批量积累所有策略的经验

        Args:
            min_samples: 最小样本数
            output_file: 输出文件路径（可选）

        Returns:
            {
                'success': bool,
                'total_processed': int,
                'experiences_created': int,
                'experiences': list
            }
        """
        # 获取所有策略-标的组合
        combinations = self._get_strategy_symbol_combinations()

        experiences = []
        for strategy_name, symbol in combinations:
            result = self.accumulate_from_performance(
                strategy_name=strategy_name,
                symbol=symbol,
                min_samples=min_samples,
                output_file=None  # 批量处理时不单独保存
            )

            if result['experience_created']:
                experiences.append(result['experience'])

        # 批量保存到文件
        if output_file and experiences:
            self._save_all_to_file(experiences, output_file)

        return {
            'success': True,
            'total_processed': len(combinations),
            'experiences_created': len(experiences),
            'experiences': experiences
        }

    def _get_paper_stats(self, strategy_name: str, symbol: Optional[str] = None) -> Dict:
        """获取纸面测试统计"""
        conn = self.signal_log._get_conn()
        cursor = None
        try:
            cursor = conn.cursor()

            conditions = ["strategy_name = %s", "status = 'verified'"]
            params = [strategy_name]

            if symbol:
                conditions.append("symbol = %s")
                params.append(symbol)

            where_clause = " AND ".join(conditions)

            query = f"""
                SELECT
                    COUNT(*) as verified_trades,
                    AVG(pnl_pct) as avg_pnl_pct,
                    MAX(pnl_pct) as max_pnl_pct,
                    MIN(pnl_pct) as min_pnl_pct,
                    SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as win_trades
                FROM {self.signal_log.TABLE_NAME}
                WHERE {where_clause}
            """

            cursor.execute(query, tuple(params))
            result = cursor.fetchone()
        finally:
            if cursor:
                cursor.close()
            conn.close()

        if not result or result[0] == 0:
            return {
                'verified_trades': 0,
                'avg_pnl_pct': 0.0,
                'win_rate': 0.0
            }

        verified_trades = result[0]
        avg_pnl_pct = float(result[1]) if result[1] is not None else 0.0
        max_pnl_pct = float(result[2]) if result[2] is not None else 0.0
        min_pnl_pct = float(result[3]) if result[3] is not None else 0.0
        win_trades = result[4]

        win_rate = (win_trades / verified_trades * 100) if verified_trades > 0 else 0.0

        return {
            'verified_trades': verified_trades,
            'avg_pnl_pct': avg_pnl_pct,
            'max_pnl_pct': max_pnl_pct,
            'min_pnl_pct': min_pnl_pct,
            'win_rate': win_rate
        }

    def _create_experience_entry(
        self,
        strategy_name: str,
        symbol: Optional[str],
        paper_stats: Dict,
        live_stats: Optional[Dict]
    ) -> Dict:
        """创建经验条目"""
        # 计算综合统计
        total_cases = paper_stats['verified_trades']
        if live_stats:
            total_cases += live_stats.get('total_trades', 0)

        # 加权平均收益
        paper_weight = paper_stats['verified_trades']
        live_weight = live_stats.get('total_trades', 0) if live_stats else 0

        if paper_weight + live_weight > 0:
            avg_return = (
                paper_stats['avg_pnl_pct'] * paper_weight +
                (live_stats.get('avg_pnl_pct', 0) if live_stats else 0) * live_weight
            ) / (paper_weight + live_weight)
        else:
            avg_return = 0.0

        # 综合胜率
        paper_win_trades = paper_stats['verified_trades'] * paper_stats['win_rate'] / 100
        live_win_trades = live_stats.get('win_trades', 0) if live_stats else 0
        total_win_trades = paper_win_trades + live_win_trades

        win_rate = (total_win_trades / total_cases * 100) if total_cases > 0 else 0.0

        # 生成场景描述
        scenario = f"使用 {strategy_name} 策略"
        if symbol:
            scenario += f" 交易 {symbol}"

        # 生成条件
        conditions = [
            f"策略: {strategy_name}",
        ]
        if symbol:
            conditions.append(f"标的: {symbol}")

        # 生成推荐
        recommendation = self._generate_recommendation(win_rate, avg_return)

        # 生成原因
        reason = self._generate_reason(win_rate, avg_return, total_cases)

        return {
            'id': str(uuid.uuid4()),
            'scenario': scenario,
            'pattern': {
                'conditions': conditions,
                'action': 'buy'  # 默认买入信号
            },
            'outcomes': {
                'total_cases': total_cases,
                'win_rate': round(win_rate, 2),
                'avg_return': round(avg_return, 2),
                'max_gain': round(paper_stats.get('max_pnl_pct', 0), 2),
                'max_loss': round(paper_stats.get('min_pnl_pct', 0), 2)
            },
            'recommendation': recommendation,
            'reason': reason,
            'examples': []  # 可以后续添加具体案例
        }

    def _generate_recommendation(self, win_rate: float, avg_return: float) -> str:
        """生成推荐等级"""
        if win_rate >= 70 and avg_return >= 3:
            return 'aggressive'
        elif win_rate >= 60 and avg_return >= 2:
            return 'moderate'
        elif win_rate >= 50 and avg_return >= 1:
            return 'cautious'
        else:
            return 'avoid'

    def _generate_reason(self, win_rate: float, avg_return: float, total_cases: int) -> str:
        """生成推荐原因"""
        return (
            f"基于 {total_cases} 个历史案例，"
            f"胜率 {win_rate:.1f}%，"
            f"平均收益 {avg_return:.2f}%"
        )

    def _get_strategy_symbol_combinations(self) -> List[tuple]:
        """获取所有策略-标的组合"""
        conn = self.signal_log._get_conn()
        cursor = None
        try:
            cursor = conn.cursor()

            query = f"""
                SELECT DISTINCT strategy_name, symbol
                FROM {self.signal_log.TABLE_NAME}
                WHERE status = 'verified'
            """

            cursor.execute(query)
            results = cursor.fetchall()
            return [(row[0], row[1]) for row in results]
        finally:
            if cursor:
                cursor.close()
            conn.close()

    def _save_to_file(self, experience: Dict, output_file: str):
        """保存单个经验到文件"""
        file_path = Path(output_file)

        # 读取现有经验库
        if file_path.exists():
            with open(file_path, 'r') as f:
                data = json.load(f)
        else:
            data = {
                'version': '1.0.0',
                'last_updated': date.today().isoformat(),
                'experiences': []
            }

        # 添加新经验
        data['experiences'].append(experience)
        data['last_updated'] = date.today().isoformat()

        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _save_all_to_file(self, experiences: List[Dict], output_file: str):
        """批量保存经验到文件"""
        file_path = Path(output_file)

        data = {
            'version': '1.0.0',
            'last_updated': date.today().isoformat(),
            'experiences': experiences
        }

        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
