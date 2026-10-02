"""集成测试 - 端到端测试"""
import pytest
from infrastructure.quantlib.core.pipeline import QuantPipeline
from domain.backtest.stages.factor_stage import FactorStage
from adapters.outbound.repositories import StockORMRepository


class TestEndToEndFlow:
    """端到端流程

    2026-10-02（REQ-261001145152-3982 审查）：本文件原有 6 条用例（分布在本类与
    TestRepositoryIntegration）注入的是 **DB-API 连接**（`StockORMRepository(db_connection=MockDB())`，
    MockDB 提供 cursor()/execute()/fetchone()）—— 那是 **ORM 迁移前**的注入方式，
    现已移除：`BaseORMRepository.__init__()` **不接受任何参数**（自动取 scoped session），
    故这些用例一律 `TypeError: unexpected keyword argument 'db_connection'`。
    它们测的是一个**不存在的实现层**（同 TestSignalRepositoryMocked 的情形），已删除；
    若要重测真实仓储行为，应另写基于 ORM/真实库的用例。类内其余用例（纯 Pipeline 流程）保留。
    """
    """测试端到端流程"""


    def test_pipeline_with_multiple_stages(self):
        """测试多Stage的Pipeline"""
        # 创建一个简单的验证Stage
        from infrastructure.quantlib.core.pipeline import PipelineStage
        from typing import Dict, Any

        class ValidationStage(PipelineStage):
            """验证Stage"""

            def __init__(self, name: str = "validation"):
                super().__init__(name)

            def validate_input(self, data: Dict[str, Any]) -> bool:
                if "symbol" not in data:
                    raise ValueError("Missing symbol")
                return True

            def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
                # 添加验证标记
                result = data.copy()
                result["validated"] = True
                return result

        # 创建Pipeline
        pipeline = QuantPipeline(name="multi_stage_test")
        pipeline.add_stage(ValidationStage(name="validation"))
        pipeline.add_stage(FactorStage(name="factors"))

        # 准备数据
        klines = []
        for i in range(30):
            klines.append({
                "date": f"2026-05-{i+1:02d}",
                "close": 100.0 + i,
                "high": 102.0 + i,
                "low": 99.0 + i,
                "open": 100.5 + i,
                "volume": 1000000
            })

        # 运行Pipeline
        result = pipeline.run({
            "symbol": "000001",
            "klines": klines
        })

        # 验证结果
        assert result["validated"] == True
        assert "factors" in result
        assert len(result["factors"]) > 0

    def test_pipeline_error_handling(self):
        """测试Pipeline错误处理"""
        pipeline = QuantPipeline(name="error_test")
        pipeline.add_stage(FactorStage(name="factors"))

        # 缺少必要字段
        with pytest.raises(ValueError, match="Missing required field: symbol"):
            pipeline.run({
                "klines": [{"close": 100.0}]
            })

        # klines类型错误
        with pytest.raises(ValueError, match="klines must be a list"):
            pipeline.run({
                "symbol": "000001",
                "klines": "not a list"
            })



    def test_pipeline_data_flow(self):
        """测试Pipeline数据流转"""
        from infrastructure.quantlib.core.pipeline import PipelineStage
        from typing import Dict, Any

        # 创建一个数据转换Stage
        class TransformStage(PipelineStage):
            """数据转换Stage"""

            def __init__(self, name: str = "transform"):
                super().__init__(name)

            def validate_input(self, data: Dict[str, Any]) -> bool:
                return True

            def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
                result = data.copy()
                result["transformed"] = True
                result["stage_count"] = data.get("stage_count", 0) + 1
                return result

        # 创建Pipeline
        pipeline = QuantPipeline(name="data_flow_test")
        pipeline.add_stage(TransformStage(name="transform1"))
        pipeline.add_stage(TransformStage(name="transform2"))
        pipeline.add_stage(TransformStage(name="transform3"))

        # 运行Pipeline
        result = pipeline.run({
            "symbol": "000001",
            "data": "test"
        })

        # 验证数据流转
        assert result["transformed"] == True
        assert result["stage_count"] == 3  # 经过3个Stage


    def test_pipeline_stage_isolation(self):
        """测试Pipeline Stage隔离性"""
        from infrastructure.quantlib.core.pipeline import PipelineStage
        from typing import Dict, Any

        # 创建一个修改输入数据的Stage
        class MutatingStage(PipelineStage):
            """修改数据的Stage"""

            def __init__(self, name: str = "mutating"):
                super().__init__(name)

            def validate_input(self, data: Dict[str, Any]) -> bool:
                return True

            def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
                # 修改输入数据
                result = data.copy()
                result["mutated"] = True
                return result

        # 创建Pipeline
        pipeline = QuantPipeline(name="isolation_test")
        pipeline.add_stage(MutatingStage(name="stage1"))
        pipeline.add_stage(MutatingStage(name="stage2"))

        # 原始数据
        original_data = {
            "symbol": "000001",
            "value": 100
        }

        # 运行Pipeline
        result = pipeline.run(original_data)

        # 验证原始数据未被修改
        assert "mutated" not in original_data
        assert result["mutated"] == True


class TestRepositoryIntegration:
    """测试Repository集成"""



class TestPipelineIntegration:
    """测试Pipeline集成"""

    def test_pipeline_stage_order(self):
        """测试Pipeline Stage执行顺序"""
        from infrastructure.quantlib.core.pipeline import PipelineStage
        from typing import Dict, Any

        execution_order = []

        class OrderTrackingStage(PipelineStage):
            """跟踪执行顺序的Stage"""

            def __init__(self, name: str, order_list: list):
                super().__init__(name)
                self.order_list = order_list

            def validate_input(self, data: Dict[str, Any]) -> bool:
                return True

            def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
                self.order_list.append(self.name)
                return data

        # 创建Pipeline
        pipeline = QuantPipeline(name="order_test")
        pipeline.add_stage(OrderTrackingStage(name="stage1", order_list=execution_order))
        pipeline.add_stage(OrderTrackingStage(name="stage2", order_list=execution_order))
        pipeline.add_stage(OrderTrackingStage(name="stage3", order_list=execution_order))

        # 运行Pipeline
        pipeline.run({"data": "test"})

        # 验证执行顺序
        assert execution_order == ["stage1", "stage2", "stage3"]

    def test_pipeline_empty_stages(self):
        """测试空Pipeline"""
        pipeline = QuantPipeline(name="empty_test")

        # 空Pipeline应该直接返回输入数据
        result = pipeline.run({"symbol": "000001"})
        assert result["symbol"] == "000001"
