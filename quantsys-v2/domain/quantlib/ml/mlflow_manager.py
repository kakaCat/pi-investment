"""
MLflow模型管理 - Team B
模型版本管理、实验跟踪、模型对比
"""
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# 尝试导入MLflow
try:
    import mlflow
    import mlflow.sklearn
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.warning("MLflow not available, using simplified version")


class MLflowManager:
    """
    MLflow模型管理

    功能:
    1. 实验跟踪
    2. 模型版本管理
    3. 模型对比
    4. 模型部署
    """

    def __init__(self, tracking_uri: str = None, experiment_name: str = "default"):
        """
        Args:
            tracking_uri: MLflow服务地址
            experiment_name: 实验名称
        """
        self.tracking_uri = tracking_uri or "file:./mlruns"
        self.experiment_name = experiment_name
        self.current_run = None

        if MLFLOW_AVAILABLE:
            mlflow.set_tracking_uri(self.tracking_uri)
            mlflow.set_experiment(experiment_name)
            logger.info(f"MLflow initialized: {self.tracking_uri}, experiment={experiment_name}")
        else:
            logger.warning("MLflow not available, using mock implementation")

    def start_run(self, run_name: str = None) -> str:
        """
        开始一个新的运行

        Returns:
            run_id
        """
        if MLFLOW_AVAILABLE:
            self.current_run = mlflow.start_run(run_name=run_name)
            run_id = self.current_run.info.run_id
            logger.info(f"Started MLflow run: {run_id}")
            return run_id
        else:
            # Mock实现
            import uuid
            run_id = str(uuid.uuid4())
            logger.info(f"Started mock run: {run_id}")
            return run_id

    def end_run(self):
        """结束当前运行"""
        if MLFLOW_AVAILABLE and self.current_run:
            mlflow.end_run()
            logger.info("Ended MLflow run")
        self.current_run = None

    def log_params(self, params: Dict[str, Any]):
        """
        记录参数

        Args:
            params: 参数字典
        """
        if MLFLOW_AVAILABLE:
            mlflow.log_params(params)
            logger.debug(f"Logged params: {list(params.keys())}")
        else:
            logger.debug(f"Mock log params: {params}")

    def log_metrics(self, metrics: Dict[str, float], step: int = None):
        """
        记录指标

        Args:
            metrics: 指标字典
            step: 步数（用于绘制曲线）
        """
        if MLFLOW_AVAILABLE:
            mlflow.log_metrics(metrics, step=step)
            logger.debug(f"Logged metrics: {list(metrics.keys())}")
        else:
            logger.debug(f"Mock log metrics: {metrics}")

    def log_model(self, model: Any, artifact_path: str = "model") -> str:
        """
        保存模型

        Args:
            model: 模型对象
            artifact_path: 模型保存路径

        Returns:
            model_uri
        """
        if MLFLOW_AVAILABLE:
            # 根据模型类型选择合适的log方法
            model_type = type(model).__name__

            if 'sklearn' in str(type(model).__module__):
                mlflow.sklearn.log_model(model, artifact_path)
            else:
                # 使用通用的pickle保存
                import pickle
                import tempfile
                with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pkl') as f:
                    pickle.dump(model, f)
                    mlflow.log_artifact(f.name, artifact_path)

            model_uri = f"runs:/{self.current_run.info.run_id}/{artifact_path}"
            logger.info(f"Logged model: {model_uri}")
            return model_uri
        else:
            logger.info(f"Mock log model: {artifact_path}")
            return f"mock://{artifact_path}"

    def load_model(self, run_id: str, artifact_path: str = "model") -> Any:
        """
        加载模型

        Args:
            run_id: 运行ID
            artifact_path: 模型路径

        Returns:
            model
        """
        if MLFLOW_AVAILABLE:
            model_uri = f"runs:/{run_id}/{artifact_path}"
            try:
                model = mlflow.sklearn.load_model(model_uri)
                logger.info(f"Loaded model from {model_uri}")
                return model
            except Exception as e:
                logger.warning(f"Failed to load sklearn model: {e}, trying pickle")
                # 尝试用pickle加载
                import pickle
                artifact_path_full = mlflow.get_artifact_uri(artifact_path)
                with open(artifact_path_full, 'rb') as f:
                    model = pickle.load(f)
                return model
        else:
            logger.info(f"Mock load model: {run_id}/{artifact_path}")
            return None

    def search_runs(self, filter_string: str = "", max_results: int = 100) -> List[Dict]:
        """
        搜索运行

        Args:
            filter_string: 过滤条件，例如 "metrics.accuracy > 0.9"
            max_results: 最大结果数

        Returns:
            运行列表
        """
        if MLFLOW_AVAILABLE:
            runs = mlflow.search_runs(
                experiment_names=[self.experiment_name],
                filter_string=filter_string,
                max_results=max_results
            )
            logger.info(f"Found {len(runs)} runs")
            return runs.to_dict('records')
        else:
            logger.info("Mock search runs")
            return []

    def compare_models(self, run_ids: List[str]) -> Dict:
        """
        对比多个模型

        Args:
            run_ids: 运行ID列表

        Returns:
            对比结果
        """
        if not MLFLOW_AVAILABLE:
            logger.info("Mock compare models")
            return {}

        comparison = {
            'run_ids': run_ids,
            'metrics': {},
            'params': {}
        }

        for run_id in run_ids:
            run = mlflow.get_run(run_id)

            # 收集指标
            for metric_name, metric_value in run.data.metrics.items():
                if metric_name not in comparison['metrics']:
                    comparison['metrics'][metric_name] = {}
                comparison['metrics'][metric_name][run_id] = metric_value

            # 收集参数
            for param_name, param_value in run.data.params.items():
                if param_name not in comparison['params']:
                    comparison['params'][param_name] = {}
                comparison['params'][param_name][run_id] = param_value

        logger.info(f"Compared {len(run_ids)} models")
        return comparison

    def register_model(self, model_uri: str, model_name: str) -> str:
        """
        注册模型到模型注册表

        Args:
            model_uri: 模型URI
            model_name: 模型名称

        Returns:
            model_version
        """
        if MLFLOW_AVAILABLE:
            result = mlflow.register_model(model_uri, model_name)
            version = result.version
            logger.info(f"Registered model {model_name} version {version}")
            return version
        else:
            logger.info(f"Mock register model: {model_name}")
            return "1"

    def transition_model_stage(self, model_name: str, version: str, stage: str):
        """
        转换模型阶段

        Args:
            model_name: 模型名称
            version: 版本号
            stage: 阶段 ('Staging', 'Production', 'Archived')
        """
        if MLFLOW_AVAILABLE:
            from mlflow.tracking import MlflowClient
            client = MlflowClient()
            client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage=stage
            )
            logger.info(f"Transitioned {model_name} v{version} to {stage}")
        else:
            logger.info(f"Mock transition: {model_name} v{version} -> {stage}")

    def get_production_model(self, model_name: str) -> Any:
        """
        获取生产环境模型

        Args:
            model_name: 模型名称

        Returns:
            model
        """
        if MLFLOW_AVAILABLE:
            model_uri = f"models:/{model_name}/Production"
            model = mlflow.sklearn.load_model(model_uri)
            logger.info(f"Loaded production model: {model_name}")
            return model
        else:
            logger.info(f"Mock get production model: {model_name}")
            return None


# 便捷函数
def quick_log_model(model: Any, params: Dict, metrics: Dict,
                   experiment_name: str = "default",
                   model_name: str = None) -> str:
    """
    快速记录模型

    Returns:
        run_id
    """
    manager = MLflowManager(experiment_name=experiment_name)

    run_id = manager.start_run()
    manager.log_params(params)
    manager.log_metrics(metrics)
    model_uri = manager.log_model(model)

    if model_name:
        manager.register_model(model_uri, model_name)

    manager.end_run()

    return run_id
