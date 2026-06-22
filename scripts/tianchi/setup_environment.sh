#!/bin/bash
# PAI-DSW 环境快速配置脚本

set -e

echo "=== PAI-DSW 环境配置 ==="

# 1. 创建工作目录
echo "[1/6] 创建工作目录..."
mkdir -p ~/tianchi-competition/{scripts,notebooks,processed_data,models,submissions}
cd ~/tianchi-competition

# 2. 检查预装工具
echo "[2/6] 检查环境..."
python --version
pip --version
ossutil --version 2>/dev/null || echo "⚠️  ossutil 未安装，需手动安装"

# 3. 安装依赖
echo "[3/6] 安装 Python 依赖..."
pip install --upgrade pip -q
pip install pandas numpy scikit-learn matplotlib seaborn -q
pip install lightgbm xgboost catboost -q
pip install tqdm joblib -q

echo "✅ 基础库安装完成"

# 4. 下载数据集提示
echo "[4/6] 准备下载数据集..."
echo ""
echo "⚠️  请从天池比赛页面复制最新的 ossutil 下载命令"
echo "   示例："
echo "   ossutil cp oss://tianchi-race-prod-sh/... ./public_dataset_a.zip \\"
echo "     -i <YOUR_KEY> -k <YOUR_SECRET> \\"
echo "     --endpoint=oss-cn-shanghai-internal.aliyuncs.com \\"
echo "     --sts-token=<YOUR_TOKEN>"
echo ""
read -p "已准备好下载命令？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "请粘贴完整的 ossutil 命令："
    read -r OSSUTIL_CMD
    eval "$OSSUTIL_CMD"

    # 解压数据集
    if [ -f "public_dataset_a.zip" ]; then
        echo "[5/6] 解压数据集..."
        unzip -q public_dataset_a.zip
        echo "✅ 数据集解压完成"

        # 显示数据结构
        echo "[6/6] 数据集结构："
        ls -lh public_dataset_a/
    else
        echo "❌ 下载失败，请检查命令"
        exit 1
    fi
else
    echo "⏭️  跳过数据下载，稍后手动执行"
fi

# 7. 创建配置文件
cat > config.yaml <<EOF
# 天池比赛配置
project_name: tianchi-competition
data_dir: ./public_dataset_a
processed_dir: ./processed_data
models_dir: ./models
submissions_dir: ./submissions

# 数据处理参数
train_test_split: 0.8
random_seed: 42
n_folds: 5

# 特征工程
feature_engineering:
  handle_missing: median
  scaling: standard
  encoding: label

# 模型参数
models:
  lightgbm:
    learning_rate: 0.05
    num_leaves: 31
    max_depth: -1
    n_estimators: 1000
    early_stopping_rounds: 50

  xgboost:
    learning_rate: 0.05
    max_depth: 6
    n_estimators: 1000
    early_stopping_rounds: 50
EOF

echo ""
echo "✅ 环境配置完成！"
echo ""
echo "下一步："
echo "  1. 运行数据探索：jupyter notebook notebooks/01_eda.ipynb"
echo "  2. 运行数据预处理：python scripts/preprocess.py"
echo "  3. 开始模型训练"
echo ""
echo "配置文件：config.yaml"
echo "工作目录：$(pwd)"
