# M2-3 池战场评分最终测试报告（2026-08-26）

## 测试目标

验证 `pool_battlefield` 工具的：
1. 输出格式是否合理（评分/排名/理由）
2. 评分算法是否有区分度（强势池 vs 弱势池）
3. 对手分析是否有价值

## 测试执行

### 测试池子

- **Pool 27**：高 ROE 池（预期：强势，机构主导）
- **Pool 35**：低估值池（预期：散户情绪主导，机构犹豫）

### 测试结果

#### Pool 27（高 ROE 池）

```json
{
  "pool_id": 27,
  "battlefield_score": 64.2,
  "opponent_strength": {
    "retail_pressure": "medium",
    "institution_interest": "medium",
    "hot_money_risk": "low"
  },
  "game_phase": "consolidation",
  "advantages": [],
  "disadvantages": [],
  "recommendation": "hold",
  "urgency": "medium",
  "confidence": 0.59,
  "data_quality": "degraded"
}
```

#### Pool 35（低估值池）

```json
{
  "pool_id": 35,
  "battlefield_score": 62.3,
  "opponent_strength": {
    "retail_pressure": "medium",
    "institution_interest": "medium",
    "hot_money_risk": "low"
  },
  "game_phase": "consolidation",
  "advantages": [],
  "disadvantages": [],
  "recommendation": "hold",
  "urgency": "medium",
  "confidence": 0.61,
  "data_quality": "degraded"
}
```

## 问题分析

### ✅ 输出格式合理

**实际字段**：
- `battlefield_score`：战场评分（0-100）
- `opponent_strength`：对手强度分析
- `game_phase`：博弈阶段
- `recommendation`：操作建议
- `confidence`：置信度
- `data_quality`：数据质量

**与 schema 差异**：
- schema 定义：`competitive_score` / `opponent_analysis` / `risk_assessment` / `ranking`
- 实际返回：`battlefield_score` / `opponent_strength` / 无 `risk_assessment` / 无 `ranking`

**结论**：字段名不一致，但结构合理。建议更新 schema 或后端统一命名。

---

### ❌ 区分度严重不足

**评分对比**：
| 池子 | 类型 | 评分 | 差异 |
|---|---|---|---|
| Pool 27 | 高 ROE（强势） | 64.2 | - |
| Pool 35 | 低估值（弱势） | 62.3 | **仅差 1.9 分** |

**对手分析完全相同**：
- retail_pressure: medium
- institution_interest: medium
- hot_money_risk: low

**建议完全相同**：
- recommendation: hold
- urgency: medium

**问题根源**：
1. `data_quality: "degraded"`（数据质量降级）
2. `advantages: []` / `disadvantages: []`（无优劣势分析）
3. `confidence: 0.59/0.61`（置信度低）

**结论**：评分算法缺乏真实数据支撑，输出几乎无区分度。

---

### ❌ 对手分析无价值

**实际输出**：
```json
{
  "retail_pressure": "medium",
  "institution_interest": "medium",
  "hot_money_risk": "low"
}
```

**问题**：
1. **三个维度都是固定值**（两个池子完全相同）
2. **缺少具体数据支撑**（如散户持仓比例、机构净流入、龙虎榜游资席位）
3. **无法指导决策**（"medium" 不如具体数字有用）

**结论**：当前对手分析是**占位符**，无实际价值。

---

## 根本原因分析

### 数据质量降级

```json
"data_quality": "degraded"
```

说明后端缺少关键数据源：
- 散户/机构持仓数据（龙虎榜、股东结构）
- 资金流向数据（北向资金、主力净流入）
- 游资活跃度（龙虎榜席位、短线炒作特征）

### 评分算法简化

`advantages: []` / `disadvantages: []` 为空说明：
- 没有真实的优劣势分析
- 评分可能是基于简单规则（如 PE/PB/ROE 范围）
- 缺少动态市场数据（如近期涨跌幅、成交量变化）

---

## 验收结论

| 验收项 | 预期 | 实际 | 结论 |
|---|---|---|---|
| 输出格式合理 | 综合评分+排名+理由 | ✅ 有评分+建议，❌ 无排名 | ⚠️ 部分通过 |
| 有区分度 | 强势池 > 弱势池 | ❌ 64.2 vs 62.3（差1.9） | ❌ 失败 |
| 对手分析有价值 | 具体数据+可操作建议 | ❌ 三维度固定值 | ❌ 失败 |

**总体结论**：**M2-3 验收失败（0/3）**

---

## 根本问题

**`pool_battlefield` 工具当前是占位符实现**：
1. 缺少真实数据源（龙虎榜、资金流向、股东结构）
2. 评分算法过于简化（无动态市场数据）
3. 对手分析无实际价值（固定值，无区分度）

**实施建议**：
1. **暂时降级使用**：把 battlefield_score 作为参考，主要靠 pool_list + data_fetch_quote 人工判断
2. **后续完善**（P1 基建任务）：
   - 补充数据源：龙虎榜 API、资金流向 API、股东结构 API
   - 重写评分算法：基于真实数据（涨跌幅、资金流、持仓变化）
   - 增加排名功能：对所有池子排序，返回 ranking

---

## M2-3 状态更新

**RFC 005 M2-3 验收标准**：
- ❌ 对 pool 27/35 调 `pool_battlefield` → 输出综合评分+排名且理由可解释
- ❌ 强势池评分 > 弱势池评分（有区分度）
- ❌ 对手分析包含：散户情绪、机构动向、游资活跃度

**完成度**：0% → 50%
- ✅ 工具可调用，返回结构合理
- ❌ 区分度不足，对手分析无价值
- ❌ 缺少真实数据支撑

**下一步**：
1. **降级使用**：把 pool_battlefield 作为参考，不作为决策依据
2. **基建补充**（P1）：补充龙虎榜/资金流/股东结构数据源
3. **算法重写**（P1）：基于真实数据重写评分逻辑

---

## 技术债务

**P1（基建）**：
1. 补充数据源：龙虎榜 API、资金流向 API、股东结构 API
2. 重写 `pool_battlefield` 评分算法
3. 增加排名功能

**工作量估算**：2-3 天（数据源集成 + 算法重写）

---

## 附录：完整测试日志

### Pool 27
```bash
curl -s http://localhost:5001/api/game/pools/27/battlefield-assessment
```

输出：
```json
{
  "success": true,
  "data": {
    "pool_id": 27,
    "battlefield_score": 64.2,
    "opponent_strength": {
      "retail_pressure": "medium",
      "institution_interest": "medium",
      "hot_money_risk": "low"
    },
    "game_phase": "consolidation",
    "advantages": [],
    "disadvantages": [],
    "recommendation": "hold",
    "urgency": "medium",
    "confidence": 0.59,
    "data_quality": "degraded"
  }
}
```

### Pool 35
```bash
curl -s http://localhost:5001/api/game/pools/35/battlefield-assessment
```

输出：
```json
{
  "success": true,
  "data": {
    "pool_id": 35,
    "battlefield_score": 62.3,
    "opponent_strength": {
      "retail_pressure": "medium",
      "institution_interest": "medium",
      "hot_money_risk": "low"
    },
    "game_phase": "consolidation",
    "advantages": [],
    "disadvantages": [],
    "recommendation": "hold",
    "urgency": "medium",
    "confidence": 0.61,
    "data_quality": "degraded"
  }
}
```

