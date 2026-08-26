# M2-3 池战场评分实测报告（2026-08-26）

## 测试样本

| Pool ID | 名称 | 预期特征 |
|---|---|---|
| 27 | 高 ROE 池 | 强势，机构主导 |
| 35 | 低估值池 | 散户情绪主导，机构犹豫 |

## 实测结果

### Pool 27（高 ROE 池）
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

### Pool 35（低估值池）
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

### 1. 评分区分度不足
- Pool 27: 64.2 vs Pool 35: 62.3（差异仅 1.9 分）
- 预期：强势池应显著高于弱势池（差距 >10 分）

### 2. 数据质量降级
- `data_quality: "degraded"` 标记数据不完整
- 根本原因：`fund_flow_repo=None`（资金流数据源未实现）

### 3. 对手分析粗糙
- 所有维度都是 "medium"，无区分度
- 依赖资金流数据计算散户/机构行为

### 4. 优劣势列表为空
- `advantages: []` 和 `disadvantages: []`
- 缺乏可解释性

## 根本原因

**评分算法依赖资金流数据**（battlefield_assessor.py L264-302）：
- 散户资金流（retail_flow）：< -1000万 → +20分
- 机构资金流（institution_flow）：> +1000万 → +30分
- 力量差距（散户抛售+机构建仓）：+10分

但路由初始化时 `fund_flow_repo=None`（intelligence.py L114），导致：
- 资金流数据全部缺失
- 所有股票都用基础分 50
- 池子评分收敛到 50 附近（实测 62-64 可能加了其他维度的小权重）

## 验收结论

**RFC 005 M2-3 验收标准**：
> 对 pool 27/35 调 `pool_battlefield` → 输出综合评分+排名且理由可解释

**验收结果**：⚠️ 部分通过
- ✅ 工具可调用，输出结构合理
- ⚠️ 评分区分度不足（<2 分差异）
- ⚠️ 理由不可解释（优劣势列表为空）
- ⚠️ 数据质量降级

## 解决方案

### 短期（P0）：标注限制
- M2-3 标记为"部分完成"
- 文档中明确说明：评分功能可用但区分度弱（依赖资金流数据）
- agent 使用时需理解评分差异 <5 分时不具备决策价值

### 中期（P1）：补充资金流数据源
- 实现 fund_flow_repo（需要龙虎榜/大单统计/北向资金等数据源）
- 重新校准评分权重
- 补充优劣势分析逻辑

### 长期（P2）：多维度数据融合
- 增加板块涨跌幅、成交量、技术指标等维度
- 机器学习评分模型（训练历史数据预测池子未来收益）

## 建议

**不阻塞 M2 实施**：
1. pool_battlefield 工具本身没有问题，是数据基础设施限制
2. 当前评分虽然区分度弱，但至少能提供基础参考（60+ vs 40-）
3. 数据源补充是独立工单（基础设施线），不应阻塞业务线
4. M2-3 标记为"部分完成"，等待 P1 数据源就绪后重新校准

**优先级建议**：M3 信号择时（挣钱线核心）> 资金流数据源补充（基础设施）

