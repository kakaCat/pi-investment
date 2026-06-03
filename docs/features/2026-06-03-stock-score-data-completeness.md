# stock.score 数据完整性报告功能

**日期**: 2026-06-03  
**状态**: ✅ 已完成  
**版本**: v2.1  

---

## 功能概述

为 `stock.score` 工具添加数据完整性检查和报告功能，让用户清楚了解：
- 哪些数据指标缺失
- 各维度的数据完整度百分比
- 数据缺失对评分的影响
- 针对性的数据补充建议

## 问题背景

之前的 `stock.score` 实现存在以下问题：

1. **评分结果不透明**: 基本面评分为 0，用户不知道是股票质量差还是数据缺失
2. **无法判断可信度**: 数据完整度 26% 和 90% 的评分无法区分
3. **缺乏改进指引**: 用户不知道需要补充哪些数据

### 示例问题

```json
{
  "symbol": "600519",
  "totalScore": 23.0,
  "fundamentalScore": 0,  // ❌ 为什么是 0？数据缺失还是质量差？
  "grade": "D"
}
```

## 解决方案

### 1. 添加数据完整性检查方法

**文件**: `quantsys-v2/services/stock_scoring_service.py`

新增方法 `_check_missing_data()`:

```python
def _check_missing_data(self, factors: Dict) -> Dict[str, list]:
    """
    检查缺失的数据指标

    Returns:
        {
            'technical': ['rsi', 'macd', ...],
            'fundamental': ['pe', 'roe', ...],
            'momentum': ['change_pct_5d', ...],
            'quality': ['gross_margin', ...]
        }
    """
    missing = {}

    # 技术面关键指标
    technical_keys = ['rsi', 'macd', 'macd_signal', 'close', 'ma5', 'ma20', 'ma60', 'bb_position']
    technical_missing = [k for k in technical_keys if factors.get(k) is None]
    if technical_missing:
        missing['technical'] = technical_missing

    # 基本面关键指标
    fundamental_keys = ['pe', 'roe', 'debt_ratio', 'debt_to_asset_ratio', 'pb']
    fundamental_missing = [k for k in fundamental_keys if factors.get(k) is None]
    if fundamental_missing:
        missing['fundamental'] = fundamental_missing

    # 动量关键指标
    momentum_keys = ['change_pct_5d', 'change_pct_20d', 'volume_ratio']
    momentum_missing = [k for k in momentum_keys if factors.get(k) is None]
    if momentum_missing:
        missing['momentum'] = momentum_missing

    # 质量关键指标
    quality_keys = ['gross_margin', 'net_margin', 'operating_cashflow_ratio']
    quality_missing = [k for k in quality_keys if factors.get(k) is None]
    if quality_missing:
        missing['quality'] = quality_missing

    return missing
```

### 2. 添加完整度计算方法

新增方法 `_calculate_completeness()`:

```python
def _calculate_completeness(self, missing_data: Dict[str, list]) -> Dict[str, any]:
    """
    计算数据完整性百分比

    Returns:
        {
            'overall': 0.75,  # 总体完整度
            'technical': 0.875,
            'fundamental': 0.6,
            'momentum': 1.0,
            'quality': 0.67,
            'warning': '基本面数据不完整，评分可能不准确'
        }
    """
    total_fields = {
        'technical': 8,
        'fundamental': 5,
        'momentum': 3,
        'quality': 3
    }

    completeness = {}
    total_missing = 0
    total_fields_count = sum(total_fields.values())

    for dimension, count in total_fields.items():
        missing_count = len(missing_data.get(dimension, []))
        completeness[dimension] = round((count - missing_count) / count, 2)
        total_missing += missing_count

    completeness['overall'] = round((total_fields_count - total_missing) / total_fields_count, 2)

    # 生成警告信息
    warnings = []
    if completeness['overall'] < 0.5:
        warnings.append('数据严重不完整（< 50%），评分仅供参考')
    elif completeness['overall'] < 0.7:
        warnings.append('数据完整度较低（< 70%），评分可能不准确')

    if completeness.get('fundamental', 1.0) < 0.5:
        warnings.append('基本面数据严重缺失，建议补充财务数据')
    elif completeness.get('fundamental', 1.0) < 0.8:
        warnings.append('基本面数据不完整，估值评分可能偏低')

    if warnings:
        completeness['warning'] = '; '.join(warnings)

    return completeness
```

### 3. 集成到主评分方法

修改 `calculate_comprehensive_score()`:

```python
# 3. 检查数据完整性
missing_data = self._check_missing_data(factors)

# ... 计算评分 ...

result = {
    'symbol': symbol,
    'name': stock_info.get('name', ''),
    # ... 其他字段 ...
}

# 7. 添加数据完整性信息
if missing_data:
    result['missing_data'] = missing_data
    result['data_completeness'] = self._calculate_completeness(missing_data)

return result
```

## 返回结果示例

### 牧原股份 (002714) - 数据不完整

```json
{
  "symbol": "002714",
  "name": "牧原股份",
  "totalScore": 21.0,
  "grade": "D",
  "technicalScore": 10.0,
  "fundamentalScore": 0,
  "momentumScore": 60.0,
  "qualityScore": 50.0,
  "missingData": {
    "fundamental": ["pe", "roe", "debt_ratio", "debt_to_asset_ratio", "pb"],
    "momentum": ["change_pct_5d", "change_pct_20d"],
    "quality": ["gross_margin", "net_margin", "operating_cashflow_ratio"],
    "technical": ["rsi", "close", "ma60", "bb_position"]
  },
  "dataCompleteness": {
    "overall": 0.26,
    "technical": 0.50,
    "fundamental": 0.0,
    "momentum": 0.33,
    "quality": 0.0,
    "warning": "数据严重不完整（< 50%），评分仅供参考; 基本面数据严重缺失，建议补充财务数据"
  },
  "signals": [
    {
      "type": "avoid",
      "message": "综合评分较低，建议回避",
      "priority": "high"
    }
  ],
  "timestamp": "2026-06-03T12:30:00.000000"
}
```

### 格式化输出

```
股票: 牧原股份 (002714)
总分: 21.0 (D)
---
技术面: 10.0
基本面: 0
动量: 60.0
质量: 50.0

⚠️  缺失数据:
  - fundamental: pe, roe, debt_ratio, debt_to_asset_ratio, pb
  - momentum: change_pct_5d, change_pct_20d
  - quality: gross_margin, net_margin, operating_cashflow_ratio
  - technical: rsi, close, ma60, bb_position

📊 数据完整度:
  overall: 26%
  technical: 50%
  fundamental: 0%
  momentum: 33%
  quality: 0%

⚠️  数据严重不完整（< 50%），评分仅供参考; 基本面数据严重缺失，建议补充财务数据

信号:
  [avoid] 综合评分较低，建议回避
```

## 警告等级规则

| 完整度 | 等级 | 警告信息 |
|--------|------|----------|
| < 50% | 严重 | 数据严重不完整（< 50%），评分仅供参考 |
| 50-70% | 中等 | 数据完整度较低（< 70%），评分可能不准确 |
| > 70% | 良好 | 无警告 |

### 基本面特殊规则

| 基本面完整度 | 警告 |
|--------------|------|
| < 50% | 基本面数据严重缺失，建议补充财务数据 |
| 50-80% | 基本面数据不完整，估值评分可能偏低 |
| > 80% | 无警告 |

## 关键指标定义

### 技术面 (8 个)
- `rsi` - 相对强弱指标
- `macd` - MACD 值
- `macd_signal` - MACD 信号线
- `close` - 收盘价
- `ma5` - 5日均线
- `ma20` - 20日均线
- `ma60` - 60日均线
- `bb_position` - 布林带位置

### 基本面 (5 个)
- `pe` - 市盈率
- `roe` - 净资产收益率
- `debt_ratio` - 资产负债率
- `debt_to_asset_ratio` - 负债资产比
- `pb` - 市净率

### 动量 (3 个)
- `change_pct_5d` - 5日涨跌幅
- `change_pct_20d` - 20日涨跌幅
- `volume_ratio` - 量比

### 质量 (3 个)
- `gross_margin` - 毛利率
- `net_margin` - 净利率
- `operating_cashflow_ratio` - 经营现金流比率

## 用户价值

### 1. 透明度提升
✅ 明确评分依据，用户知道是数据问题还是股票质量问题  
✅ 避免误判：低分 ≠ 质量差，可能只是数据不完整

### 2. 可信度评估
✅ 数据完整度 > 70%：评分可信  
✅ 数据完整度 < 50%：仅供参考，需补充数据

### 3. 改进指引
✅ 明确列出缺失指标，指导数据采集工作  
✅ 针对性建议：优先补充基本面数据（权重 30%）

### 4. 风险控制
✅ 防止基于不完整数据做出错误投资决策  
✅ 警告信息醒目，降低误用风险

## 使用建议

### 场景 1: 数据完整（> 70%）
- ✅ 评分可信，可直接用于选股决策
- ✅ 信号准确度高

### 场景 2: 数据中等（50-70%）
- ⚠️ 评分供参考，需结合其他信息
- 💡 优先补充缺失的高权重维度（基本面、技术面）

### 场景 3: 数据不足（< 50%）
- ❌ 评分不可靠，不建议直接使用
- 📝 先补充数据再评分
- 🔍 使用其他工具（如 `data_fetch_financial`、`data_fetch_kline`）采集数据

## 后续改进

### P1 - 数据补充工具联动
- [ ] 在返回结果中添加 `data_fetch_*` 工具调用建议
- [ ] 例如：`"suggested_actions": ["data_fetch_financial(symbol='002714')", ...]`

### P2 - 自动数据补充
- [ ] 检测到关键数据缺失时，自动调用数据获取工具
- [ ] 重新计算评分并标注"已自动补充数据"

### P3 - 历史完整度趋势
- [ ] 记录每次评分的数据完整度
- [ ] 追踪数据质量改善趋势

### P4 - 自定义关键指标
- [ ] 允许用户定义哪些指标是"必需"的
- [ ] 基于用户投资风格调整警告阈值

## 相关文件

- **Service**: `quantsys-v2/services/stock_scoring_service.py`
- **API Route**: `quantsys-v2/api/routes/analysis.py`
- **TypeScript Tool**: `src/infrastructure/tools/cli/stock-cli-tool.ts`
- **修复文档**: `docs/fixes/2026-06-03-stock-score-v1-to-v2-migration.md`

## 测试验证

### 测试用例 1: 数据不完整股票

```bash
curl -s "http://127.0.0.1:5001/api/stock/002714/score"
```

**预期结果**:
- ✅ `missingData` 字段列出缺失指标
- ✅ `dataCompleteness.overall` < 0.5
- ✅ 包含警告信息

### 测试用例 2: 数据完整股票

```bash
curl -s "http://127.0.0.1:5001/api/stock/600519/score"
```

**预期结果**:
- ✅ 如果数据完整，`missingData` 为空或不存在
- ✅ `dataCompleteness.overall` > 0.7
- ✅ 无警告信息

## 总结

通过添加数据完整性检查，`stock.score` 工具从"黑盒评分"升级为"透明评估"：

- **Before**: 评分 23.0，不知原因
- **After**: 评分 23.0，数据完整度 26%，基本面数据全缺失，仅供参考

这大幅提升了工具的可用性和用户信任度。
