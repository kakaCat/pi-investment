# Quantsys-v2 性能基准测试套件

## 概述

本目录包含Quantsys-v2项目的完整性能基准测试套件，用于验证各项优化措施的实际效果。

## 测试项目

### 1. 因子计算性能测试 (`benchmark_factors.py`)

**测试场景：**
- 100/1K/5K股票 × 252天数据
- 批量计算5个技术因子（SMA, EMA, RSI, MACD, Bollinger Bands）

**对比维度：**
- CPU vs GPU计算
- 不同数据规模

**预期性能提升：** 10-100倍（GPU加速）

### 2. 机器学习性能测试 (`benchmark_ml.py`)

**测试场景：**
- 随机森林训练（1K/10K/50K样本 × 50特征）
- 逻辑回归训练
- XGBoost训练（如果可用）

**对比维度：**
- CPU vs GPU训练
- 训练时间 vs 预测时间

**预期性能提升：** 10-50倍（GPU加速）

### 3. 数据库查询性能测试（内置于 `BenchmarkService`）

**测试场景：**
- 10/100/1000次查询

**对比维度：**
- 同步查询 vs 异步查询
- 单次模拟查询 vs 批量异步调度

**预期性能提升：** 10-1000倍（异步I/O + 批量查询）

### 4. 缓存性能测试 (`benchmark_cache.py`)

**测试场景：**
- 1000次读写操作
- 真实场景模拟（100次查询 × 10只股票）

**对比维度：**
- 内存缓存 vs Redis缓存
- 有缓存 vs 无缓存
- 缓存命中率测试

**预期性能提升：** 10-100倍（缓存命中）

### 5. 策略回测性能测试 (`benchmark_backtest.py`)

**测试场景：**
- 50/100/200只股票回测
- 1年/3年数据

**对比维度：**
- 串行 vs 并行回测
- 不同worker数量

**预期性能提升：** 4-8倍（多核并行）

## 快速开始

### 运行所有测试

```bash
cd quantsys-v2/benchmarks
python3 run_all_benchmarks.py
```

这将依次运行所有基准测试，并生成综合报告。

### 运行单个测试

```bash
# 因子计算测试
python3 benchmark_factors.py

# 机器学习测试
python3 benchmark_ml.py

# 数据库查询测试（服务内置）
python3 - <<'PY'
from services.benchmark_service import BenchmarkService
BenchmarkService().run_benchmarks(["database"])
PY

# 缓存测试
python3 benchmark_cache.py

# 回测测试
python3 benchmark_backtest.py
```

## 测试结果

### 结果文件位置

- **JSON数据：** `benchmarks/results/*.json`
- **综合报告：** `docs/reports/PERFORMANCE_BENCHMARK_REPORT.md`

### 结果格式

每个测试生成一个JSON文件，包含：
- 测试场景配置
- 性能指标（平均时间、标准差、吞吐量）
- CPU vs GPU对比（如适用）
- 加速比计算

## 测试环境要求

### 基础环境

```bash
# Python 3.8+
python3 --version

# 安装依赖
pip install -r requirements.txt
```

### GPU测试（可选）

如需运行GPU加速测试，需要安装：

```bash
# CUDA 11.x
nvidia-smi

# CuPy (GPU因子计算)
pip install cupy-cuda11x

# cuML (GPU机器学习)
pip install cuml-cu11

# XGBoost GPU支持
pip install xgboost[gpu]
```

**注意：** 如果没有GPU，测试会自动跳过GPU部分，只运行CPU测试。

### 数据库测试（可选）

如需运行真实数据库测试，需要：

```bash
# PostgreSQL 12+
psql --version

# 异步驱动
pip install asyncpg

# 配置数据库连接
# 编辑 .env 文件或使用默认配置
```

**注意：** 如果数据库不可用，会使用模拟数据进行测试。

### Redis测试（可选）

如需测试Redis缓存：

```bash
# Redis 6+
redis-cli --version

# Python客户端
pip install redis hiredis
```

**注意：** 如果Redis不可用，会使用内存缓存进行测试。

## 测试配置

### 修改测试参数

每个测试脚本都可以通过修改代码中的`scenarios`列表来调整测试场景：

```python
# benchmark_factors.py
scenarios = [
    {'n_stocks': 100, 'n_days': 252, 'name': '100股票×252天'},
    {'n_stocks': 1000, 'n_days': 252, 'name': '1K股票×252天'},
    # 添加更多场景...
]
```

### 调整重复次数

默认每个测试重复3次取平均值，可以修改`repeat`参数：

```python
result = benchmark_batch_factors(calc, df, factors, repeat=5)  # 重复5次
```

## 性能指标说明

### 时间指标

- **mean_time**: 平均执行时间
- **std_time**: 标准差
- **min_time**: 最小执行时间
- **max_time**: 最大执行时间

### 吞吐量指标

- **QPS**: 每秒查询数（Queries Per Second）
- **throughput**: 吞吐量（如：股票/秒、样本/秒）
- **ops_per_sec**: 每秒操作数

### 加速比

```
加速比 = 基准时间 / 优化后时间
```

例如：
- 2x = 快2倍
- 10x = 快10倍
- 100x = 快100倍

## 故障排除

### GPU测试失败

```bash
# 检查CUDA是否可用
python3 -c "import cupy; print(cupy.cuda.runtime.getDeviceCount())"

# 检查cuML是否可用
python3 -c "import cuml; print(cuml.__version__)"
```

### 数据库连接失败

```bash
# 检查PostgreSQL是否运行
pg_isready

# 检查连接参数
psql -h localhost -U postgres -d quantsys
```

### 内存不足

如果测试数据量过大导致内存不足，可以：
1. 减少测试场景的数据规模
2. 减少重复次数
3. 分批运行测试

## 性能优化建议

根据测试结果，可以：

1. **识别瓶颈：** 找出性能最差的环节
2. **验证优化：** 对比优化前后的性能指标
3. **调整配置：** 根据实际硬件调整并行度、批量大小等参数
4. **持续监控：** 定期运行基准测试，确保性能不退化

## 贡献指南

### 添加新的基准测试

1. 创建新的测试脚本 `benchmark_xxx.py`
2. 实现测试函数，返回标准格式的结果
3. 将脚本添加到 `run_all_benchmarks.py` 的测试列表
4. 更新本README文档

### 测试脚本模板

```python
#!/usr/bin/env python3
"""
新测试项目描述
"""
import sys
import time
import numpy as np
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

def run_xxx_benchmarks():
    """运行XXX基准测试"""
    results = {
        'test_name': 'xxx',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'scenarios': []
    }
    
    # 实现测试逻辑...
    
    # 保存结果
    output_file = Path(__file__).parent / 'results' / 'benchmark_xxx.json'
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    return results

def main():
    try:
        results = run_xxx_benchmarks()
        return 0
    except Exception as e:
        print(f"错误: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
```

## 许可证

本测试套件遵循项目主许可证。

## 联系方式

如有问题或建议，请提交Issue或Pull Request。
