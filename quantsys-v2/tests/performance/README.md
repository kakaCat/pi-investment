# Performance Tests

性能基准测试目录，用于验证关键组件的性能指标。

## 测试文件

### test_talib_performance.py
TA-Lib 因子计算性能测试，对比 C 实现的性能优势。

**测试因子：**
- MACD（指数平滑移动平均线）
- RSI14（相对强弱指标）
- ROC10（变化率）
- Momentum10（动量指标）

**运行：**
```bash
python tests/performance/test_talib_performance.py
```

**预期结果：** TA-Lib C 实现比 pandas 快 5-10 倍

### test_factor_performance_benchmark.py
因子库性能基准测试，覆盖 104 个技术因子的计算性能。

**测试维度：**
- 不同数据量（100/500/1000 根K线）
- 不同因子类别（动量/趋势/波动率/成交量/均线/反转）
- 批量计算性能

**运行：**
```bash
python tests/performance/test_factor_performance_benchmark.py
```

## 性能指标

| 数据量 | MACD | RSI14 | ROC10 | Momentum10 |
|--------|------|-------|-------|------------|
| 100 条  | 0.01ms | 0.01ms | 0.01ms | 0.01ms |
| 500 条  | 0.04ms | 0.04ms | 0.05ms | 0.04ms |
| 1000 条 | 0.07ms | 0.06ms | 0.06ms | 0.05ms |

## 添加新测试

创建新的性能测试文件时，请遵循以下规范：

1. **文件命名：** `test_<component>_performance.py`
2. **测试结构：**
   - 生成测试数据函数
   - 性能基准测试函数（含预热）
   - 多种数据量对比
   - 清晰的输出格式
3. **性能指标：** 使用毫秒（ms）为单位，保留 2 位小数
4. **文档更新：** 在本 README 中添加新测试的说明

## 相关文档

- [因子库参考文档](../../docs/FACTOR_LIBRARY_REFERENCE.md)
- [TA-Lib 增强报告](../../docs/2026-06-04-phase2-talib-enhancement-report.md)
