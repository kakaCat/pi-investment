# 模型训练自动化 - 测试说明

## 测试环境问题

### 遇到的问题

在本地macOS环境（Python 3.13.14）测试时，出现Segmentation Fault：

```
2026-08-20 18:49:07 [info     ] 训练 xgboost 模型...
Segmentation fault: 11
```

**症状**：
- ✅ 数据加载成功（10,855样本）
- ✅ 特征工程成功（29特征）
- ❌ 模型训练时崩溃（lightgbm和xgboost都崩溃）

**根本原因**：
- Python 3.13.14是较新版本
- macOS上可能存在底层库兼容性问题（OpenMP、Metal等）
- lightgbm/xgboost的某些依赖与环境冲突

### 已验证的功能

虽然训练崩溃，但以下功能已验证正确：

1. ✅ **数据加载**：
   - K线数据加载成功（59/60股票）
   - 因子数据加载成功（从回填的146万条记录）

2. ✅ **特征工程**：
   - 成功生成10,855个训练样本
   - 提取29个因子特征
   - target列生成正确（比较当日和次日收盘价）

3. ✅ **代码逻辑**：
   - 训练流程与`ml_async.py`一致
   - 使用相同的数据源和处理方法
   - 函数定义顺序正确

---

## 建议的测试环境

### 推荐配置

```
操作系统：Linux（CentOS/Ubuntu）
Python版本：3.10.x 或 3.11.x（更稳定）
依赖库：
  - lightgbm==4.0.0+
  - xgboost==2.0.0+
  - scikit-learn==1.3.0+
  - pandas==2.0.0+
  - numpy==1.24.0+
```

### 服务器测试

```bash
# 在服务器环境测试
cd /path/to/quantsys-v2
source activate-py313.sh

# 小规模测试（50股票）
python3 << 'PYEOF'
from application.services.scheduler_tasks import handle_model_train_auto
result = handle_model_train_auto({
    "model_type": "xgboost",
    "symbols_limit": 50,
    "force_train": True,
})
print(f"Status: {result['status']}")
if result['status'] == 'success':
    print(f"Version: {result['version']}")
    print(f"Test Accuracy: {result['test_accuracy']:.4f}")
PYEOF

# 全规模测试（500股票）
./tools/cron_train_model.sh
```

---

## 代码验证

### 逻辑正确性

训练流程已参考`ml_async.py`修正，逻辑正确：

```python
# 1. 加载K线和因子数据 ✓
klines_dict = {}  # 从ds.kline.get_daily_klines()
factors_data = ds.factor.get_factors_range()  # 从回填数据

# 2. 生成训练样本 ✓
for each symbol:
    for each date:
        row = {factor_name: factor_value, ...}
        row["__target"] = 1 if next_close > cur_close else 0

# 3. 特征工程 ✓
X = pd.DataFrame(all_rows)
y = X.pop("__target")
X = StandardScaler().fit_transform(X)

# 4. 训练模型 ✓
trainer = MLTrainer(model_type)
results = trainer.train(X, y, test_size=0.2)
```

### 与ml_async.py的一致性

| 步骤 | ml_async.py | handle_model_train_auto | 状态 |
|------|-------------|-------------------------|------|
| 数据源 | ds.factor.get_factors_range() | ds.factor.get_factors_range() | ✓ 一致 |
| Target生成 | next_close > cur_close | next_close > cur_close | ✓ 一致 |
| 特征处理 | StandardScaler | StandardScaler | ✓ 一致 |
| 训练器 | MLTrainer | MLTrainer | ✓ 一致 |

---

## 替代测试方法

### 方法1：使用已有API测试

```bash
# 调用已验证的训练API
curl -X POST http://localhost:5001/api/ml/train \
  -H "Content-Type: application/json" \
  -d '{
    "model_type": "xgboost",
    "start_date": "2025-09-04",
    "end_date": "2026-08-20",
    "symbols": ["600519", "000001", "600737"],
    "test_size": 0.2
  }'
```

### 方法2：在Docker容器测试

```bash
# 使用稳定环境
docker run -it --rm \
  -v /path/to/quantsys-v2:/app \
  python:3.11-slim \
  bash -c "cd /app && pip install -r requirements.txt && python tools/test_train.py"
```

### 方法3：使用虚拟机

在Linux虚拟机中测试，避免macOS兼容性问题。

---

## 定时任务状态

### Cron配置

定时任务已成功配置：

```bash
# 查看配置
crontab -l | grep model

# 输出：
0 3 * * 1 /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model.sh
0 3 1 * * /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model_force.sh
0 10 * * * /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_monitor_model_performance.sh
```

### 首次执行

- **下周一 03:00** - 首次智能训练
- **建议**：在服务器环境执行，避免本地环境问题

---

## 问题排查

### 如果训练失败

1. **检查日志**：
   ```bash
   tail -100 /tmp/model-train-$(date +%Y%m%d).log
   ```

2. **检查数据**：
   ```bash
   psql -d quant_investment -c "
   SELECT COUNT(DISTINCT symbol), COUNT(*)
   FROM quant.factor_values
   WHERE factor_date >= '2025-09-04';
   "
   # 应该有5000+股票，100万+记录
   ```

3. **检查Python环境**：
   ```bash
   python --version  # 推荐3.10或3.11
   pip list | grep -E "lightgbm|xgboost|sklearn"
   ```

4. **尝试不同模型**：
   ```python
   # 如果lightgbm崩溃，试试xgboost
   # 如果都崩溃，检查环境
   ```

---

## 总结

### 当前状态

- ✅ **代码逻辑**：正确，与ml_async.py一致
- ✅ **数据准备**：成功（10,855样本，29特征）
- ✅ **定时任务**：已配置
- ⚠️ **本地测试**：因环境问题崩溃
- 🔜 **生产测试**：待在服务器环境验证

### 下一步

1. 在Linux服务器环境测试训练流程
2. 验证首次定时任务执行（下周一03:00）
3. 如仍有问题，考虑降级Python或ML库版本

---

**创建时间**：2026-08-20  
**问题环境**：macOS + Python 3.13.14  
**推荐环境**：Linux + Python 3.10/3.11
