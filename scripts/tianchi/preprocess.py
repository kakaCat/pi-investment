"""
天池比赛数据预处理脚本
支持：缺失值处理、特征编码、标准化、数据集划分
"""

import os
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder, RobustScaler
from sklearn.model_selection import train_test_split, StratifiedKFold
import warnings
warnings.filterwarnings('ignore')

class TianchiPreprocessor:
    """天池数据预处理器"""

    def __init__(self, data_dir='./public_dataset_a', output_dir='./processed_data'):
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.encoders = {}
        self.scaler = None

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

    def load_data(self):
        """加载原始数据"""
        print("=" * 60)
        print("加载数据集...")

        train_data = pd.read_csv(f'{self.data_dir}/train/data.csv')
        train_labels = pd.read_csv(f'{self.data_dir}/train/labels.csv')
        test_data = pd.read_csv(f'{self.data_dir}/test/data.csv')

        print(f"训练数据: {train_data.shape}")
        print(f"训练标签: {train_labels.shape}")
        print(f"测试数据: {test_data.shape}")

        return train_data, train_labels, test_data

    def explore_data(self, train_data, train_labels):
        """数据探索"""
        print("\n" + "=" * 60)
        print("数据探索...")

        # 特征列
        print(f"\n特征数量: {len(train_data.columns)}")
        print(f"特征列: {train_data.columns.tolist()[:10]}...")

        # 数据类型
        numeric_cols = train_data.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = train_data.select_dtypes(include=['object']).columns.tolist()
        print(f"\n数值特征: {len(numeric_cols)}")
        print(f"类别特征: {len(categorical_cols)}")

        # 缺失值统计
        missing = train_data.isnull().sum()
        if missing.sum() > 0:
            print("\n缺失值统计:")
            print(missing[missing > 0].sort_values(ascending=False).head(10))
        else:
            print("\n✅ 无缺失值")

        # 标签分布
        print("\n标签分布:")
        print(train_labels['label'].value_counts().sort_index())

        return numeric_cols, categorical_cols

    def handle_missing_values(self, df, strategy='median'):
        """处理缺失值"""
        print("\n" + "=" * 60)
        print(f"处理缺失值 (策略: {strategy})...")

        missing_before = df.isnull().sum().sum()

        # 数值特征
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if strategy == 'median':
            df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
        elif strategy == 'mean':
            df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].mean())
        else:
            df[numeric_cols] = df[numeric_cols].fillna(0)

        # 类别特征
        categorical_cols = df.select_dtypes(include=['object']).columns
        for col in categorical_cols:
            if df[col].isnull().sum() > 0:
                df[col] = df[col].fillna(df[col].mode()[0] if len(df[col].mode()) > 0 else 'unknown')

        missing_after = df.isnull().sum().sum()
        print(f"处理前缺失值: {missing_before}, 处理后: {missing_after}")

        return df

    def encode_features(self, train_df, test_df):
        """特征编码"""
        print("\n" + "=" * 60)
        print("特征编码...")

        categorical_cols = train_df.select_dtypes(include=['object']).columns

        if len(categorical_cols) == 0:
            print("无类别特征需要编码")
            return train_df, test_df

        print(f"编码 {len(categorical_cols)} 个类别特征")

        for col in categorical_cols:
            le = LabelEncoder()

            # 合并训练集和测试集的类别
            all_values = pd.concat([train_df[col], test_df[col]]).unique()
            le.fit(all_values)

            train_df[col] = le.transform(train_df[col])
            test_df[col] = le.transform(test_df[col])

            self.encoders[col] = le
            print(f"  {col}: {len(all_values)} 个唯一值")

        return train_df, test_df

    def normalize_features(self, train_df, test_df, method='standard'):
        """特征标准化"""
        print("\n" + "=" * 60)
        print(f"特征标准化 (方法: {method})...")

        numeric_cols = train_df.select_dtypes(include=[np.number]).columns

        if method == 'standard':
            self.scaler = StandardScaler()
        elif method == 'robust':
            self.scaler = RobustScaler()
        else:
            print("跳过标准化")
            return train_df, test_df

        train_df[numeric_cols] = self.scaler.fit_transform(train_df[numeric_cols])
        test_df[numeric_cols] = self.scaler.transform(test_df[numeric_cols])

        print(f"标准化 {len(numeric_cols)} 个数值特征")

        return train_df, test_df

    def create_folds(self, train_full, n_folds=5):
        """创建交叉验证折"""
        print("\n" + "=" * 60)
        print(f"创建 {n_folds} 折交叉验证...")

        train_full['fold'] = -1

        skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)

        for fold, (train_idx, val_idx) in enumerate(skf.split(train_full, train_full['label'])):
            train_full.loc[val_idx, 'fold'] = fold

        print(f"折分布:")
        print(train_full['fold'].value_counts().sort_index())

        return train_full

    def save_data(self, train_full, test_data):
        """保存处理后的数据"""
        print("\n" + "=" * 60)
        print("保存数据...")

        # 保存完整训练集（带折标记）
        train_full.to_csv(f'{self.output_dir}/train_full.csv', index=False)
        print(f"✅ 训练集: {self.output_dir}/train_full.csv")

        # 保存测试集
        test_data.to_csv(f'{self.output_dir}/test_processed.csv', index=False)
        print(f"✅ 测试集: {self.output_dir}/test_processed.csv")

        # 保存各折数据
        for fold in range(train_full['fold'].max() + 1):
            fold_train = train_full[train_full['fold'] != fold]
            fold_val = train_full[train_full['fold'] == fold]

            fold_train.to_csv(f'{self.output_dir}/fold{fold}_train.csv', index=False)
            fold_val.to_csv(f'{self.output_dir}/fold{fold}_val.csv', index=False)

        print(f"✅ 交叉验证数据: {self.output_dir}/fold*.csv")

    def run(self):
        """执行完整预处理流水线"""
        print("\n" + "🚀 " * 20)
        print("天池数据预处理流水线")
        print("🚀 " * 20)

        # 1. 加载数据
        train_data, train_labels, test_data = self.load_data()

        # 2. 数据探索
        numeric_cols, categorical_cols = self.explore_data(train_data, train_labels)

        # 3. 处理缺失值
        train_data = self.handle_missing_values(train_data, strategy='median')
        test_data = self.handle_missing_values(test_data, strategy='median')

        # 4. 特征编码
        train_data, test_data = self.encode_features(train_data, test_data)

        # 5. 特征标准化
        train_data, test_data = self.normalize_features(train_data, test_data, method='standard')

        # 6. 合并标签
        train_full = train_data.merge(train_labels, on='id', how='left')

        # 7. 创建交叉验证折
        train_full = self.create_folds(train_full, n_folds=5)

        # 8. 保存数据
        self.save_data(train_full, test_data)

        print("\n" + "✅ " * 20)
        print("预处理完成！")
        print("✅ " * 20)
        print(f"\n数据集信息:")
        print(f"  训练集: {train_full.shape}")
        print(f"  测试集: {test_data.shape}")
        print(f"  特征数: {len(train_data.columns)}")
        print(f"  输出目录: {self.output_dir}")

if __name__ == '__main__':
    preprocessor = TianchiPreprocessor(
        data_dir='./public_dataset_a',
        output_dir='./processed_data'
    )
    preprocessor.run()
