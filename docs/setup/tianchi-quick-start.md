# 天池比赛快速启动指南

## 🚀 一键启动流程

### 第一步：进入 PAI-DSW 环境

1. 访问 https://pai.console.aliyun.com/
2. 创建 DSW 实例（推荐配置见 `pai-dsw-setup-guide.md`）
3. 启动实例并打开 Terminal

### 第二步：执行环境配置脚本

```bash
# 下载项目脚本
git clone <your-repo-url> ~/tianchi-competition
# 或手动创建目录
mkdir -p ~/tianchi-competition && cd ~/tianchi-competition

# 执行环境配置（会自动安装依赖）
bash scripts/tianchi/setup_environment.sh
```

### 第三步：下载数据集

**从天池比赛页面复制最新下载命令**（STS 凭证有效期 < 1小时）：

```bash
# 示例（需替换为实际凭证）
ossutil cp oss://tianchi-race-prod-sh/.../public_dataset_a.zip ./public_dataset_a.zip \
  -i <ACCESS_KEY_ID> \
  -k <ACCESS_KEY_SECRET> \
  --endpoint=oss-cn-shanghai-internal.aliyuncs.com \
  --sts-token=<STS_TOKEN>

# 解压数据
unzip public_dataset_a.zip
```

### 第四步：数据预处理

```bash
python scripts/tianchi/preprocess.py
```

**预处理功能：**
- ✅ 自动处理缺失值（中位数/均值填充）
- ✅ 类别特征编码（Label Encoding）
- ✅ 数值特征标准化（Standard/Robust Scaler）
- ✅ 创建 5 折交叉验证数据

**输出文件：**
```
processed_data/
├── train_full.csv         # 完整训练集（含 fold 标记）
├── test_processed.csv     # 测试集
├── fold0_train.csv        # 第 0 折训练集
├── fold0_val.csv          # 第 0 折验证集
├── fold1_train.csv
├── fold1_val.csv
└── ...
```

### 第五步：模型训练

```bash
python scripts/tianchi/train.py
```

**支持的模型：**
1. **LightGBM** — 快速、内存友好
2. **XGBoost** — 高精度、鲁棒性强
3. **CatBoost** — 自动处理类别特征

**训练特性：**
- ✅ 5 折交叉验证
- ✅ Early Stopping（防止过拟合）
- ✅ 自动模型融合（预测时平均 5 个模型）
- ✅ 自动生成提交文件

**输出文件：**
```
models/
├── lightgbm_fold0.txt
├── lightgbm_fold1.txt
├── lightgbm_cv_scores.csv  # 交叉验证得分
├── xgboost_fold0.json
├── catboost_fold0.cbm
└── ...

submissions/
├── lightgbm_submission.csv
├── xgboost_submission.csv
└── catboost_submission.csv
```

### 第六步：提交结果

1. 下载提交文件：`submissions/<model>_submission.csv`
2. 登录天池比赛页面
3. 上传 CSV 文件提交
4. 查看排行榜成绩

---

## 📊 数据探索（可选）

### 方法 1：Jupyter Notebook

```bash
jupyter notebook
# 打开 notebooks/01_eda.ipynb
```

### 方法 2：Python 脚本

```python
import pandas as pd

# 加载数据
train = pd.read_csv('./public_dataset_a/train/data.csv')
labels = pd.read_csv('./public_dataset_a/train/labels.csv')

# 基本统计
print(train.shape)
print(train.describe())
print(labels['label'].value_counts())

# 缺失值检查
print(train.isnull().sum().sort_values(ascending=False).head())
```

---

## 🛠️ 高级用法

### 自定义预处理参数

编辑 `scripts/tianchi/preprocess.py`：

```python
preprocessor = TianchiPreprocessor(
    data_dir='./public_dataset_a',
    output_dir='./processed_data'
)

# 修改处理策略
train_data = preprocessor.handle_missing_values(train_data, strategy='mean')  # 均值填充
train_data, test_data = preprocessor.normalize_features(train_data, test_data, method='robust')  # 鲁棒标准化
```

### 调整模型参数

编辑 `scripts/tianchi/train.py`：

```python
# LightGBM 参数
params = {
    'learning_rate': 0.01,      # 降低学习率
    'num_leaves': 63,           # 增加叶子数
    'max_depth': 8,             # 限制深度
    'feature_fraction': 0.7,    # 特征采样比例
    'bagging_fraction': 0.7,    # 数据采样比例
}
```

### 模型融合（Ensemble）

```python
import pandas as pd

# 加载三个模型的预测结果
lgb_pred = pd.read_csv('./submissions/lightgbm_submission.csv')
xgb_pred = pd.read_csv('./submissions/xgboost_submission.csv')
cat_pred = pd.read_csv('./submissions/catboost_submission.csv')

# 加权平均（可调整权重）
ensemble_pred = lgb_pred.copy()
ensemble_pred['label'] = (
    lgb_pred['label'] * 0.4 +
    xgb_pred['label'] * 0.3 +
    cat_pred['label'] * 0.3
).round().astype(int)

# 保存融合结果
ensemble_pred.to_csv('./submissions/ensemble_submission.csv', index=False)
```

---

## 🐛 常见问题

### Q1: STS 凭证过期
**错误**: `InvalidAccessKeyId` 或 `SecurityTokenExpired`
**解决**: 回到天池比赛页面重新复制最新的下载命令

### Q2: 内存不足
**错误**: `MemoryError` 或 `Killed`
**解决**:
- 升级 DSW 实例规格（增加内存）
- 使用分块读取：`pd.read_csv(..., chunksize=10000)`

### Q3: 训练速度慢
**优化方案**:
- 使用 GPU 实例（XGBoost/LightGBM 支持 GPU 加速）
- 减少特征数量（特征选择）
- 降低交叉验证折数（5 → 3）

### Q4: 模型过拟合
**表现**: 训练集准确率高，验证集准确率低
**解决**:
- 增加正则化（`lambda_l1`, `lambda_l2`）
- 降低模型复杂度（`max_depth`, `num_leaves`）
- 增加 Early Stopping 轮数

### Q5: 标签不平衡
**症状**: 某些类别预测准确率极低
**解决**:
```python
# 方法1：类别权重
params = {
    'scale_pos_weight': len(y_train[y_train==0]) / len(y_train[y_train==1])
}

# 方法2：SMOTE 过采样
from imblearn.over_sampling import SMOTE
smote = SMOTE(random_state=42)
X_train, y_train = smote.fit_resample(X_train, y_train)
```

---

## 📝 文件结构

```
~/tianchi-competition/
├── public_dataset_a/           # 原始数据（下载后）
│   ├── train/
│   │   ├── data.csv
│   │   └── labels.csv
│   ├── test/
│   │   └── data.csv
│   └── sample_submission.csv
│
├── processed_data/             # 预处理后的数据
│   ├── train_full.csv
│   ├── test_processed.csv
│   └── fold*_*.csv
│
├── models/                     # 训练好的模型
│   ├── lightgbm_fold*.txt
│   ├── xgboost_fold*.json
│   ├── catboost_fold*.cbm
│   └── *_cv_scores.csv
│
├── submissions/                # 提交文件
│   ├── lightgbm_submission.csv
│   ├── xgboost_submission.csv
│   └── catboost_submission.csv
│
├── scripts/tianchi/
│   ├── setup_environment.sh    # 环境配置脚本
│   ├── preprocess.py           # 数据预处理
│   └── train.py                # 模型训练
│
├── notebooks/
│   └── 01_eda.ipynb            # 数据探索
│
└── config.yaml                 # 配置文件
```

---

## 🎯 下一步优化方向

1. **特征工程**
   - 交叉特征（特征交互）
   - 多项式特征
   - 目标编码（Target Encoding）

2. **模型优化**
   - 超参数调优（Optuna/GridSearch）
   - Stacking/Blending 融合
   - 神经网络（TabNet、DeepFM）

3. **后处理**
   - 阈值调整（Threshold Tuning）
   - 规则修正（Rule-based Correction）

---

## 💡 提分技巧

1. **数据增强**：合成少数类样本（SMOTE、ADASYN）
2. **特征选择**：移除低重要性特征，减少噪声
3. **模型融合**：结合多个模型的预测（Voting/Averaging/Stacking）
4. **交叉验证**：确保本地 CV 分数与线上分数一致
5. **Pseudo Labeling**：使用测试集高置信度预测扩充训练集

---

## 🔗 相关文档

- [PAI-DSW 详细配置指南](./pai-dsw-setup-guide.md)
- [天池官方文档](https://tianchi.aliyun.com/course)
- [LightGBM 参数说明](https://lightgbm.readthedocs.io/)
- [XGBoost 参数说明](https://xgboost.readthedocs.io/)

---

**⚠️ 重要提醒：**
- 使用完 PAI-DSW 记得**停止实例**，避免产生费用
- STS 凭证有效期 < 1 小时，下载数据时注意时效性
- 提交前检查 CSV 格式是否符合 `sample_submission.csv`
