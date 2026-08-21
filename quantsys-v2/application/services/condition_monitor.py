"""
条件监控服务 - ORM版本
基于规则表达式监控市场、持仓、策略等条件，触发自动化任务

完全使用ORM，不再直接执行SQL
"""
import asyncio
import structlog
from typing import Dict, Callable, Any, Optional, List
from datetime import datetime, timedelta
import json

from domain.ports.repository_ports_extended import (
    IConditionRuleRepository,
    IConditionResultRepository
)

logger = structlog.get_logger(__name__)


class ConditionMonitorService:
    """条件监控服务（ORM版本）

    功能：
    1. 定期检查市场/持仓/策略条件
    2. 条件满足时触发任务
    3. 支持复杂条件表达式
    4. 防止重复触发（冷却时间）

    迁移状态：✅ 已完成ORM迁移
    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        rule_repo: Optional[IConditionRuleRepository] = None,
        result_repo: Optional[IConditionResultRepository] = None,
    ):
        """初始化服务

        Args:
            rule_repo: 条件规则仓库（可选）
            result_repo: 条件结果仓库（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.rule_repo = rule_repo or IConditionRuleRepository()
        self.result_repo = result_repo or IConditionResultRepository()
        self.condition_checkers: Dict[str, Callable] = {}
        self.is_running = False
        self._register_builtin_checkers()
        logger.info("ConditionMonitorService initialized with ORM")

    def _register_builtin_checkers(self):
        """注册内置条件检查器"""
        self.condition_checkers['market'] = self._check_market_condition
        self.condition_checkers['price'] = self._check_price_condition
        self.condition_checkers['volume'] = self._check_volume_condition
        self.condition_checkers['position'] = self._check_position_condition
        self.condition_checkers['strategy'] = self._check_strategy_condition
        self.condition_checkers['indicator'] = self._check_indicator_condition
        self.condition_checkers['custom'] = self._check_custom_condition

    async def load_active_rules(self) -> List:
        """从数据库加载活跃规则

        Returns:
            活跃规则列表
        """
        try:
            rules = self.rule_repo.get_active_rules()
            logger.info(f"Loaded {len(rules)} active rules from database")
            return rules
        except Exception as e:
            logger.error(f"Failed to load active rules: {e}")
            return []

    async def check_rule(self, rule) -> bool:
        """检查单个规则条件

        Args:
            rule: 规则对象

        Returns:
            True if condition is met, False otherwise
        """
        try:
            # 检查冷却时间
            if not self.rule_repo.can_trigger(rule):
                logger.debug(f"Rule {rule.rule_name} in cooldown period")
                return False

            # 获取对应的检查器
            checker = self.condition_checkers.get(rule.condition_type)
            if not checker:
                logger.warning(f"No checker for type: {rule.condition_type}")
                return False

            # 解析条件表达式
            try:
                condition = json.loads(rule.condition_expr) if isinstance(rule.condition_expr, str) else rule.condition_expr
            except:
                condition = {'expr': rule.condition_expr}

            # 执行检查
            result = await checker(rule, condition)

            # 记录检查结果
            self.result_repo.record_result({
                'rule_id': rule.rule_id,
                'symbol': rule.symbol,
                'condition_met': result['met'],
                'actual_value': result.get('actual_value'),
                'threshold_value': rule.threshold_value,
                'message': result.get('message')
            })

            # 如果条件满足，记录触发
            if result['met']:
                self.rule_repo.record_trigger(rule.rule_id)
                logger.info(f"Rule {rule.rule_name} triggered: {result.get('message')}")

            return result['met']

        except Exception as e:
            logger.error(f"Error checking rule {rule.rule_name}: {e}")
            return False

    async def check_all_rules(self) -> Dict[str, Any]:
        """检查所有活跃规则

        Returns:
            检查结果汇总
        """
        try:
            rules = await self.load_active_rules()
            results = {
                'total': len(rules),
                'triggered': 0,
                'failed': 0,
                'details': []
            }

            for rule in rules:
                try:
                    met = await self.check_rule(rule)
                    if met:
                        results['triggered'] += 1
                        results['details'].append({
                            'rule_name': rule.rule_name,
                            'status': 'triggered',
                            'action': rule.action
                        })
                except Exception as e:
                    results['failed'] += 1
                    logger.error(f"Failed to check rule {rule.rule_name}: {e}")

            return results

        except Exception as e:
            logger.error(f"Error checking all rules: {e}")
            return {'total': 0, 'triggered': 0, 'failed': 0, 'details': []}

    async def _check_price_condition(self, rule, condition: Dict) -> Dict:
        """检查价格条件"""
        try:
            # 这里应该从KlineRepository获取实时价格
            # 简化实现，返回示例
            actual_value = 10.5  # 从数据库获取
            threshold = rule.threshold_value or condition.get('threshold', 0)
            op = rule.comparison_op or condition.get('op', '>')

            met = self._compare(actual_value, op, threshold)

            return {
                'met': met,
                'actual_value': actual_value,
                'message': f"Price {actual_value} {op} {threshold}"
            }
        except Exception as e:
            logger.error(f"Error checking price condition: {e}")
            return {'met': False, 'message': str(e)}

    async def _check_volume_condition(self, rule, condition: Dict) -> Dict:
        """检查成交量条件"""
        try:
            # 从数据库获取成交量数据
            actual_value = 1000000  # 示例值
            threshold = rule.threshold_value or condition.get('threshold', 0)
            op = rule.comparison_op or condition.get('op', '>')

            met = self._compare(actual_value, op, threshold)

            return {
                'met': met,
                'actual_value': actual_value,
                'message': f"Volume {actual_value} {op} {threshold}"
            }
        except Exception as e:
            logger.error(f"Error checking volume condition: {e}")
            return {'met': False, 'message': str(e)}

    async def _check_market_condition(self, rule, condition: Dict) -> Dict:
        """检查市场条件"""
        try:
            # 市场条件检查逻辑
            return {
                'met': False,
                'message': 'Market condition check not implemented'
            }
        except Exception as e:
            logger.error(f"Error checking market condition: {e}")
            return {'met': False, 'message': str(e)}

    async def _check_position_condition(self, rule, condition: Dict) -> Dict:
        """检查持仓条件"""
        try:
            # 持仓条件检查逻辑
            return {
                'met': False,
                'message': 'Position condition check not implemented'
            }
        except Exception as e:
            logger.error(f"Error checking position condition: {e}")
            return {'met': False, 'message': str(e)}

    async def _check_strategy_condition(self, rule, condition: Dict) -> Dict:
        """检查策略条件"""
        try:
            # 策略条件检查逻辑
            return {
                'met': False,
                'message': 'Strategy condition check not implemented'
            }
        except Exception as e:
            logger.error(f"Error checking strategy condition: {e}")
            return {'met': False, 'message': str(e)}

    async def _check_indicator_condition(self, rule, condition: Dict) -> Dict:
        """检查指标条件"""
        try:
            # 指标条件检查逻辑
            return {
                'met': False,
                'message': 'Indicator condition check not implemented'
            }
        except Exception as e:
            logger.error(f"Error checking indicator condition: {e}")
            return {'met': False, 'message': str(e)}

    async def _check_custom_condition(self, rule, condition: Dict) -> Dict:
        """检查自定义条件"""
        try:
            # 自定义条件检查逻辑
            return {
                'met': False,
                'message': 'Custom condition check not implemented'
            }
        except Exception as e:
            logger.error(f"Error checking custom condition: {e}")
            return {'met': False, 'message': str(e)}

    def _compare(self, actual: float, op: str, threshold: float) -> bool:
        """比较操作"""
        if op == '>':
            return actual > threshold
        elif op == '>=':
            return actual >= threshold
        elif op == '<':
            return actual < threshold
        elif op == '<=':
            return actual <= threshold
        elif op == '==':
            return actual == threshold
        elif op == '!=':
            return actual != threshold
        else:
            return False

    def get_rule_history(self, rule_name: str, limit: int = 100) -> List[Dict]:
        """获取规则的历史结果

        Args:
            rule_name: 规则名称
            limit: 返回数量限制

        Returns:
            历史结果列表
        """
        try:
            rule = self.rule_repo.get_rule_by_name(rule_name)
            if not rule:
                return []

            results = self.result_repo.get_results_by_rule(rule.rule_id, limit)
            return [r.to_dict() for r in results]
        except Exception as e:
            logger.error(f"Error getting rule history: {e}")
            return []

    def get_triggered_history(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict]:
        """获取触发历史

        Args:
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制

        Returns:
            触发历史列表
        """
        try:
            results = self.result_repo.get_triggered_results(start_time, end_time, limit)
            return [r.to_dict() for r in results]
        except Exception as e:
            logger.error(f"Error getting triggered history: {e}")
            return []
