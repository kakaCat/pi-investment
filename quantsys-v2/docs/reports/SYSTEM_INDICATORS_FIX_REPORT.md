# 系统指标显示问题修复报告

## 问题描述
前端"系统指标"列表为空，无法显示内置的技术指标。

## 根本原因
数据库中缺少系统内置指标数据（`strategy_type='builtin'`）。

## 解决方案

### 1. 数据库诊断
创建了诊断脚本 `check_strategy_configs.py` 来检查数据库状态：
- 确认使用的是 PostgreSQL 数据库（quant_investment）
- 确认表名为 `quant.strategy_configs`（不是 strategy_code）
- 发现初始数据库只有5个用户指标（strategy_type='custom'）

### 2. 创建系统指标
创建了 `create_builtin_indicators_direct.py` 脚本，直接通过数据库连接插入5个系统内置指标：

| ID | 指标名称 | 类型 | 分类 |
|----|---------|------|------|
| 8  | RSI超买超卖策略 | builtin | momentum |
| 9  | 双均线交叉策略 | builtin | trend |
| 10 | MACD金叉死叉策略 | builtin | trend |
| 11 | 布林带突破策略 | builtin | volatility |
| 12 | KDJ超买超卖策略 | builtin | momentum |

### 3. API验证
测试 `/api/indicators/list?type=system` 端点：
```bash
curl "http://127.0.0.1:5001/api/indicators/list?type=system"
```

**结果**：✅ 成功返回5个系统指标

响应示例：
```json
{
  "data": {
    "total": 5,
    "page": 1,
    "items": [
      {
        "id": 12,
        "name": "KDJ超买超卖策略",
        "strategyType": "builtin",
        "codeType": "indicator",
        "description": "KDJ指标策略，适合短线交易",
        "author": "system",
        "metadata": {
          "category": "momentum",
          "builtin": true
        }
      },
      // ... 其他4个指标
    ]
  }
}
```

## 技术细节

### 数据库配置
```bash
PGDATABASE=quant_investment
PGHOST=127.0.0.1
PGPORT=5432
PGUSER=mac
PGPASSWORD=
```

### 表结构
- 表名：`quant.strategy_configs`
- 关键字段：
  - `strategy_type`: 'builtin' (系统内置) | 'custom' (用户自定义)
  - `code_type`: 'indicator' (指标) | 'script' (脚本)
  - `strategy_name`: 策略名称
  - `code_content`: 策略代码
  - `metadata`: JSONB字段，存储category等额外信息

### API过滤逻辑
```python
# api/server.py 第3833-3834行
elif filter_type == 'system':
    indicators = [i for i in indicators if i.get('strategy_type') != 'custom']
```

## 验证步骤

### 1. 数据库验证
```bash
cd quantsys-v2
python3 check_strategy_configs.py
```

预期输出：
```
总指标数: 10
系统指标数: 5
用户指标数: 5
```

### 2. API验证
```bash
curl -s "http://127.0.0.1:5001/api/indicators/list?type=system" | python3 -m json.tool
```

预期：返回5个系统指标

### 3. 前端验证
1. 访问 http://127.0.0.1:3001
2. 进入"指标IDE"页面
3. 点击"系统指标"标签
4. 确认显示5个内置指标

## 服务状态

### 后端服务
- 端口：5001
- 状态：✅ 运行中
- 启动命令：
  ```bash
  cd quantsys-v2
  PYTHONPATH=/Users/mac/Documents/ai/pi-investment/quantsys-v2:$PYTHONPATH python3 api/server.py
  ```

### 前端服务
- 端口：3001
- 状态：✅ 运行中
- 访问地址：http://127.0.0.1:3001

## 相关文件

### 新创建的文件
1. `check_strategy_configs.py` - 数据库状态检查脚本
2. `create_builtin_indicators_direct.py` - 系统指标创建脚本
3. `SYSTEM_INDICATORS_FIX_REPORT.md` - 本报告

### 修改的文件
无需修改代码，问题通过添加数据解决。

## 后续建议

1. **数据持久化**：将系统指标创建脚本集成到数据库初始化流程中
2. **更多指标**：考虑添加更多常用技术指标（CCI、ATR、OBV等）
3. **指标分类**：完善指标分类体系（趋势、动量、波动率、成交量）
4. **文档完善**：为每个系统指标添加详细的使用说明和参数说明

## 总结

✅ **问题已解决**：系统指标现在可以正常显示
- 数据库中已有5个系统内置指标
- API端点正常返回系统指标列表
- 前端和后端服务都在正常运行
- 用户可以在指标IDE页面查看和使用系统指标

---
报告生成时间：2026-05-24
修复人员：AI Assistant
