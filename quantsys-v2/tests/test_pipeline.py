"""
测试Pipeline模式

目标：统一因子→模型→回测的调用方式
"""
import pytest
from domain.quantlib.core.pipeline import QuantPipeline, PipelineStage


class TestPipelineBasics:
    """测试Pipeline基础功能"""

    def test_create_empty_pipeline(self):
        """测试创建空Pipeline"""
        pipeline = QuantPipeline(name="test_pipeline")

        assert pipeline.name == "test_pipeline"
        assert len(pipeline.stages) == 0

    def test_add_stage(self):
        """测试添加Stage"""
        pipeline = QuantPipeline(name="test")

        # 创建Mock Stage
        class MockStage(PipelineStage):
            def process(self, data):
                return {"result": "mock"}

        stage = MockStage(name="mock_stage")
        pipeline.add_stage(stage)

        assert len(pipeline.stages) == 1
        assert pipeline.stages[0].name == "mock_stage"

    def test_pipeline_execution_order(self):
        """测试Pipeline执行顺序"""
        pipeline = QuantPipeline(name="test")
        execution_order = []

        class Stage1(PipelineStage):
            def process(self, data):
                execution_order.append("stage1")
                return {"stage1": "done"}

        class Stage2(PipelineStage):
            def process(self, data):
                execution_order.append("stage2")
                return {"stage2": "done"}

        pipeline.add_stage(Stage1(name="stage1"))
        pipeline.add_stage(Stage2(name="stage2"))

        pipeline.run({"input": "data"})

        assert execution_order == ["stage1", "stage2"], "执行顺序应该是stage1→stage2"


class TestPipelineDataFlow:
    """测试Pipeline数据流转"""

    def test_data_passing_between_stages(self):
        """测试Stage之间的数据传递"""
        pipeline = QuantPipeline(name="test")

        class AddStage(PipelineStage):
            def process(self, data):
                return {"value": data.get("value", 0) + 10}

        class MultiplyStage(PipelineStage):
            def process(self, data):
                return {"value": data.get("value", 0) * 2}

        pipeline.add_stage(AddStage(name="add"))
        pipeline.add_stage(MultiplyStage(name="multiply"))

        result = pipeline.run({"value": 5})

        # (5 + 10) * 2 = 30
        assert result["value"] == 30, "数据应该在Stage间正确传递"


class TestPipelinePartialExecution:
    """测试Pipeline部分执行"""

    def test_run_until_specific_stage(self):
        """测试运行到指定Stage"""
        pipeline = QuantPipeline(name="test")

        class Stage1(PipelineStage):
            def process(self, data):
                return {"stage": "1"}

        class Stage2(PipelineStage):
            def process(self, data):
                return {"stage": "2"}

        class Stage3(PipelineStage):
            def process(self, data):
                return {"stage": "3"}

        pipeline.add_stage(Stage1(name="stage1"))
        pipeline.add_stage(Stage2(name="stage2"))
        pipeline.add_stage(Stage3(name="stage3"))

        # 只运行到stage2
        result = pipeline.run_until("stage2", {"input": "data"})

        assert result["stage"] == "2", "应该只运行到stage2"
