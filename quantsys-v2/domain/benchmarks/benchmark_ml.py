#!/usr/bin/env python3
"""
机器学习性能基准测试

测试场景：
- 随机森林训练（1K/10K/100K样本）
- XGBoost训练（1K/10K/100K样本）
- 批量预测（1K/10K/100K样本）
- CPU vs GPU对比
"""

import sys
import time
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Tuple
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.quantlib.gpu_acceleration.gpu_ml import GPUMLTrainer


def generate_classification_data(
    n_samples: int,
    n_features: int = 50,
    n_informative: int = 30
) -> Tuple[np.ndarray, np.ndarray]:
    """生成分类测试数据"""
    np.random.seed(42)

    # 生成特征
    X = np.random.randn(n_samples, n_features)

    # 生成标签（基于前n_informative个特征）
    weights = np.random.randn(n_informative)
    y_continuous = X[:, :n_informative] @ weights
    y = (y_continuous > np.median(y_continuous)).astype(int)

    return X, y


def benchmark_model_training(
    trainer: GPUMLTrainer,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    model_type: str,
    repeat: int = 3,
    **model_params
) -> Dict:
    """测试模型训练性能"""
    train_times = []
    predict_times = []
    scores = []

    for _ in range(repeat):
        # 训练
        if model_type == 'random_forest':
            model, train_time = trainer.train_random_forest(
                X_train, y_train, **model_params
            )
        elif model_type == 'logistic_regression':
            model, train_time = trainer.train_logistic_regression(
                X_train, y_train, **model_params
            )
        elif model_type == 'xgboost':
            model, train_time = trainer.train_xgboost(
                X_train, y_train, **model_params
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        train_times.append(train_time)

        # 预测
        start = time.perf_counter()
        score = model.score(X_test, y_test)
        predict_time = time.perf_counter() - start

        predict_times.append(predict_time)
        scores.append(score)

    return {
        'train_time_mean': np.mean(train_times),
        'train_time_std': np.std(train_times),
        'train_time_min': np.min(train_times),
        'predict_time_mean': np.mean(predict_times),
        'predict_time_std': np.std(predict_times),
        'score_mean': np.mean(scores),
        'score_std': np.std(scores)
    }


def run_ml_benchmarks():
    """运行机器学习基准测试"""
    print("=" * 80)
    print("机器学习性能基准测试")
    print("=" * 80)

    results = {
        'test_name': 'machine_learning',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'scenarios': []
    }

    # 测试场景
    scenarios = [
        {'n_samples': 1000, 'n_features': 50, 'name': '1K样本×50特征'},
        {'n_samples': 10000, 'n_features': 50, 'name': '10K样本×50特征'},
        {'n_samples': 50000, 'n_features': 50, 'name': '50K样本×50特征'},
    ]

    # 模型配置
    models = [
        {
            'type': 'random_forest',
            'name': '随机森林',
            'params': {'n_estimators': 100, 'max_depth': 10}
        },
        {
            'type': 'logistic_regression',
            'name': '逻辑回归',
            'params': {'max_iter': 1000}
        },
    ]

    # 尝试添加XGBoost
    try:
        import xgboost
        models.append({
            'type': 'xgboost',
            'name': 'XGBoost',
            'params': {'n_estimators': 100, 'max_depth': 6}
        })
    except ImportError:
        print("XGBoost不可用，跳过XGBoost测试")

    for scenario in scenarios:
        print(f"\n{'='*80}")
        print(f"场景: {scenario['name']}")
        print(f"{'='*80}")

        # 生成测试数据
        print(f"生成测试数据...")
        X, y = generate_classification_data(
            scenario['n_samples'],
            scenario['n_features']
        )

        # 分割数据
        split = int(0.8 * scenario['n_samples'])
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        print(f"训练集: {len(X_train):,} 样本")
        print(f"测试集: {len(X_test):,} 样本")

        scenario_result = {
            'name': scenario['name'],
            'n_samples': scenario['n_samples'],
            'n_features': scenario['n_features'],
            'n_train': len(X_train),
            'n_test': len(X_test),
            'models': []
        }

        for model_config in models:
            print(f"\n[{model_config['name']}]")

            model_result = {
                'name': model_config['name'],
                'type': model_config['type'],
                'cpu': {},
                'gpu': {}
            }

            # CPU训练
            print(f"  CPU训练...")
            cpu_trainer = GPUMLTrainer(use_gpu=False)

            cpu_result = benchmark_model_training(
                cpu_trainer,
                X_train, y_train,
                X_test, y_test,
                model_config['type'],
                repeat=3,
                **model_config['params']
            )
            model_result['cpu'] = cpu_result

            print(f"    训练时间: {cpu_result['train_time_mean']:.3f}s ± {cpu_result['train_time_std']:.3f}s")
            print(f"    预测时间: {cpu_result['predict_time_mean']:.4f}s")
            print(f"    准确率: {cpu_result['score_mean']:.4f} ± {cpu_result['score_std']:.4f}")

            # GPU训练
            try:
                print(f"  GPU训练...")
                gpu_trainer = GPUMLTrainer(use_gpu=True)

                if gpu_trainer.use_gpu:
                    gpu_result = benchmark_model_training(
                        gpu_trainer,
                        X_train, y_train,
                        X_test, y_test,
                        model_config['type'],
                        repeat=3,
                        **model_config['params']
                    )
                    model_result['gpu'] = gpu_result

                    print(f"    训练时间: {gpu_result['train_time_mean']:.3f}s ± {gpu_result['train_time_std']:.3f}s")
                    print(f"    预测时间: {gpu_result['predict_time_mean']:.4f}s")
                    print(f"    准确率: {gpu_result['score_mean']:.4f} ± {gpu_result['score_std']:.4f}")

                    # 计算加速比
                    train_speedup = cpu_result['train_time_mean'] / gpu_result['train_time_mean']
                    predict_speedup = cpu_result['predict_time_mean'] / gpu_result['predict_time_mean']

                    model_result['train_speedup'] = train_speedup
                    model_result['predict_speedup'] = predict_speedup

                    print(f"\n  [性能对比]")
                    print(f"    训练加速比: {train_speedup:.2f}x")
                    print(f"    预测加速比: {predict_speedup:.2f}x")
                else:
                    print("    GPU不可用，跳过GPU测试")
                    model_result['gpu'] = None
            except Exception as e:
                print(f"    GPU测试失败: {e}")
                model_result['gpu'] = None

            scenario_result['models'].append(model_result)

        results['scenarios'].append(scenario_result)

    # 保存结果
    output_file = Path(__file__).parent / 'results' / 'benchmark_ml.json'
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*80}")
    print(f"测试完成！结果已保存到: {output_file}")
    print(f"{'='*80}")

    return results


def main():
    """主函数"""
    try:
        results = run_ml_benchmarks()

        # 打印汇总
        print("\n" + "=" * 80)
        print("测试汇总")
        print("=" * 80)

        for scenario in results['scenarios']:
            print(f"\n{scenario['name']}:")

            for model in scenario['models']:
                print(f"  {model['name']}:")
                print(f"    CPU训练: {model['cpu']['train_time_mean']:.3f}s")

                if model['gpu']:
                    print(f"    GPU训练: {model['gpu']['train_time_mean']:.3f}s")
                    print(f"    加速比: {model.get('train_speedup', 0):.2f}x")
                else:
                    print(f"    GPU: 不可用")

        return 0
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
