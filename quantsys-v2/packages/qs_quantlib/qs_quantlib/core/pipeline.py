"""
Pipeline模式实现

统一因子→模型→回测的调用方式
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class PipelineStage(ABC):
    """Pipeline阶段基类"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理数据

        Args:
            data: 输入数据

        Returns:
            处理后的数据
        """
        pass

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """验证输入数据"""
        return True

    def on_error(self, error: Exception, data: Dict[str, Any]) -> Dict[str, Any]:
        """错误处理"""
        logger.error(f"Stage {self.name} error: {error}")
        raise error


class QuantPipeline:
    """
    量化Pipeline - 统一因子→模型→回测的调用方式

    用法1：一次性运行全部
    >>> pipeline = QuantPipeline("full_analysis")
    >>> pipeline.add_stage(FactorStage())
    >>> pipeline.add_stage(ModelStage())
    >>> pipeline.add_stage(BacktestStage())
    >>> result = pipeline.run({"symbol": "600000"})

    用法2：分步运行
    >>> factors = pipeline.run_until("factors", {"symbol": "600000"})
    >>> prediction = pipeline.run_until("prediction", {"symbol": "600000"})
    """

    def __init__(self, name: str):
        self.name = name
        self.stages: List[PipelineStage] = []
        self._stage_map: Dict[str, int] = {}

    def add_stage(self, stage: PipelineStage) -> 'QuantPipeline':
        """添加Stage（支持链式调用）"""
        self.stages.append(stage)
        self._stage_map[stage.name] = len(self.stages) - 1
        logger.info(f"Pipeline '{self.name}' added stage: {stage.name}")
        return self

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """运行完整Pipeline"""
        return self._execute(input_data, end_stage=None)

    def run_until(self, stage_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """运行到指定Stage"""
        if stage_name not in self._stage_map:
            raise ValueError(f"Stage '{stage_name}' not found in pipeline")
        return self._execute(input_data, end_stage=stage_name)

    def _execute(
        self,
        input_data: Dict[str, Any],
        end_stage: Optional[str] = None
    ) -> Dict[str, Any]:
        """执行Pipeline"""
        data = input_data.copy()
        end_index = self._stage_map.get(end_stage, len(self.stages) - 1) if end_stage else len(self.stages) - 1

        logger.info(f"Pipeline '{self.name}' started")

        for i, stage in enumerate(self.stages):
            if i > end_index:
                break

            try:
                if not stage.validate_input(data):
                    raise ValueError(f"Stage '{stage.name}' input validation failed")

                logger.info(f"Executing stage: {stage.name}")
                data = stage.process(data)

                if stage.name == end_stage:
                    logger.info(f"Pipeline stopped at stage: {stage.name}")
                    return data

            except Exception as e:
                logger.error(f"Pipeline '{self.name}' failed at stage '{stage.name}': {e}")
                data = stage.on_error(e, data)

        logger.info(f"Pipeline '{self.name}' completed")
        return data
