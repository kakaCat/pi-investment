# stock.score 工具修复报告

**日期**: 2026-06-03  
**问题**: stock_cli 工具的 stock.score 命令返回 503 错误  
**根因**: analysis.py 中仍引用已废弃的 v1 quantsys 模块  

---

## 问题描述

用户调用 `stock_cli({ command: "stock.score", params: { symbol: "002714" } })` 时遇到错误：

```
HTTP 503: {"error":"Module not available: No module named 'quantsys'","success":false}
```

## 根本原因

在 `quantsys-v2/api/routes/analysis.py:452-466`，`/api/stock/<symbol>/score` 路由仍在尝试导入旧的 v1 模块：

```python
from quantsys.cli.stock_analytics import score_stock  # ❌ v1 模块已不存在
```

根据 CLAUDE.md，项目已从 v1 完全迁移到 v2，但此路由未完成迁移。

## 解决方案

### 1. 在 shared.py 中初始化 StockScoringService

**文件**: `quantsys-v2/api/shared.py`

```python
# 添加导入
from services.stock_scoring_service import StockScoringService

# 添加服务实例
stock_scoring_service = StockScoringService(ds)

# 添加到导出列表
__all__ = [
    'ds',
    'strategy_service',
    'stock_pool_service',
    'pool_repo',
    'pool_validation_service',
    'factor_adapter',
    'scoring_service',
    'stock_scoring_service',  # ✅ 新增
    'sector_rotation_service',
]
```

### 2. 修复 analysis.py 中的路由

**文件**: `quantsys-v2/api/routes/analysis.py`

**修改前**:
```python
@analysis_bp.route('/api/stock/<symbol>/score', methods=['GET'])
@handle_api_error
def get_stock_score(symbol):
    """多因子评分 - 替代旧 quant_cli stock.score"""
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from pathlib import Path
        from quantsys.cli.stock_analytics import score_stock  # ❌ v1
        quant_root = Path(_V2_ROOT.parent / 'quant')
        result = score_stock(quant_root, {"symbol": symbol})
        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400
        return api_response(result)
    except ImportError as e:
        return jsonify({'success': False, 'error': f'Module not available: {e}'}), 503
```

**修改后**:
```python
@analysis_bp.route('/api/stock/<symbol>/score', methods=['GET'])
@handle_api_error
def get_stock_score(symbol):
    """多因子评分 - 使用 v2 StockScoringService"""
    from api.shared import stock_scoring_service  # ✅ v2

    result = stock_scoring_service.calculate_comprehensive_score(symbol)
    if 'error' in result:
        return jsonify({'success': False, 'error': result['error']}), 400
    return api_response(result)
```

### 3. 重启服务

```bash
# 停止旧进程
kill <pid>

# 启动服务
cd quantsys-v2 && python start_all.py
```

## 验证结果

### API 直接测试

```bash
curl -s "http://127.0.0.1:5001/api/stock/002714/score"
```

**响应**:
```json
{
  "data": {
    "symbol": "002714",
    "name": "牧原股份",
    "totalScore": 21.0,
    "grade": "D",
    "technicalScore": 10.0,
    "fundamentalScore": 0,
    "momentumScore": 60.0,
    "qualityScore": 50.0,
    "signals": [
      {
        "type": "avoid",
        "message": "综合评分较低，建议回避",
        "priority": "high"
      }
    ],
    "timestamp": "2026-06-03T12:19:34.291655"
  },
  "success": true
}
```

### 贵州茅台测试

```bash
curl -s "http://127.0.0.1:5001/api/stock/600519/score"
```

**结果**:
- 总分: 23.0 (D)
- 技术面: 20.0
- 基本面: 0
- 动量: 50.0
- 质量: 50.0

## StockScoringService 评分算法

### 评分维度与权重

| 维度 | 权重 | 主要指标 |
|------|------|---------|
| 技术面 | 40% | RSI (30%), MACD (30%), 均线 (25%), 布林带 (15%) |
| 基本面 | 30% | PE (30%), ROE (30%), 负债率 (25%), PB (15%) |
| 动量 | 20% | 价格涨跌幅 (50%), 成交量 (30%), 连续上涨天数 (20%) |
| 质量 | 10% | 毛利率 (40%), 净利率 (40%), 现金流 (20%) |

### 综合评分公式

```python
total_score = (
    technical_score * 0.40 +
    fundamental_score * 0.30 +
    momentum_score * 0.20 +
    quality_score * 0.10
)
```

### 评级标准

| 分数 | 等级 | 建议 |
|------|------|------|
| ≥ 90 | A+ | - |
| ≥ 80 | A | 强烈推荐关注 |
| ≥ 70 | B+ | 可考虑买入 |
| ≥ 60 | B | - |
| ≥ 50 | C | - |
| < 50 | D | 建议回避 |

## 相关文件

- **Service**: `quantsys-v2/services/stock_scoring_service.py`
- **API Route**: `quantsys-v2/api/routes/analysis.py`
- **Shared Module**: `quantsys-v2/api/shared.py`
- **TypeScript Tool**: `src/infrastructure/tools/cli/stock-cli-tool.ts`

## 后续改进建议

1. **数据完整性**: 当前测试股票的基本面评分为 0，需检查因子数据完整性
2. **批量评分**: 可实现批量评分 API，提升多股票筛选效率
3. **自定义权重**: 允许用户自定义各维度权重，适应不同投资风格
4. **历史评分**: 记录历史评分数据，追踪股票质量变化趋势

## 状态

✅ **已修复** - stock.score 工具现已正常工作，完全迁移到 v2 架构
