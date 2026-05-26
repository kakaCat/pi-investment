# P1 Implementation Plan: 深度学习模型训练 API

> **前置条件**: P0 已完成（时间序列、因子模型、投资组合优化）
> **目标**: 实现 LSTM/Transformer 完整训练 pipeline，使 AI Agent 可以训练和管理深度学习模型
> **计划日期**: 2026-05-26
> **预估工时**: 8-12 小时

---

## 背景

### 现状

| 组件 | 状态 | 说明 |
|------|------|------|
| LSTM 推理模块 | ✅ 已实现 | `quantlib/ml/lstm_predictor.py` - 只支持预测 |
| Transformer 推理模块 | ✅ 已实现 | `quantlib/ml/transformer_predictor.py` - 只支持预测 |
| 训练 API | ❌ 未实现 | 当前只支持 XGBoost/LightGBM |
| 模型管理 | ⚠️ 部分实现 | 缺少 DL 模型的保存/加载机制 |

### 问题

1. **推理与训练分离**: 现有 LSTM/Transformer 类只有 `predict()` 方法，没有 `train()` 或 `fit()` 方法
2. **训练 pipeline 缺失**: 没有数据准备、训练循环、验证、早停等完整流程
3. **模型持久化**: 缺少 PyTorch 模型的保存/加载机制
4. **异步支持**: 深度学习训练耗时长，需要后台任务支持

---

## 实现方案

### 架构设计

```
AI Agent
  ↓ (调用 model_train 工具)
TypeScript model_train tool
  ↓ (HTTP POST)
quantsys-v2 /api/training/start
  ↓ (model_type="lstm" or "transformer")
services/ml_pipeline/dl_trainer.py (新建)
  ↓
quantlib/ml/lstm_predictor.py (扩展)
quantlib/ml/transformer_predictor.py (扩展)
  ↓ (保存模型)
models/{model_id}.pth
```

### 核心组件

#### 1. DL 训练器 (`services/ml_pipeline/dl_trainer.py`)

**职责**:
- 数据准备（序列化、归一化、train/val split）
- 训练循环（epoch、batch、梯度更新）
- 验证和早停
- 模型保存和元数据记录

**接口**:
```python
class DLModelTrainer:
    def __init__(self, model_type: str, hyperparams: Dict):
        """初始化训练器"""
        
    def prepare_data(self, features: pd.DataFrame, target_col: str) -> Tuple:
        """准备训练数据（序列化、归一化）"""
        
    def train(self, X_train, y_train, X_val, y_val) -> Dict:
        """训练模型并返回训练报告"""
        
    def save_model(self, model, model_id: str, metadata: Dict):
        """保存模型和元数据"""
```

#### 2. 扩展 LSTM/Transformer 预测器

**新增方法**:
```python
class LSTMPredictor:
    # 现有方法
    def predict(self, features): ...
    def prepare_sequences(self, data, target_col): ...
    
    # 新增方法
    def fit(self, X_train, y_train, X_val=None, y_val=None, 
            epochs=100, batch_size=32, learning_rate=0.001,
            early_stopping_patience=10) -> Dict:
        """训练 LSTM 模型"""
        
    def save(self, filepath: str):
        """保存模型权重"""
        
    def load(self, filepath: str):
        """加载模型权重"""
```

#### 3. 训练 API 端点扩展

**修改**: `quantsys-v2/api/routes/training.py`

```python
@training_bp.route('/api/training/start', methods=['POST'])
@handle_api_error
def training_start():
    data = request.get_json()
    model_type = data.get('model_type', 'xgboost')
    
    if model_type in ('lstm', 'transformer'):
        # 深度学习训练路径
        from services.ml_pipeline.dl_trainer import DLModelTrainer
        
        trainer = DLModelTrainer(
            model_type=model_type,
            hyperparams=data.get('hyperparams', {})
        )
        
        # 准备数据
        X_train, y_train, X_val, y_val = trainer.prepare_data(
            features_df, 
            target_col=data.get('target_col', 'roc_5')
        )
        
        # 训练
        training_results = trainer.train(X_train, y_train, X_val, y_val)
        
        # 保存模型
        model_id = f"{model_type}_{int(time.time())}"
        trainer.save_model(training_results['model'], model_id, training_results['metadata'])
        
        return api_response({
            'model_id': model_id,
            'model_type': model_type,
            'metrics': training_results['metrics'],
            'training_history': training_results['history']
        })
    else:
        # 现有 XGBoost/LightGBM 路径
        ...
```

#### 4. TypeScript 工具扩展

**修改**: `src/infrastructure/tools/model/train-tool.ts`

```typescript
interface TrainModelParams {
  model_type?: "xgboost" | "lightgbm" | "lstm" | "transformer";
  days?: number;
  future_days?: number;
  return_threshold?: number;
  symbols?: string[];
  cv_splits?: number;
  
  // 深度学习超参数
  hyperparams?: {
    // LSTM 参数
    hidden_size?: number;        // 隐藏层维度 (默认 64)
    num_layers?: number;         // LSTM 层数 (默认 2)
    dropout?: number;            // Dropout 比例 (默认 0.2)
    sequence_length?: number;    // 序列长度 (默认 20)
    
    // Transformer 参数
    d_model?: number;            // 模型维度 (默认 128)
    nhead?: number;              // 注意力头数 (默认 8)
    dim_feedforward?: number;    // 前馈网络维度 (默认 512)
    
    // 训练参数
    epochs?: number;             // 训练轮数 (默认 100)
    batch_size?: number;         // 批次大小 (默认 32)
    learning_rate?: number;      // 学习率 (默认 0.001)
    early_stopping_patience?: number;  // 早停耐心值 (默认 10)
    val_split?: number;          // 验证集比例 (默认 0.2)
  };
}
```

---

## 实现步骤

### Phase 1: 核心训练功能 (4-5h)

#### Step 1.1: 创建 DL 训练器基础类

**文件**: `quantsys-v2/services/ml_pipeline/dl_trainer.py`

```python
"""
Deep Learning Model Trainer
支持 LSTM 和 Transformer 模型的训练
"""
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from typing import Dict, Tuple, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DLModelTrainer:
    """深度学习模型训练器"""
    
    def __init__(self, model_type: str = 'lstm', hyperparams: Optional[Dict] = None):
        self.model_type = model_type
        self.hyperparams = hyperparams or {}
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Using device: {self.device}")
        
    def prepare_data(self, 
                     features: pd.DataFrame, 
                     target_col: str,
                     sequence_length: int = 20,
                     val_split: float = 0.2) -> Tuple:
        """
        准备训练数据
        
        Returns:
            (X_train, y_train, X_val, y_val, scaler)
        """
        from sklearn.preprocessing import StandardScaler
        
        # 归一化特征
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features.drop(columns=[target_col]))
        target = features[target_col].values
        
        # 创建序列
        X, y = [], []
        for i in range(len(features_scaled) - sequence_length):
            X.append(features_scaled[i:i+sequence_length])
            y.append(target[i+sequence_length])
        
        X = np.array(X)
        y = np.array(y)
        
        # 划分训练集和验证集
        split_idx = int(len(X) * (1 - val_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        logger.info(f"Training samples: {len(X_train)}, Validation samples: {len(X_val)}")
        
        return X_train, y_train, X_val, y_val, scaler
    
    def train(self, 
              X_train: np.ndarray, 
              y_train: np.ndarray,
              X_val: Optional[np.ndarray] = None,
              y_val: Optional[np.ndarray] = None) -> Dict:
        """
        训练模型
        
        Returns:
            {
                'model': trained_model,
                'metrics': {...},
                'history': {...},
                'metadata': {...}
            }
        """
        # 超参数
        epochs = self.hyperparams.get('epochs', 100)
        batch_size = self.hyperparams.get('batch_size', 32)
        learning_rate = self.hyperparams.get('learning_rate', 0.001)
        early_stopping_patience = self.hyperparams.get('early_stopping_patience', 10)
        
        # 创建模型
        if self.model_type == 'lstm':
            from quantlib.ml import LSTMPredictor
            model = LSTMPredictor(
                input_size=X_train.shape[2],
                hidden_size=self.hyperparams.get('hidden_size', 64),
                num_layers=self.hyperparams.get('num_layers', 2),
                dropout=self.hyperparams.get('dropout', 0.2),
                sequence_length=X_train.shape[1]
            )
        elif self.model_type == 'transformer':
            from quantlib.ml import TransformerPredictor
            model = TransformerPredictor(
                input_size=X_train.shape[2],
                d_model=self.hyperparams.get('d_model', 128),
                nhead=self.hyperparams.get('nhead', 8),
                num_layers=self.hyperparams.get('num_layers', 3),
                sequence_length=X_train.shape[1]
            )
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")
        
        # 转换为 PyTorch tensors
        X_train_tensor = torch.FloatTensor(X_train).to(self.device)
        y_train_tensor = torch.FloatTensor(y_train).to(self.device)
        
        train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        
        if X_val is not None:
            X_val_tensor = torch.FloatTensor(X_val).to(self.device)
            y_val_tensor = torch.FloatTensor(y_val).to(self.device)
            val_dataset = TensorDataset(X_val_tensor, y_val_tensor)
            val_loader = DataLoader(val_dataset, batch_size=batch_size)
        
        # 训练循环
        criterion = nn.MSELoss()
        optimizer = optim.Adam(model.parameters(), lr=learning_rate)
        
        history = {'train_loss': [], 'val_loss': []}
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(epochs):
            # 训练阶段
            model.train()
            train_loss = 0.0
            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs.squeeze(), batch_y)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()
            
            train_loss /= len(train_loader)
            history['train_loss'].append(train_loss)
            
            # 验证阶段
            if X_val is not None:
                model.eval()
                val_loss = 0.0
                with torch.no_grad():
                    for batch_X, batch_y in val_loader:
                        outputs = model(batch_X)
                        loss = criterion(outputs.squeeze(), batch_y)
                        val_loss += loss.item()
                
                val_loss /= len(val_loader)
                history['val_loss'].append(val_loss)
                
                # 早停检查
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                else:
                    patience_counter += 1
                
                if patience_counter >= early_stopping_patience:
                    logger.info(f"Early stopping at epoch {epoch+1}")
                    break
                
                if (epoch + 1) % 10 == 0:
                    logger.info(f"Epoch {epoch+1}/{epochs} - Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}")
            else:
                if (epoch + 1) % 10 == 0:
                    logger.info(f"Epoch {epoch+1}/{epochs} - Train Loss: {train_loss:.4f}")
        
        # 计算最终指标
        metrics = {
            'final_train_loss': history['train_loss'][-1],
            'final_val_loss': history['val_loss'][-1] if X_val is not None else None,
            'best_val_loss': best_val_loss if X_val is not None else None,
            'epochs_trained': len(history['train_loss'])
        }
        
        metadata = {
            'model_type': self.model_type,
            'hyperparams': self.hyperparams,
            'input_shape': X_train.shape,
            'device': str(self.device)
        }
        
        return {
            'model': model,
            'metrics': metrics,
            'history': history,
            'metadata': metadata
        }
    
    def save_model(self, model, model_id: str, metadata: Dict):
        """保存模型和元数据"""
        models_dir = Path('models')
        models_dir.mkdir(exist_ok=True)
        
        model_path = models_dir / f"{model_id}.pth"
        metadata_path = models_dir / f"{model_id}_metadata.json"
        
        # 保存模型权重
        torch.save(model.state_dict(), model_path)
        
        # 保存元数据
        import json
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Model saved to {model_path}")
```

#### Step 1.2: 扩展 LSTM 预测器

**修改**: `quantsys-v2/quantlib/ml/lstm_predictor.py`

在类中添加 `fit()`, `save()`, `load()` 方法（参考上面的训练器实现）。

#### Step 1.3: 扩展训练 API 端点

**修改**: `quantsys-v2/api/routes/training.py`

添加深度学习训练分支（参考上面的 API 端点设计）。

### Phase 2: 工具集成和测试 (2-3h)

#### Step 2.1: 更新 TypeScript 工具

**修改**: `src/infrastructure/tools/model/train-tool.ts`

添加 LSTM/Transformer 参数定义。

#### Step 2.2: 端到端测试

```bash
# 测试 LSTM 训练
curl -X POST http://127.0.0.1:5001/api/training/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_type": "lstm",
    "symbols": ["600519"],
    "days": 365,
    "hyperparams": {
      "hidden_size": 64,
      "num_layers": 2,
      "epochs": 50,
      "batch_size": 32
    }
  }'
```

### Phase 3: 模型管理和预测集成 (2-3h)

#### Step 3.1: 模型加载功能

**修改**: `src/infrastructure/tools/model/predict-tool.ts`

支持加载 LSTM/Transformer 模型进行预测。

#### Step 3.2: 模型列表和元数据查询

**新增**: `quantsys-v2/api/routes/models.py`

```python
@models_bp.route('/api/models/list', methods=['GET'])
def list_models():
    """列出所有已训练的模型"""
    
@models_bp.route('/api/models/<model_id>/metadata', methods=['GET'])
def get_model_metadata(model_id):
    """获取模型元数据"""
```

---

## 验收标准

- [ ] `model_train(model_type="lstm")` 成功训练并返回训练报告
- [ ] `model_train(model_type="transformer")` 成功训练并返回训练报告
- [ ] 训练报告包含：metrics, training_history, model_id
- [ ] 模型成功保存到 `models/` 目录
- [ ] `model_predict` 可以加载 DL 模型进行预测
- [ ] PyTorch 不可用时返回明确错误信息
- [ ] 支持 GPU 加速（如果可用）
- [ ] 早停机制正常工作
- [ ] 训练过程有日志输出

---

## 技术考虑

### PyTorch 依赖

```bash
# CPU 版本
pip install torch torchvision torchaudio

# GPU 版本 (CUDA 11.8)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 性能优化

1. **批处理**: 使用 DataLoader 进行批量训练
2. **GPU 加速**: 自动检测并使用 CUDA
3. **早停**: 避免过拟合和浪费计算资源
4. **异步训练**: 考虑使用后台任务（Celery/RQ）

### 数据要求

- **最小样本数**: 建议 >= 1000 个序列
- **序列长度**: 默认 20，可调整
- **特征数量**: 建议 5-50 个特征
- **训练时间**: LSTM 约 1-5 分钟（CPU），Transformer 约 5-15 分钟

---

## 后续优化

1. **超参数调优**: 集成 Optuna 进行自动调参
2. **模型集成**: 支持多模型 ensemble
3. **在线学习**: 支持增量训练
4. **模型版本管理**: MLflow 集成
5. **分布式训练**: 多 GPU 支持

---

## 参考资料

- PyTorch 官方文档: https://pytorch.org/docs/stable/index.html
- LSTM 论文: https://www.bioinf.jku.at/publications/older/2604.pdf
- Transformer 论文: https://arxiv.org/abs/1706.03762
- 时间序列预测最佳实践: https://otexts.com/fpp3/
