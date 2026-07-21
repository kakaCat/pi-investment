# Quantsys-v2 示例代码

本目录包含Quantsys-v2所有核心功能的完整示例代码。

## 📁 示例列表

### 1. 因子工程框架

#### example_ic_analysis.py
**IC/IR分析完整示例**

演示内容：
- 准备因子和收益数据
- 计算IC时间序列（1日、5日、10日、20日）
- 计算IC统计指标（IC_mean, IC_IR, IC_positive_rate等）
- 因子质量评分
- 可视化IC曲线
- 对比多个因子的表现

运行：
```bash
python example_ic_analysis.py
```

#### example_orthogonalization.py
**因子正交化完整示例**

演示内容：
- 创建相关的因子数据
- 计算因子相关性矩阵
- Schmidt正交化（基于基础因子）
- PCA正交化（主成分分析）
- 对称正交化（QR分解）
- 对比不同正交化方法的效果
- 实际应用场景

运行：
```bash
python example_orthogonalization.py
```

### 2. 期权策略框架

#### example_greeks_calculator.py
**期权Greeks计算完整示例**

演示内容：
- Black-Scholes期权定价
- Greeks计算（Delta, Gamma, Theta, Vega, Rho）
- Greeks解读和应用
- 隐含波动率计算
- Greeks敏感性分析
- 期权策略Greeks（跨式、牛市价差、铁鹰式）

运行：
```bash
python example_greeks_calculator.py
```

### 3. GPU加速框架

#### example_gpu_factors.py
**GPU加速因子计算完整示例**

演示内容：
- GPU环境检测
- 单个因子CPU vs GPU性能对比
- 批量因子计算
- 性能基准测试（不同数据规模）
- 大规模数据处理（100只股票）
- 实用技巧和优化建议

运行：
```bash
python example_gpu_factors.py
```

### 4. 跨品种策略框架

#### example_index_hedge.py
**股指期货对冲完整示例**

演示内容：
- Beta计算和滚动Beta
- 静态对冲策略
- 动态对冲策略（根据市场状况调整）
- 最小方差对冲（优化对冲比率）
- 对冲效果评估
- 实际应用场景

运行：
```bash
python example_index_hedge.py
```

### 5. 高频策略框架

#### example_market_making.py
**做市策略完整示例**

演示内容：
- 订单簿管理和分析
- 做市报价计算
- 库存管理和风险控制
- 模拟做市交易
- 统计套利策略
- 风险管理技巧
- 性能指标计算

运行：
```bash
python example_market_making.py
```

## 🚀 快速开始

### 运行单个示例
```bash
# 进入项目根目录
cd quantsys-v2

# 运行任意示例
python docs/examples/example_ic_analysis.py
```

### 运行所有示例
```bash
python docs/examples/run_all_examples.py
```

## 📊 示例统计

| 示例 | 代码行数 | 运行时间 | 难度 |
|------|---------|---------|------|
| IC分析 | 258 | ~5秒 | ⭐⭐ |
| 因子正交化 | 325 | ~3秒 | ⭐⭐⭐ |
| 期权Greeks | 364 | ~2秒 | ⭐⭐ |
| GPU加速 | 398 | ~10秒 | ⭐⭐⭐ |
| 股指对冲 | 457 | ~4秒 | ⭐⭐⭐ |
| 做市策略 | 420 | ~3秒 | ⭐⭐⭐⭐ |

总计：**2,222行代码**

## 💡 学习建议

### 初学者路径
1. 先运行 `example_ic_analysis.py` 了解因子评估
2. 再运行 `example_greeks_calculator.py` 了解期权定价
3. 阅读代码注释，理解每个步骤

### 进阶路径
1. 运行 `example_orthogonalization.py` 学习因子处理
2. 运行 `example_gpu_factors.py` 了解性能优化
3. 修改参数，观察结果变化

### 实战路径
1. 运行 `example_index_hedge.py` 学习对冲策略
2. 运行 `example_market_making.py` 学习高频策略
3. 使用真实数据替换模拟数据
4. 构建自己的策略

## 🔧 依赖要求

### 必需依赖
```bash
numpy>=1.20.0
pandas>=1.3.0
scipy>=1.7.0
scikit-learn>=0.24.0
```

### 可选依赖
```bash
# GPU加速（example_gpu_factors.py）
cupy-cuda11x  # CUDA 11.x
cupy-cuda12x  # CUDA 12.x

# 可视化（部分示例）
matplotlib>=3.3.0
seaborn>=0.11.0
```

## 📝 代码特点

所有示例代码具有以下特点：

✅ **完整性** - 可以独立运行，无需额外配置
✅ **清晰性** - 详细的中文注释和说明
✅ **实用性** - 基于真实的量化交易场景
✅ **教学性** - 循序渐进，易于理解
✅ **可扩展** - 模块化设计，易于修改

## 🐛 故障排查

### 问题1: 导入错误
```
ModuleNotFoundError: No module named 'quant'
```

**解决方案**：
```bash
# 确保在项目根目录运行
cd quantsys-v2
python docs/examples/example_ic_analysis.py
```

### 问题2: GPU不可用
```
GPU加速不可用，将使用CPU计算
```

**解决方案**：
- 这是正常的，代码会自动回退到CPU
- 如需GPU加速，安装cupy: `pip install cupy-cuda11x`

### 问题3: 数据维度错误
```
ValueError: shapes not aligned
```

**解决方案**：
- 检查数据格式是否正确
- 参考示例中的数据准备代码

## 📚 相关文档

- [快速入门指南](../guides/QUICK_START.md)
- [最佳实践指南](../guides/BEST_PRACTICES.md)
- [文档中心](../README.md)

## 🤝 贡献

欢迎贡献新的示例！请确保：
- 代码可以独立运行
- 包含详细的注释
- 遵循现有代码风格
- 更新本README

## 📄 许可证

MIT License
