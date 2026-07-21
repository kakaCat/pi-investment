# Phase 2: 核心能力提升 (3-4个月)

**目标**: 从90分提升到95分 (+5分)  
**时间**: 3-4个月  
**重点**: 提升技术深度

---

## 任务清单

### 1. 机器学习升级 (+4分)

#### 1.1 深度学习模型集成 (4周)

**目标**: 支持LSTM/Transformer/GRU时序预测

**技术方案**:

```python
# ml/models/lstm_predictor.py

import torch
import torch.nn as nn

class LSTMPredictor(nn.Module):
    """LSTM时序预测模型"""
    
    def __init__(self, input_size: int, hidden_size: int = 128, 
                 num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout,
            batch_first=True
        )
        self.fc = nn.Linear(hidden_size, 1)
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x):
        # x shape: (batch, seq_len, input_size)
        lstm_out, _ = self.lstm(x)
        # 取最后一个时间步
        last_output = lstm_out[:, -1, :]
        output = self.fc(last_output)
        return self.sigmoid(output)

# ml/models/transformer_predictor.py

class TransformerPredictor(nn.Module):
    """Transformer注意力机制预测模型"""
    
    def __init__(self, input_size: int, d_model: int = 128, 
                 nhead: int = 8, num_layers: int = 3):
        super().__init__()
        self.embedding = nn.Linear(input_size, d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, 
            nhead=nhead,
            dim_feedforward=512,
            dropout=0.1
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers)
        self.fc = nn.Linear(d_model, 1)
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x):
        # x shape: (batch, seq_len, input_size)
        x = self.embedding(x)
        # Transformer expects (seq_len, batch, d_model)
        x = x.transpose(0, 1)
        transformer_out = self.transformer(x)
        # 取最后一个时间步
        last_output = transformer_out[-1, :, :]
        output = self.fc(last_output)
        return self.sigmoid(output)

# ml/trainer.py 增强

class DeepLearningTrainer:
    """深度学习模型训练器"""
    
    def __init__(self, model_type: str = 'lstm'):
        self.model_type = model_type
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    def train(self, train_data: pd.DataFrame, val_data: pd.DataFrame,
              epochs: int = 100, batch_size: int = 32):
        """训练模型"""
        # 准备数据
        train_loader = self._prepare_dataloader(train_data, batch_size)
        val_loader = self._prepare_dataloader(val_data, batch_size)
        
        # 创建模型
        if self.model_type == 'lstm':
            model = LSTMPredictor(input_size=train_data.shape[1])
        elif self.model_type == 'transformer':
            model = TransformerPredictor(input_size=train_data.shape[1])
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
        
        model = model.to(self.device)
        
        # 训练循环
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        criterion = nn.BCELoss()
        
        best_val_loss = float('inf')
        for epoch in range(epochs):
            train_loss = self._train_epoch(model, train_loader, optimizer, criterion)
            val_loss = self._validate(model, val_loader, criterion)
            
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                torch.save(model.state_dict(), 'best_model.pth')
            
            print(f"Epoch {epoch}: train_loss={train_loss:.4f}, val_loss={val_loss:.4f}")
        
        return model
```

**集成到Pipeline**:
```python
# quant/stages/model_stage.py 增强

class ModelStage(PipelineStage):
    def __init__(self, model_type: str = 'xgboost'):
        self.model_type = model_type
        if model_type in ['lstm', 'transformer', 'gru']:
            self.model = self._load_deep_learning_model(model_type)
        else:
            self.model = self._load_xgboost_model()
    
    def _load_deep_learning_model(self, model_type: str):
        """加载深度学习模型"""
        import torch
        if model_type == 'lstm':
            model = LSTMPredictor(input_size=39)
        elif model_type == 'transformer':
            model = TransformerPredictor(input_size=39)
        
        model.load_state_dict(torch.load(f'models/{model_type}_latest.pth'))
        model.eval()
        return model
```

**验收标准**:
- [ ] LSTM模型实现并训练
- [ ] Transformer模型实现并训练
- [ ] GRU模型实现并训练
- [ ] 模型性能 > XGBoost基线
- [ ] GPU加速支持

---

#### 1.2 MLflow模型版本管理 (2周)

**目标**: 实验跟踪和模型版本管理

**技术方案**:
```python
# ml/mlflow_manager.py

import mlflow
import mlflow.pytorch
import mlflow.xgboost

class MLflowManager:
    """MLflow实验管理"""
    
    def __init__(self, tracking_uri: str = "http://localhost:5000"):
        mlflow.set_tracking_uri(tracking_uri)
    
    def start_experiment(self, experiment_name: str):
        """开始实验"""
        mlflow.set_experiment(experiment_name)
        return mlflow.start_run()
    
    def log_params(self, params: dict):
        """记录参数"""
        mlflow.log_params(params)
    
    def log_metrics(self, metrics: dict, step: int = None):
        """记录指标"""
        mlflow.log_metrics(metrics, step=step)
    
    def log_model(self, model, model_type: str = 'pytorch'):
        """保存模型"""
        if model_type == 'pytorch':
            mlflow.pytorch.log_model(model, "model")
        elif model_type == 'xgboost':
            mlflow.xgboost.log_model(model, "model")
    
    def load_model(self, run_id: str, model_type: str = 'pytorch'):
        """加载模型"""
        model_uri = f"runs:/{run_id}/model"
        if model_type == 'pytorch':
            return mlflow.pytorch.load_model(model_uri)
        elif model_type == 'xgboost':
            return mlflow.xgboost.load_model(model_uri)

# 使用示例
with MLflowManager().start_experiment("stock_prediction"):
    mlflow.log_params({
        "model_type": "lstm",
        "hidden_size": 128,
        "num_layers": 2,
        "learning_rate": 0.001
    })
    
    # 训练模型
    model = train_model()
    
    # 记录指标
    mlflow.log_metrics({
        "train_loss": 0.123,
        "val_loss": 0.145,
        "accuracy": 0.876
    })
    
    # 保存模型
    mlflow.pytorch.log_model(model, "model")
```

**验收标准**:
- [ ] MLflow服务部署
- [ ] 实验跟踪功能
- [ ] 模型版本管理
- [ ] 模型对比功能

---

#### 1.3 A/B测试框架 (2周)

**目标**: 支持多模型在线对比

**技术方案**:
```python
# ml/ab_testing.py

class ABTestingFramework:
    """A/B测试框架"""
    
    def __init__(self):
        self.experiments = {}
    
    def create_experiment(self, name: str, models: dict, 
                         traffic_split: dict):
        """
        创建A/B测试实验
        
        Args:
            name: 实验名称
            models: 模型字典 {'model_a': model_a, 'model_b': model_b}
            traffic_split: 流量分配 {'model_a': 0.5, 'model_b': 0.5}
        """
        self.experiments[name] = {
            'models': models,
            'traffic_split': traffic_split,
            'metrics': {k: [] for k in models.keys()}
        }
    
    def get_model(self, experiment_name: str, user_id: str):
        """根据用户ID分配模型"""
        experiment = self.experiments[experiment_name]
        
        # 使用哈希确保同一用户总是分配到同一模型
        hash_value = hash(user_id) % 100
        
        cumulative = 0
        for model_name, split in experiment['traffic_split'].items():
            cumulative += split * 100
            if hash_value < cumulative:
                return experiment['models'][model_name], model_name
    
    def record_metric(self, experiment_name: str, model_name: str, 
                     metric_value: float):
        """记录指标"""
        self.experiments[experiment_name]['metrics'][model_name].append(metric_value)
    
    def get_results(self, experiment_name: str) -> dict:
        """获取实验结果"""
        experiment = self.experiments[experiment_name]
        results = {}
        
        for model_name, metrics in experiment['metrics'].items():
            results[model_name] = {
                'mean': np.mean(metrics),
                'std': np.std(metrics),
                'count': len(metrics)
            }
        
        # 统计显著性检验
        if len(experiment['models']) == 2:
            model_names = list(experiment['models'].keys())
            metrics_a = experiment['metrics'][model_names[0]]
            metrics_b = experiment['metrics'][model_names[1]]
            
            from scipy import stats
            t_stat, p_value = stats.ttest_ind(metrics_a, metrics_b)
            results['statistical_test'] = {
                't_statistic': t_stat,
                'p_value': p_value,
                'significant': p_value < 0.05
            }
        
        return results

# 使用示例
ab_test = ABTestingFramework()
ab_test.create_experiment(
    name='lstm_vs_transformer',
    models={'lstm': lstm_model, 'transformer': transformer_model},
    traffic_split={'lstm': 0.5, 'transformer': 0.5}
)

# 预测时
model, model_name = ab_test.get_model('lstm_vs_transformer', user_id='user123')
prediction = model.predict(features)

# 记录结果
ab_test.record_metric('lstm_vs_transformer', model_name, accuracy)

# 查看结果
results = ab_test.get_results('lstm_vs_transformer')
```

**验收标准**:
- [ ] A/B测试框架实现
- [ ] 流量分配功能
- [ ] 统计显著性检验
- [ ] 实验结果可视化

---

#### 1.4 模型监控和漂移检测 (2周)

**目标**: 监控模型性能衰减

**技术方案**:
```python
# ml/model_monitor.py

from evidently import ColumnMapping
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset, TargetDriftPreset

class ModelMonitor:
    """模型监控"""
    
    def __init__(self):
        self.reference_data = None
        self.current_data = []
    
    def set_reference(self, data: pd.DataFrame):
        """设置参考数据集（训练数据）"""
        self.reference_data = data
    
    def add_prediction(self, features: dict, prediction: float, actual: float = None):
        """添加预测记录"""
        record = features.copy()
        record['prediction'] = prediction
        if actual is not None:
            record['actual'] = actual
        self.current_data.append(record)
    
    def check_drift(self) -> dict:
        """检测数据漂移"""
        current_df = pd.DataFrame(self.current_data)
        
        # 使用Evidently检测漂移
        report = Report(metrics=[
            DataDriftPreset(),
            TargetDriftPreset()
        ])
        
        report.run(
            reference_data=self.reference_data,
            current_data=current_df
        )
        
        # 提取漂移信息
        drift_results = report.as_dict()
        
        return {
            'has_drift': drift_results['metrics'][0]['result']['dataset_drift'],
            'drifted_features': [
                f for f, v in drift_results['metrics'][0]['result']['drift_by_columns'].items()
                if v['drift_detected']
            ],
            'drift_score': drift_results['metrics'][0]['result']['share_of_drifted_columns']
        }
    
    def calculate_performance_metrics(self) -> dict:
        """计算性能指标"""
        df = pd.DataFrame(self.current_data)
        
        if 'actual' not in df.columns:
            return {'error': 'No actual values available'}
        
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        
        predictions = (df['prediction'] > 0.5).astype(int)
        actuals = df['actual'].astype(int)
        
        return {
            'accuracy': accuracy_score(actuals, predictions),
            'precision': precision_score(actuals, predictions),
            'recall': recall_score(actuals, predictions),
            'f1': f1_score(actuals, predictions)
        }

# 集成到服务
class ModelMonitorService:
    def __init__(self):
        self.monitor = ModelMonitor()
        self.alert_threshold = 0.3  # 30%特征漂移触发告警
    
    async def check_and_alert(self):
        """定期检查并告警"""
        drift_result = self.monitor.check_drift()
        
        if drift_result['drift_score'] > self.alert_threshold:
            # 发送告警
            await self.send_alert({
                'type': 'model_drift',
                'severity': 'high',
                'message': f"检测到{drift_result['drift_score']:.1%}的特征漂移",
                'drifted_features': drift_result['drifted_features']
            })
        
        # 记录到数据库
        await self.log_drift_metrics(drift_result)
```

**验收标准**:
- [ ] 数据漂移检测
- [ ] 性能监控
- [ ] 自动告警
- [ ] 监控Dashboard

---

#### 1.5 AutoML功能 (2周)

**目标**: 自动模型选择和调参

**技术方案**:
```python
# ml/automl.py

from autogluon.tabular import TabularPredictor
import optuna

class AutoMLPipeline:
    """AutoML Pipeline"""
    
    def auto_train(self, train_data: pd.DataFrame, target_col: str,
                   time_limit: int = 3600):
        """
        使用AutoGluon自动训练
        
        Args:
            train_data: 训练数据
            target_col: 目标列
            time_limit: 时间限制（秒）
        """
        predictor = TabularPredictor(
            label=target_col,
            eval_metric='accuracy',
            problem_type='binary'
        )
        
        predictor.fit(
            train_data=train_data,
            time_limit=time_limit,
            presets='best_quality'
        )
        
        # 获取排行榜
        leaderboard = predictor.leaderboard(train_data)
        
        return predictor, leaderboard
    
    def hyperparameter_tuning(self, model_class, train_data, val_data,
                             n_trials: int = 100):
        """
        使用Optuna进行超参数调优
        """
        def objective(trial):
            # 定义超参数搜索空间
            params = {
                'hidden_size': trial.suggest_int('hidden_size', 64, 256),
                'num_layers': trial.suggest_int('num_layers', 1, 4),
                'dropout': trial.suggest_float('dropout', 0.1, 0.5),
                'learning_rate': trial.suggest_loguniform('learning_rate', 1e-5, 1e-2)
            }
            
            # 训练模型
            model = model_class(**params)
            val_loss = train_and_evaluate(model, train_data, val_data)
            
            return val_loss
        
        # 创建研究
        study = optuna.create_study(direction='minimize')
        study.optimize(objective, n_trials=n_trials)
        
        return study.best_params, study.best_value

# 使用示例
automl = AutoMLPipeline()

# 方式1: AutoGluon自动训练
predictor, leaderboard = automl.auto_train(train_data, target_col='label')
print(leaderboard)

# 方式2: Optuna调参
best_params, best_score = automl.hyperparameter_tuning(
    LSTMPredictor, train_data, val_data, n_trials=50
)
```

**验收标准**:
- [ ] AutoGluon集成
- [ ] Optuna超参数优化
- [ ] 自动特征工程
- [ ] 模型集成(Ensemble)

---

### 2. 数据质量提升 (+1分)

#### 2.1 数据清洗Pipeline (2周)

**技术方案**:
```python
# data/cleaning_pipeline.py

from great_expectations.dataset import PandasDataset

class DataCleaningPipeline:
    """数据清洗Pipeline"""
    
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """执行清洗流程"""
        df = self._remove_duplicates(df)
        df = self._handle_missing_values(df)
        df = self._remove_outliers(df)
        df = self._validate_data(df)
        return df
    
    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """去重"""
        before = len(df)
        df = df.drop_duplicates(subset=['symbol', 'date'])
        after = len(df)
        logger.info(f"Removed {before - after} duplicates")
        return df
    
    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理缺失值"""
        # 价格字段：前向填充
        price_cols = ['open', 'high', 'low', 'close']
        df[price_cols] = df[price_cols].fillna(method='ffill')
        
        # 成交量：填充0
        df['volume'] = df['volume'].fillna(0)
        
        return df
    
    def _remove_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """移除异常值"""
        from pyod.models.iforest import IForest
        
        # 使用Isolation Forest检测异常
        clf = IForest(contamination=0.01)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        outlier_labels = clf.fit_predict(df[numeric_cols])
        
        # 移除异常值
        df = df[outlier_labels == 0]
        
        return df
    
    def _validate_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据验证"""
        ge_df = PandasDataset(df)
        
        # 定义期望
        ge_df.expect_column_values_to_be_between('close', min_value=0, max_value=10000)
        ge_df.expect_column_values_to_not_be_null('symbol')
        ge_df.expect_column_values_to_be_unique('symbol')
        
        # 验证
        validation_result = ge_df.validate()
        
        if not validation_result['success']:
            logger.warning(f"Data validation failed: {validation_result}")
        
        return df
```

**验收标准**:
- [ ] 去重功能
- [ ] 缺失值处理
- [ ] 异常值检测
- [ ] 数据验证

---

## 时间表

| 月份 | 任务 | 状态 |
|------|------|------|
| M1 | 深度学习模型 + MLflow | 🔲 |
| M2 | A/B测试 + 模型监控 | 🔲 |
| M3 | AutoML + 数据清洗 | 🔲 |
| M4 | 集成测试 + 优化 | 🔲 |

---

## 验收标准

- [ ] 3种深度学习模型上线
- [ ] MLflow实验管理可用
- [ ] A/B测试框架运行
- [ ] 模型漂移监控告警
- [ ] AutoML功能可用
- [ ] 数据清洗Pipeline运行

---

## 下一步

完成Phase 2后，进入[Phase 3: 全面完善](./phase3-full-coverage.md)
