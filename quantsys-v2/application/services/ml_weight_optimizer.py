"""
机器学习权重优化服务

使用 Ridge Regression 学习最优因子权重
"""
from typing import Dict, List, Optional
import structlog
import numpy as np

logger = structlog.get_logger(__name__)


class MLWeightOptimizer:
    """机器学习权重优化器"""

    def __init__(self):
        self.model = None
        self.factor_names = None

    def optimize_weights(
        self,
        factor_values: np.ndarray,
        forward_returns: np.ndarray,
        factor_names: List[str],
        alpha: float = 1.0
    ) -> Dict:
        """
        使用 Ridge Regression 优化因子权重

        Args:
            factor_values: 因子值矩阵 (n_samples, n_factors)
            forward_returns: 未来收益序列 (n_samples,)
            factor_names: 因子名称列表
            alpha: 正则化系数

        Returns:
            {
                'weights': Dict[str, float],    # 因子权重
                'model_score': float,           # R² 分数
                'coefficients': List[float],    # 原始系数
                'intercept': float              # 截距
            }
        """
        try:
            from sklearn.linear_model import Ridge
            from sklearn.preprocessing import StandardScaler
            
            # 1. 数据验证
            if len(factor_values) != len(forward_returns):
                raise ValueError("因子值和收益序列长度不匹配")
            
            if len(factor_values) < 30:
                logger.warning("训练样本过少 (< 30)，结果可能不稳定")
            
            # 2. 标准化
            scaler = StandardScaler()
            X = scaler.fit_transform(factor_values)
            y = forward_returns
            
            # 3. 训练 Ridge Regression
            model = Ridge(alpha=alpha)
            model.fit(X, y)
            
            # 4. 获取系数
            coefficients = model.coef_
            intercept = model.intercept_
            score = model.score(X, y)
            
            # 5. 转换为权重（取绝对值并归一化）
            abs_coefs = np.abs(coefficients)
            total = np.sum(abs_coefs)
            
            if total == 0:
                total = 1.0
            
            weights_array = abs_coefs / total
            
            # 6. 映射到因子名称
            weights = {}
            for i, factor_name in enumerate(factor_names):
                weights[factor_name] = float(weights_array[i])
            
            # 7. 按维度聚合权重
            dimension_weights = self._aggregate_to_dimensions(weights)
            
            logger.info(
                f"ML权重优化完成: R²={score:.3f}, "
                f"维度权重={dimension_weights}"
            )
            
            result = {
                'weights': dimension_weights,
                'factor_weights': weights,
                'model_score': round(score, 3),
                'coefficients': [round(c, 4) for c in coefficients.tolist()],
                'intercept': round(float(intercept), 4),
                'n_samples': len(factor_values)
            }
            
            # 保存模型
            self.model = model
            self.factor_names = factor_names
            
            return result
            
        except ImportError:
            logger.error("sklearn 未安装，无法使用 ML 权重优化")
            return self._get_default_result()
        except Exception as e:
            logger.error(f"ML权重优化失败: {e}", exc_info=True)
            return self._get_default_result()

    def _aggregate_to_dimensions(self, factor_weights: Dict[str, float]) -> Dict[str, float]:
        """将因子权重聚合到维度权重"""
        dimension_weights = {
            'technical': 0.0,
            'fundamental': 0.0,
            'capital': 0.0
        }
        
        # 因子分类
        technical_factors = ['rsi', 'macd', 'bollinger', 'momentum']
        fundamental_factors = ['roe', 'pe', 'pb', 'debt_ratio', 'gross_margin']
        
        for factor_name, weight in factor_weights.items():
            if factor_name.lower() in technical_factors:
                dimension_weights['technical'] += weight
            elif factor_name.lower() in fundamental_factors:
                dimension_weights['fundamental'] += weight
            else:
                dimension_weights['capital'] += weight
        
        # 归一化
        total = sum(dimension_weights.values())
        if total > 0:
            dimension_weights = {k: v / total for k, v in dimension_weights.items()}
        
        return {k: round(v, 3) for k, v in dimension_weights.items()}

    def predict(self, factor_values: np.ndarray) -> np.ndarray:
        """使用训练好的模型预测"""
        if self.model is None:
            raise ValueError("模型未训练，请先调用 optimize_weights()")
        
        return self.model.predict(factor_values)

    def _get_default_result(self) -> Dict:
        """返回默认结果"""
        return {
            'weights': {
                'technical': 0.5,
                'fundamental': 0.3,
                'capital': 0.2
            },
            'factor_weights': {},
            'model_score': 0.0,
            'coefficients': [],
            'intercept': 0.0,
            'n_samples': 0,
            'error': 'ML optimization failed, using default weights'
        }
