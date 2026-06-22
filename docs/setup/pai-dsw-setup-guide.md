# PAI-DSW 环境配置指南

## 一、创建 DSW 实例

### 1.1 访问控制台
```
https://pai.console.aliyun.com/
→ 交互式建模（DSW）
→ 创建实例
```

### 1.2 实例配置推荐

**基础配置：**
- **实例规格**：`ecs.gn6i-c4g1.xlarge`（1×T4 GPU，适合训练）或 `ecs.c6.xlarge`（仅 CPU，适合数据处理）
- **镜像**：`Python 3.8 + PyTorch 1.12`（推荐）或 `Python 3.9 + TensorFlow 2.x`
- **存储**：100GB+（根据数据集大小调整）
- **网络**：专有网络 VPC（默认）

**费用优化：**
- 免费试用：新用户有 40 小时免费额度
- 按量付费：停止实例时不计费（仅存储费用）
- 使用完记得停止实例

### 1.3 启动实例
创建后等待 2-3 分钟，状态变为"运行中"，点击"打开"进入 JupyterLab 界面。

## 二、环境初始化

### 2.1 打开 Terminal
JupyterLab 界面 → Launcher → Terminal

### 2.2 检查预装工具
```bash
# 检查 Python 版本
python --version

# 检查 ossutil（PAI-DSW 预装）
ossutil --version

# 检查常用库
pip list | grep -E "pandas|numpy|sklearn|torch"
```

### 2.3 创建工作目录
```bash
mkdir -p ~/tianchi-competition
cd ~/tianchi-competition
```

## 三、下载天池数据集

### 3.1 执行下载命令

**注意：** 从天池比赛页面复制最新的内网下载命令（STS 凭证有效期 < 1 小时）

```bash
# 示例命令（需要替换为最新凭证）
ossutil cp oss://tianchi-race-prod-sh/file/race/documents/prod/532486/1796/public/public_dataset_a.zip \
  ./public_dataset_a.zip \
  -i <YOUR_ACCESS_KEY_ID> \
  -k <YOUR_ACCESS_KEY_SECRET> \
  --endpoint=oss-cn-shanghai-internal.aliyuncs.com \
  --sts-token=<YOUR_STS_TOKEN>
```

### 3.2 解压数据集
```bash
# 解压
unzip public_dataset_a.zip

# 查看结构
tree -L 2 -h  # 或 ls -lhR
```

### 3.3 预期数据结构
```
public_dataset_a/
├── train/
│   ├── data.csv          # 训练数据
│   └── labels.csv        # 训练标签
├── test/
│   └── data.csv          # 测试数据
└── sample_submission.csv # 提交样例
```

## 四、数据预处理环境

### 4.1 安装额外依赖（如需要）
```bash
# 安装常用数据科学库
pip install pandas numpy scikit-learn matplotlib seaborn -U

# 安装深度学习库（根据任务选择）
pip install torch torchvision  # PyTorch
# 或
pip install tensorflow         # TensorFlow

# 安装时间序列/金融库（如适用）
pip install ta-lib statsmodels arch
```

### 4.2 创建数据处理脚本模板
```bash
# 创建脚本目录
mkdir -p scripts notebooks
```

## 五、数据探索（EDA）模板

创建 Jupyter Notebook：`notebooks/01_eda.ipynb`

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 设置中文字体（避免乱码）
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 1. 加载数据
train_data = pd.read_csv('../public_dataset_a/train/data.csv')
train_labels = pd.read_csv('../public_dataset_a/train/labels.csv')
test_data = pd.read_csv('../public_dataset_a/test/data.csv')

# 2. 数据概览
print("训练集形状:", train_data.shape)
print("测试集形状:", test_data.shape)
print("\n特征列:")
print(train_data.columns.tolist())

# 3. 缺失值检查
print("\n缺失值统计:")
print(train_data.isnull().sum())

# 4. 数据类型
print("\n数据类型:")
print(train_data.dtypes)

# 5. 统计描述
print("\n数值特征统计:")
print(train_data.describe())

# 6. 标签分布
print("\n标签分布:")
print(train_labels['label'].value_counts())

# 7. 可视化
fig, axes = plt.subplots(2, 2, figsize=(15, 10))

# 标签分布
axes[0, 0].bar(train_labels['label'].value_counts().index, 
               train_labels['label'].value_counts().values)
axes[0, 0].set_title('标签分布')

# 特征相关性热力图（选取前 20 个数值特征）
numeric_cols = train_data.select_dtypes(include=[np.number]).columns[:20]
sns.heatmap(train_data[numeric_cols].corr(), ax=axes[0, 1], cmap='coolwarm')
axes[0, 1].set_title('特征相关性')

plt.tight_layout()
plt.savefig('../eda_report.png')
plt.show()
```

## 六、预处理脚本模板

创建 `scripts/preprocess.py`：

```python
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split

def load_data(data_dir='../public_dataset_a'):
    """加载原始数据"""
    train_data = pd.read_csv(f'{data_dir}/train/data.csv')
    train_labels = pd.read_csv(f'{data_dir}/train/labels.csv')
    test_data = pd.read_csv(f'{data_dir}/test/data.csv')
    return train_data, train_labels, test_data

def handle_missing_values(df):
    """处理缺失值"""
    # 数值特征：中位数填充
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
    
    # 类别特征：众数填充
    categorical_cols = df.select_dtypes(include=['object']).columns
    for col in categorical_cols:
        df[col] = df[col].fillna(df[col].mode()[0])
    
    return df

def encode_features(train_df, test_df):
    """特征编码"""
    # 类别特征 Label Encoding
    categorical_cols = train_df.select_dtypes(include=['object']).columns
    
    encoders = {}
    for col in categorical_cols:
        le = LabelEncoder()
        # 合并训练集和测试集的类别
        all_values = pd.concat([train_df[col], test_df[col]]).unique()
        le.fit(all_values)
        
        train_df[col] = le.transform(train_df[col])
        test_df[col] = le.transform(test_df[col])
        encoders[col] = le
    
    return train_df, test_df, encoders

def normalize_features(train_df, test_df):
    """特征标准化"""
    numeric_cols = train_df.select_dtypes(include=[np.number]).columns
    
    scaler = StandardScaler()
    train_df[numeric_cols] = scaler.fit_transform(train_df[numeric_cols])
    test_df[numeric_cols] = scaler.transform(test_df[numeric_cols])
    
    return train_df, test_df, scaler

def preprocess_pipeline(data_dir='../public_dataset_a', output_dir='../processed_data'):
    """完整预处理流水线"""
    # 1. 加载数据
    print("加载数据...")
    train_data, train_labels, test_data = load_data(data_dir)
    
    # 2. 处理缺失值
    print("处理缺失值...")
    train_data = handle_missing_values(train_data)
    test_data = handle_missing_values(test_data)
    
    # 3. 特征编码
    print("特征编码...")
    train_data, test_data, encoders = encode_features(train_data, test_data)
    
    # 4. 特征标准化
    print("特征标准化...")
    train_data, test_data, scaler = normalize_features(train_data, test_data)
    
    # 5. 合并标签
    train_full = train_data.merge(train_labels, on='id', how='left')
    
    # 6. 划分训练集和验证集
    print("划分数据集...")
    train_set, val_set = train_test_split(
        train_full, test_size=0.2, random_state=42, stratify=train_full['label']
    )
    
    # 7. 保存处理后的数据
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    train_set.to_csv(f'{output_dir}/train_processed.csv', index=False)
    val_set.to_csv(f'{output_dir}/val_processed.csv', index=False)
    test_data.to_csv(f'{output_dir}/test_processed.csv', index=False)
    
    print(f"预处理完成！数据已保存到 {output_dir}/")
    print(f"训练集: {train_set.shape}, 验证集: {val_set.shape}, 测试集: {test_data.shape}")
    
    return train_set, val_set, test_data

if __name__ == '__main__':
    preprocess_pipeline()
```

## 七、执行预处理

```bash
# 运行预处理脚本
cd ~/tianchi-competition/scripts
python preprocess.py
```

## 八、常见问题

### 8.1 STS 凭证过期
**错误**：`InvalidAccessKeyId` 或 `SecurityTokenExpired`
**解决**：回到天池比赛页面重新复制最新的下载命令

### 8.2 内存不足
**错误**：`MemoryError` 或 `Killed`
**解决**：
- 升级实例规格（增加内存）
- 分块读取数据：`pd.read_csv(..., chunksize=10000)`

### 8.3 磁盘空间不足
**解决**：
- 删除不需要的文件：`rm -rf ~/.cache/pip`
- 扩容存储（控制台操作）

### 8.4 中文乱码
**解决**：
```python
# 方法1：指定编码
df = pd.read_csv('data.csv', encoding='utf-8')

# 方法2：自动检测编码
import chardet
with open('data.csv', 'rb') as f:
    result = chardet.detect(f.read(100000))
df = pd.read_csv('data.csv', encoding=result['encoding'])
```

## 九、下一步

1. **数据探索**：运行 `notebooks/01_eda.ipynb`
2. **特征工程**：创建新特征、特征选择
3. **模型训练**：选择合适的算法（LightGBM、XGBoost、深度学习）
4. **模型评估**：交叉验证、调参
5. **生成提交文件**：按 `sample_submission.csv` 格式输出

## 十、资源清理

**⚠️ 重要：** 使用完毕后停止实例，避免产生不必要的费用

```
PAI 控制台 → DSW 实例列表 → 停止实例
```

保留的数据会存储在实例的持久化存储中，下次启动时可继续使用。
