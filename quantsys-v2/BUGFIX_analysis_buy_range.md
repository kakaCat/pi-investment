# Bug Fix: analysis.buy_range

## 修复日期
2026-06-22

## 问题描述

`analysis.buy_range` 工具在调用时返回误导性错误："akshare 或 pandas 模块不可用"，即使这些模块实际上是可用的。真正的问题被错误的异常处理掩盖了。

## 根本原因

1. **嵌套的 try-except 块**：旧代码有双层 try-except 结构，内层异常被外层的通用 ImportError 捕获，导致真实错误信息丢失

2. **Polars DataFrame 检查错误**：`KlineRepository.get_daily_klines()` 返回 Polars DataFrame，但代码使用了不兼容的检查方式：
   ```python
   if not klines or len(klines) == 0:  # ❌ 错误：对 DataFrame 使用 not 会抛出异常
   ```

3. **DataFrame 转换错误**：尝试用 `pd.DataFrame(klines)` 从 Polars DataFrame 构造 Pandas DataFrame，这不是正确的方法

## 修复内容

### 文件：`application/services/technical_analysis_service.py`

**修改前的问题代码：**
```python
try:
    import pandas as pd
    from adapters.outbound.datasources.manager import get_data_source_manager
    
    try:
        # ... 数据获取逻辑 ...
        if not klines or len(klines) == 0:  # ❌ Polars DataFrame 检查错误
            return {'success': False, 'error': '没有历史数据'}
        
        df = pd.DataFrame(klines)  # ❌ 不正确的转换方式
        
    except Exception as e:
        return {'success': False, 'error': f'计算失败: {str(e)}'}

except ImportError:
    return {'success': False, 'error': 'akshare 或 pandas 模块不可用'}  # ❌ 误导性错误
```

**修复后的代码：**
```python
try:
    import pandas as pd
    from adapters.outbound.repositories.kline_repository import KlineRepository
    
    # ... 数据获取逻辑 ...
    
    if klines is None or klines.is_empty():  # ✅ 正确的 Polars DataFrame 检查
        return {'success': False, 'error': f'股票 {symbol} 没有历史数据'}
    
    # 将 Polars DataFrame 转换为 Pandas DataFrame
    df = klines.to_pandas()  # ✅ 正确的转换方式
    
    # ... 计算逻辑 ...
    
except ImportError as e:
    self.logger.error(f"模块导入失败: {e}")
    return {'success': False, 'error': f'模块导入失败: {str(e)}'}  # ✅ 具体的错误信息

except Exception as e:
    self.logger.error(f"买入区间计算失败: {e}", exc_info=True)
    return {'success': False, 'error': f'买入区间计算失败: {str(e)}'}  # ✅ 真实错误信息
```

## 关键改进

1. **简化异常处理**：移除嵌套 try-except，使用单层结构，确保真实错误能够被正确捕获和报告

2. **修复 DataFrame 检查**：
   - 从：`if not klines or len(klines) == 0`
   - 到：`if klines is None or klines.is_empty()`

3. **修复数据转换**：
   - 从：`df = pd.DataFrame(klines)`
   - 到：`df = klines.to_pandas()`

4. **改进错误消息**：所有错误现在都包含具体的错误信息，而不是通用的误导性消息

## 验证

修复后，工具能够正确处理：

```bash
$ python -c "
from application.services.technical_analysis_service import TechnicalAnalysisService
service = TechnicalAnalysisService()
result = service.calculate_buy_range('600000')
print(result)
"

# 输出：
{
  'success': True,
  'data': {
    'symbol': '600000',
    'current_price': 9.34,
    'lower_bound': 8.81,
    'upper_bound': 9.47,
    'ma20': 9.14,
    'recommendation': 'hold',
    'update_time': '2026-06-22T14:20:11.252575'
  }
}
```

## 部署说明

修复后需要重启 quantsys-v2 后端服务以应用更改：

```bash
# 使用新的启动脚本（推荐）
cd quantsys-v2
./start_api.sh

# 或手动启动
cd quantsys-v2
export PGDATABASE=quant_investment PGHOST=127.0.0.1 PGPORT=5432 PGUSER=mac PYTHONPATH=.
python adapters/inbound/api/server.py
```

**注意**：启动前确保清理 Python 缓存：
```bash
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
```

## 影响范围

- **修复的工具**：`analysis.buy_range` (通过 `analysis_cli` 调用)
- **修改的文件**：`application/services/technical_analysis_service.py`
- **向后兼容**：是，API 接口和返回格式保持不变
- **测试状态**：已通过直接 Python 函数调用测试

## 相关问题

该服务中还有其他方法使用了类似的反模式（双层 try-except + 误导性错误消息）：
- `get_price_action()` (第81行)
- `analyze_candlestick()` (第252行)
- `get_exit_plan()` (第343行)

建议在后续版本中采用相同的修复策略。

## 后续改进建议

1. 统一所有服务方法的异常处理模式
2. 为 Polars/Pandas DataFrame 操作创建辅助函数
3. 添加单元测试覆盖 DataFrame 转换逻辑
4. 考虑使用类型提示明确 DataFrame 类型（Polars vs Pandas）
