# ML Pipeline 实现方案

## 项目概述

独立的机器学习管道，用于股票量化策略的特征工程、模型训练和预测。

## 目录结构

```
ml-pipeline/
├── ml_pipeline.py          # CLI 入口
├── db.py                   # 软链接到 ../pipeline/db.py
├── features/               # 特征工程
│   ├── __init__.py
│   ├── technical.py        # 技术特征
│   └── fundamental.py      # 基本面特征
├── models/                 # 模型定义
│   ├── __init__.py
│   └── signal_model.py     # 信号预测模型
├── training/               # 训练模块
│   ├── __init__.py
│   └── trainer.py          # 训练器
├── inference/              # 推理模块
│   ├── __init__.py
│   └── predictor.py        # 预测器
├── tests/                  # 测试
│   └── test_cli.py
└── requirements.txt        # 依赖
```

## Phase 1: 基础框架

### 1.1 CLI 入口 (ml_pipeline.py)

```python
#!/usr/bin/env python3
"""ML Pipeline - 机器学习管道"""

import argparse
import sys

def main(argv=None):
    parser = argparse.ArgumentParser(description='ML Pipeline')
    subparsers = parser.add_subparsers(dest='command')

    # train 命令
    train_parser = subparsers.add_parser('train')
    train_parser.add_argument('--model', default='signal')

    # predict 命令
    predict_parser = subparsers.add_parser('predict')
    predict_parser.add_argument('--model', default='signal')

    # evaluate 命令
    evaluate_parser = subparsers.add_parser('evaluate')
    evaluate_parser.add_argument('--model', default='signal')

    # list-models 命令
    list_parser = subparsers.add_parser('list-models')

    args = parser.parse_args(argv)

    if args.command == 'train':
        print(f"[Train] 训练模型: {args.model}")
    elif args.command == 'predict':
        print(f"[Predict] 生成预测: {args.model}")
    elif args.command == 'evaluate':
        print(f"[Evaluate] 评估模型: {args.model}")
    elif args.command == 'list-models':
        print("[List] 可用模型: signal")
    else:
        parser.print_help()
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
```

### 1.2 requirements.txt

```
scikit-learn>=1.3.0
xgboost>=2.0.0
pandas>=2.0.0
numpy>=1.24.0
```

### 1.3 测试 (tests/test_cli.py)

```python
import unittest
from ml_pipeline import main

class TestCLI(unittest.TestCase):
    def test_train_command(self):
        result = main(['train', '--model', 'signal'])
        self.assertEqual(result, 0)

    def test_predict_command(self):
        result = main(['predict'])
        self.assertEqual(result, 0)

    def test_evaluate_command(self):
        result = main(['evaluate'])
        self.assertEqual(result, 0)

    def test_list_models_command(self):
        result = main(['list-models'])
        self.assertEqual(result, 0)
```

## 实现步骤

1. 创建目录结构
2. 实现 ml_pipeline.py
3. 创建 requirements.txt
4. 创建软链接: `ln -s ../pipeline/db.py ml-pipeline/db.py`
5. 创建空的 __init__.py 文件
6. 实现测试
7. 运行测试验证
