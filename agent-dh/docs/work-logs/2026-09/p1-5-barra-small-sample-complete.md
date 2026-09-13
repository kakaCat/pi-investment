---
id: wl-2026-09-p1-5-barra-small-sample-complete
title: P1-5 Barra 小样本路径完成报告
type: worklog
status: archived
updated: 2026-09-12
owners: [agent-dh]
tags: [worklog, 2026-09]
---

# P1-5 Barra 小样本路径完成报告

**任务编号**: P1-5  
**任务名称**: Barra 小样本路径  
**完成时间**: 2026-09-12 12:41:01  
**实施人员**: Claude (Agent-DH)  
**预估工作量**: 4-5h  
**实际工作量**: ~3h  

---

## 一、任务目标

让 2-3 只持仓也能做 Barra 风险分解（降级但可用）

### 问题背景

- **当前限制**: Barra 横截面回归需要 ≥10 只股票（因子数+5），持仓不足时直接报错
- **实际需求**: 小账户或集中持仓场景（2-3 只股票）也需要风险分解能力
- **用户痛点**: `risk_barra_decomposition` 在小持仓时完全不可用

---

## 二、解决方案

### 技术方案选择

采用**单因子映射法（市值因子）**作为小样本路径：

| 方案 | 适用场景 | 优点 | 缺点 | 选择 |
|------|---------|------|------|------|
| 单因子映射 | 2-9 只股票 | 实现简单、统计稳定、结果可解释 | 信息有限（只有市值维度） | ✅ 采用 |
| 收缩协方差 | 5-8 只股票 | 保留多因子信息、统计更稳健 | 需要 sklearn、计算复杂 | ❌ 未采用 |

### 实现策略

1. **自动降级**: `calculate()` 方法检测股票数，< 10 只时自动调用小样本路径
2. **降级标记**: 返回结果中添加 `degraded=true`、`method='single_factor_size'`、`warning` 字段
3. **保持兼容**: 完整模式（≥10 只股票）逻辑不变，降级模式作为补充路径

---

## 三、实施内容

### 3.1 后端实现（Python）

#### 文件 1: `quantsys-v2/domain/factors/models/barra.py`

**新增方法**: `calculate_small_sample()`

```python
def calculate_small_sample(self,
                          returns: pd.DataFrame,
                          market_caps: Optional[pd.Series] = None,
                          portfolio_weights: Optional[pd.Series] = None) -> Dict[str, Any]:
    """
    Small-sample Barra risk decomposition (2-9 stocks).
    
    Uses simplified single-factor (size) model when insufficient stocks
    for full multi-factor cross-sectional regression.
    """
```

**核心算法**:
- 使用市值因子（log market cap 标准化）作为唯一因子
- 时间序列回归: `r_i,t = β_i * f_t + ε_i,t`
- 因子方差从因子收益序列估计
- 特异方差从残差计算
- 最小要求: ≥2 只股票，≥30 期观测

**修改逻辑**: `calculate()` 方法

```python
# 检测股票数，自动降级
n_stocks = len(common_stocks)
n_factors = len(factor_exposures.columns)
min_stocks_for_full = n_factors + 5

if 2 <= n_stocks < min_stocks_for_full:
    logger.warning(f"Barra: {n_stocks} stocks < {min_stocks_for_full}, 降级到单因子小样本模式")
    return self.calculate_small_sample(...)
```

#### 文件 2: `quantsys-v2/adapters/inbound/fastapi_app/routes/factor_models_async.py`

**修改**: `/api/factor-models/barra/calculate` 路由

添加返回字段:
```python
'degraded': bool(value.get('degraded', False)),
'method': value.get('method', 'full'),
'warning': value.get('warning'),
```

### 3.2 前端工具更新（TypeScript）

#### 文件 1: `agent-dh/packages/risk/src/tools/BarraDecompositionTool/prompt.ts`

**更新接口**:
```typescript
export interface BarraDecompositionResult {
  // ... 现有字段
  degraded?: boolean;      // 是否为降级模式
  method?: string;         // 计算方法
  warning?: string;        // 降级警告
}
```

**更新 description**:
> 完整模式需 ≥10 只股票；2-9 只时自动降级到单因子（市值）小样本模式（degraded=true）

**更新 notes**:
> 【P1-5 小样本支持】≥10 只股票=完整多因子模式；2-9 只=自动降级单因子（市值）模式（degraded=true，精度降低但可用）

#### 文件 2: `agent-dh/packages/risk/src/tools/BarraDecompositionTool/BarraDecompositionTool.ts`

**更新 wrap 方法**:
```typescript
protected wrap(result: BarraDecompositionResult, _context: ToolContext) {
  if (result.degraded) {
    return {
      success: true,
      data: result,
      message: result.warning || '小样本模式：仅使用市值单因子，精度降低但可用',
    };
  }
  return { success: true, data: result };
}
```

---

## 四、测试验证

### 测试脚本

创建: `quantsys-v2/tests/test_barra_small_sample.py`

### 测试用例

| 测试用例 | 股票数 | 预期结果 | 实际结果 |
|---------|-------|---------|---------|
| test_2_stocks | 2 | 降级模式，n_factors=1 | ✅ PASS |
| test_3_stocks | 3 | 降级模式，degraded=true | ✅ PASS |
| test_auto_degrade | 3 | 自动降级 | ✅ PASS |
| test_10_stocks | 10 | 完整模式，n_factors=5 | ✅ PASS |

### 测试输出示例

```
测试 1: 2 只股票（小样本模式）
✓ 计算成功
  - 股票数: 2
  - 因子数: 1
  - 总风险: 0.0096
  - 因子风险: 0.0000
  - 特异风险: 0.0096
  - 降级标记: True
  - 方法: single_factor_size
  - 警告: 小样本模式（2只股票）：仅使用市值单因子，精度降低
✓ 所有断言通过

测试 4: 10 只股票（完整多因子模式）
✓ 计算成功
  - 股票数: 10
  - 因子数: 5
  - 总风险: 0.0044
  - 降级标记: False
✓ 所有断言通过

============================================================
✓ 所有测试通过！
```

---

## 五、使用示例

### 场景 1: 2-3 只持仓的小账户

**调用**:
```typescript
const result = await tools.risk_barra_decomposition({
  symbols: ['600519', '000858'],
  start_date: '2024-01-01',
  end_date: '2024-12-31'
});
```

**返回**:
```json
{
  "success": true,
  "data": {
    "total_risk": 0.0096,
    "factor_risk": 0.0000,
    "specific_risk": 0.0096,
    "n_stocks": 2,
    "n_factors": 1,
    "degraded": true,
    "method": "single_factor_size",
    "warning": "小样本模式（2只股票）：仅使用市值单因子，精度降低"
  },
  "message": "小样本模式：仅使用市值单因子，精度降低但可用"
}
```

### 场景 2: 10 只以上持仓（完整模式）

**调用**:
```typescript
const result = await tools.risk_barra_decomposition({
  symbols: ['600519', '000858', '601318', ...], // 10+ stocks
});
```

**返回**:
```json
{
  "success": true,
  "data": {
    "total_risk": 0.0044,
    "factor_risk": 0.0028,
    "specific_risk": 0.0034,
    "n_stocks": 10,
    "n_factors": 5,
    "degraded": false,
    "factor_covariance": {...},
    "portfolio_exposures": {...}
  }
}
```

---

## 六、技术亮点

### 6.1 自动降级设计

- **透明切换**: 用户无需手动选择模式，系统根据股票数自动降级
- **明确标识**: `degraded` 字段让用户清楚知道当前使用的模式
- **保持兼容**: 完整模式行为不变，降级是增量特性

### 6.2 统计稳健性

- **单因子回归**: 市值因子 + 时间序列回归，比横截面回归对小样本更稳定
- **最小样本保护**: 硬性要求 ≥2 只股票、≥30 期观测，避免统计不可靠
- **明确警告**: 用户知道精度降低，不会误以为结果与完整模式等价

### 6.3 代码质量

- **测试覆盖**: 4 个测试用例覆盖 2/3/10 只股票场景 + 自动降级逻辑
- **类型安全**: TypeScript 接口完整定义所有字段
- **错误处理**: 样本不足时给出可操作的错误提示

---

## 七、限制与改进方向

### 当前限制

1. **信息维度**: 小样本模式只使用市值单因子，无法分析行业、风格等维度
2. **精度降低**: 单因子模型比完整多因子模型精度低，适合粗略估计而非精确分析
3. **边界场景**: 1 只股票无法计算（需要至少 2 只）

### 未来改进

#### P1-5.1: 收缩协方差法（中等优先级）

- **适用场景**: 5-8 只股票
- **优势**: 保留多因子信息，比单因子精度更高
- **技术**: Ledoit-Wolf 收缩估计
- **工作量**: ~2-3h（需引入 sklearn）

#### P1-5.2: 动态因子选择（低优先级）

- **适用场景**: 根据股票数动态选择因子数量
- **示例**: 5 只股票用 2 因子（市值+估值），8 只股票用 3 因子
- **工作量**: ~1-2h

---

## 八、变更文件清单

### 后端（Python）

- ✅ `quantsys-v2/domain/factors/models/barra.py`（+160 行）
  - 新增 `calculate_small_sample()` 方法
  - 修改 `calculate()` 自动降级逻辑

- ✅ `quantsys-v2/adapters/inbound/fastapi_app/routes/factor_models_async.py`（+3 行）
  - 添加 `degraded`/`method`/`warning` 返回字段

### 前端（TypeScript）

- ✅ `agent-dh/packages/risk/src/tools/BarraDecompositionTool/prompt.ts`（+10 行）
  - 更新 `BarraDecompositionResult` 接口
  - 更新 description 和 notes
  - 更新 output schema

- ✅ `agent-dh/packages/risk/src/tools/BarraDecompositionTool/BarraDecompositionTool.ts`（+8 行）
  - 更新 `wrap()` 方法添加降级警告

### 测试

- ✅ `quantsys-v2/tests/test_barra_small_sample.py`（新建，+300 行）
  - 4 个测试用例，全部通过

**总计**: 5 个文件，~481 行代码

---

## 九、部署检查清单

### 后端部署

- [x] Python 代码已修改
- [x] 测试通过（4/4）
- [ ] quantsys-v2 服务重启（`cd quantsys-v2 && python start_all.py`）
- [ ] API 端点验证（`curl -X POST http://localhost:5001/api/factor-models/barra/calculate`）

### 前端部署

- [x] TypeScript 代码已修改
- [ ] 构建（`cd agent-dh && pnpm build`，可选）
- [ ] DSH profile 重启（`launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh`）
- [ ] 工具可用性验证（在 DSH Web UI 调用 `risk_barra_decomposition`）

### 验收测试

使用 DSH Web UI 测试：

```typescript
// 测试 1: 2 只股票（应降级）
await tools.risk_barra_decomposition({
  symbols: ['600519', '000858']
});
// 预期: degraded=true, n_factors=1, message 包含"小样本模式"

// 测试 2: 10 只股票（完整模式）
await tools.risk_barra_decomposition({
  symbols: ['600519', '000858', '601318', '000001', '600036', 
            '601398', '600028', '601288', '600900', '000333']
});
// 预期: degraded=false, n_factors=5
```

---

## 十、总结

### 成果

✅ **核心目标达成**: 2-3 只持仓现在可以做 Barra 风险分解  
✅ **自动降级**: 用户无需关心模式切换，系统智能处理  
✅ **明确标识**: `degraded` 标记让用户清楚精度权衡  
✅ **测试充分**: 4 个测试用例全部通过  
✅ **保持兼容**: 完整模式不受影响  

### 价值

- **覆盖长尾场景**: 小账户/集中持仓用户不再被拒之门外
- **降低使用门槛**: 从"至少 10 只股票"降低到"至少 2 只股票"
- **用户体验**: 工具从"完全不可用"变为"降级可用"，大幅提升可用性

### 工作量

- **预估**: 4-5h
- **实际**: ~3h
- **效率**: 提前完成，测试覆盖充分

---

## 附录

### A. 数学原理

#### 完整 Barra 模型（≥10 只股票）

$$
r_i = \sum_{k=1}^{K} \beta_{ik} f_k + \epsilon_i
$$

其中:
- `r_i`: 股票 i 的收益率
- `β_ik`: 股票 i 对因子 k 的暴露度
- `f_k`: 因子 k 的收益率（横截面回归估计）
- `ε_i`: 特异收益（残差）

组合风险:
$$
\sigma_p^2 = X^T F X + w^T \Delta w
$$

其中:
- `X`: 组合因子暴露向量
- `F`: 因子协方差矩阵
- `w`: 持仓权重向量
- `Δ`: 特异风险对角矩阵

#### 小样本模式（2-9 只股票）

简化为单因子模型:
$$
r_i = \beta_i f_{size} + \epsilon_i
$$

其中:
- `f_size`: 市值因子收益（横截面回归估计）
- `β_i`: 股票 i 的市值暴露度（log market cap 标准化）

组合风险:
$$
\sigma_p^2 = \beta_p^2 \sigma_f^2 + \sum_i w_i^2 \sigma_{\epsilon_i}^2
$$

### B. 相关文档

- RFC: 无（P1 系列不要求 RFC）
- 设计文档: 本报告即设计文档
- API 文档: `quantsys-v2/docs/api/factor_models.md`（需更新）
- 用户指南: `agent-dh/docs/tools/risk.md`（需更新）

---

**报告完成时间**: 2026-09-12 12:41:01  
**状态**: ✅ 实施完成，待部署验收
