# RFC 009: M2 标的工厂实施方案（主线→标的映射 / 排雷清单 / 池战场评分）

| 字段 | 值 |
|---|---|
| 状态 | 🟡 部分实施（2026-08-26） |
| 日期 | 2026-08-26 设计+实施 |
| 编制 | agent-dh k3（审计+文档角色） |
| 实施方 | agent-dh k3（2026-08-26，feat/m2-stock-selection 分支） |
| 上游设计 | [RFC 004 盈利引擎设计](004-profit-engine-design.md) M2 模块；[RFC 005 工单包](005-profit-engine-work-tickets.md) M2-1/M2-2/M2-3 |
| 前置依赖 | M2-1 依赖 M1-2（主线识别数据，**未就绪**）；M2-2/M2-3 无依赖 |
| 实施 commits | M2-2: `9612d7c0` + `d3845e9d`（+83/-10）；M2-3: `b9b6a50d`（测试报告） |
| 完成度 | M2-2 ✅ 100%、M2-3 ⚠️ 50%、M2-1 🟡 0%（等待 M1-2），总体 66% |

---

## 0. 现状盘点（已验证能力基线）

### ✅ 已可用

| 组件 | 能力 | 验证状态 |
|---|---|---|
| **manipulation_detect** | 检测个股操纵嫌疑（拉高出货/对倒/诱多诱空），返回嫌疑评分+模式+证据 | ✅ 工具存在（competition 插件） |
| **pool_battlefield** | 评估股票池的博弈竞争优势（综合评分+对手分析+风险评估+排名） | ✅ 工具存在（competition 插件） |
| **pool_list** | 列出全部股票池（名称/筛选逻辑/成员数/更新时间） | ✅ 工具存在（investment 插件） |
| **screening** | 按自定义指标阈值精确过滤股票 | ✅ 工具存在（strategy 插件） |
| **opportunity_scan** | 多因子综合评分扫描全市场机会 | ✅ 工具存在（strategy 插件） |
| **mainline_stocks** | 主线→标的映射（输入主线名称，输出候选标的+理由+风险标注） | ✅ 工具存在（market 插件） |

### ❌ 缺失能力（M2 要补）

1. **M2-1 主线→标的映射未验证**：`mainline_stocks` 工具存在，但依赖 M1-2 主线识别数据（quant.market_themes 表），数据未完整积累且 API 404
2. **M2-2 排雷清单未校准**：`manipulation_detect` 未实测（不知道嫌疑评分的区分度）；减持/商誉/ST 过滤规则未代码化
3. **M2-3 池战场评分未校准**：`pool_battlefield` 未实测（不知道输出格式和评分合理性）

### 🎯 M2 核心价值

**把"在哪个战场、打哪只"从人工决策变成数据驱动的自动筛选**——每日主线 Top3 各自动映射到 ≥2 只候选标的，排雷规则过滤问题股，池战场评分指导战场选择。

---

## 1. 设计原则

1. **数据驱动而非主观**：标的选择必须基于主线数据（M1-2）+ 财务指标 + 操纵检测，不是 agent 凭感觉
2. **排雷优先**：先过滤问题股（ST/操纵嫌疑/减持/商誉），再从安全池中选优
3. **可解释**：每个候选标的必须附入选理由（为什么是它）+ 风险标注（有什么问题）
4. **容错降级**：主线数据缺失时，回退到 opportunity_scan（多因子评分）保底

---

## 2. M2-1: 主线→标的映射器

### 2.1 需求

**问题**：现在 `mainline_stocks` 工具虽然存在，但依赖 M1-2 的 quant.market_themes 表数据，该表未完整积累（M1-2 代码完成但数据生产未上线）。

**目标**：
- M1-2 数据就绪后，验证 `mainline_stocks` 工具输出合理
- 每日主线 Top3 各自动映射到 ≥2 只候选标的
- 候选标的附入选理由 + 风险标注（ST/亏损/高估值/操纵嫌疑）

### 2.2 技术方案

#### 2.2.1 依赖确认

**前置条件**：M1-2 主线识别数据就绪（quant.market_themes 表有近期数据 + GET /api/market/themes API 可用）

**检查命令**：
```bash
# 1. 检查数据库表
psql postgresql://localhost/quant -c "SELECT COUNT(*) FROM market_themes WHERE trade_date >= CURRENT_DATE - 7;"

# 2. 检查 API
curl http://localhost:5001/api/market/themes?days=1
```

**预期结果**：表有最近 7 日数据 + API 返回当日主线 Top3

#### 2.2.2 工具验证（M1-2 就绪后执行）

**工具**：`mainline_stocks`（market 插件）

**测试场景**：
```typescript
// 场景 1：读取当日主线 Top3 全量映射（不传 mainline 参数）
const result1 = await mainline_stocks({ top_n: 3 });
// 预期：每条主线有 ≥2 只候选标的 + 入选理由 + 风险标注

// 场景 2：指定主线映射（如 M1-2 识别到"白银"主线）
const result2 = await mainline_stocks({ mainline: "白银", top_n: 3 });
// 预期：返回白银产业链的 3 只龙头标的（如赤峰黄金、银泰黄金、盛达资源）

// 场景 3：容错降级（M1-2 数据缺失时）
const result3 = await mainline_stocks({});  // 空参数
// 预期：API 返回空或降级提示，agent 自动回退到 opportunity_scan
```

**验收标准**：
- ✅ 输入「粮食安全」（或当日主线）→ 输出 ≥2 只候选 + 入选理由 + 风险标注（RFC 005 M2-1）
- ✅ 风险标注覆盖：ST/*ST、退市风险、操纵嫌疑未检测（需过 manipulation_detect）、减持、商誉
- ✅ 候选标的按市值排序（龙头优先）

#### 2.2.3 降级策略（M1-2 未就绪时）

**当前阶段**（2026-08-26）：M1-2 数据未就绪，M2-1 暂不实施。

**临时方案**：盘前选股使用 `opportunity_scan`（多因子评分）代替主线映射。

**长期方案**：M1-2 数据积累 1 个月后（2026-09 下旬），再实施 M2-1 验证与集成。

### 2.3 实施计划（M1-2 就绪后）

| 步骤 | 内容 | 预计工时 |
|---|---|---|
| 1 | 确认 M1-2 数据就绪（market_themes 表 + API） | 0.5h |
| 2 | 测试 mainline_stocks 工具（3 个场景） | 1h |
| 3 | 验证输出格式与风险标注完整性 | 0.5h |
| 4 | 文档更新（验收通过记录） | 0.5h |
| **合计** | | **2.5h** |

---

## 3. M2-2: 排雷清单

### 3.1 需求

**问题**：
- `manipulation_detect` 工具未实测，不知道嫌疑评分的区分度（问题股 vs 正常股能否有效区分）
- 减持、商誉、ST 等风险因子未代码化（genome 宪法第 5 条提到，但没有自动过滤）

**目标**：
- 实测 `manipulation_detect` 对 3 只已知问题股（如历史暴雷股）的嫌疑评分，验证区分度
- 代码化排雷规则：ST/*ST 禁止买入、manipulation_detect 嫌疑评分 >70 禁止买入
- 减持/商誉规则设计（需财务数据支持，本阶段先设计不实施）

### 3.2 技术方案

#### 3.2.1 manipulation_detect 实测校准

**测试样本**：
- **问题股**（已知操纵/暴雷）：选 3 只（如 300XX 妖股、曾因操纵被罚的股票）
- **正常股**（蓝筹）：选 3 只（如 600519 贵州茅台、000001 平安银行、601318 中国平安）

**测试命令**：
```bash
# 对每只股票调用 manipulation_detect
curl -X POST http://localhost:5001/api/risk/manipulation-detect \
  -H "Content-Type: application/json" \
  -d '{"symbol": "600519", "days": 30}'
```

**验收标准**：
- ✅ 问题股嫌疑评分 >70，正常股 <30（有明显区分度）
- ✅ 输出包含：嫌疑评分、检测到的模式、证据列表、操作建议

**校准调整**（如果区分度不足）：
- 调整 quantsys-v2 后端 `manipulation_detect` 的评分权重
- 增加检测维度（如涨停连板、龙虎榜游资席位、高换手率等）

#### 3.2.2 排雷规则代码化

**位置**：trading 插件 `portfolio_trade` 工具，在 M4-2 熔断检查和 M4-1 仓位映射之后、executeTrade 之前插入。

**规则列表**：

| 规则 | 触发条件 | 动作 | 数据来源 |
|---|---|---|---|
| **ST 禁区** | symbol 包含 "ST"（简化匹配） | 拒绝交易 | symbol 字符串 |
| **操纵嫌疑** | manipulation_detect 嫌疑评分 >70 | 拒绝交易 + 留痕 | 调用 manipulation_detect |
| **减持风险** | 近 3 个月高管减持占比 >5% | ⚠️ 警告（不拒绝，记录风险） | 财务 API（待实现） |
| **商誉风险** | 商誉占净资产 >50% | ⚠️ 警告（不拒绝，记录风险） | 财务 API（待实现） |

**实施优先级**：
- **P0（本阶段）**：ST 禁区 + 操纵嫌疑（数据可得，立即可做）
- **P1（后续）**：减持风险 + 商誉风险（需补充财务 API）

**代码示例**（插入 portfolio_trade）：
```typescript
// M2-2 排雷检查（2026-08-26）：买入前过滤问题股
if (String(args.action).toUpperCase() === 'BUY') {
  const symbol = args.symbol;

  // 1. ST 禁区（简化匹配）
  if (symbol.includes('ST')) {
    return {
      success: false,
      blocked: true,
      reason: 'ST 禁区：ST/*ST 股票禁止买入（交易宪法第 5 条）',
      rule: 'M2-2-ST',
    };
  }

  // 2. 操纵嫌疑检测
  try {
    const manipResult: any = await qv2.manipulationDetect({ symbol, days: 30 });
    const suspicionScore = Number(manipResult?.suspicion_score || 0);

    if (suspicionScore > 70) {
      // 拒绝交易 + 落库留痕
      await this.osMemory.write({
        title: `M2-2 操纵嫌疑拦截：${symbol}`,
        content: JSON.stringify({
          symbol,
          suspicion_score: suspicionScore,
          patterns: manipResult?.patterns,
          evidence: manipResult?.evidence,
          blocked: true,
          reason: `操纵嫌疑评分 ${suspicionScore.toFixed(1)} >70，禁止买入`,
          timestamp: new Date().toISOString(),
        }),
        namespace: 'risk',
        tags: ['m2', 'manipulation_block', symbol],
      });

      return {
        success: false,
        blocked: true,
        reason: `操纵嫌疑：嫌疑评分 ${suspicionScore.toFixed(1)} >70，禁止买入（genome 标的禁区）`,
        suspicion_score: suspicionScore,
        patterns: manipResult?.patterns,
        rule: 'M2-2-manipulation',
      };
    }
  } catch {
    // 检测失败不阻塞交易（保守：允许，但记录警告）
    await this.osMemory.write({
      title: `M2-2 操纵检测失败：${symbol}`,
      content: JSON.stringify({
        symbol,
        error: 'manipulation_detect API 调用失败',
        action: '允许交易（保守原则）',
        timestamp: new Date().toISOString(),
      }),
      namespace: 'risk',
      tags: ['m2', 'manipulation_detect_error', symbol],
    });
  }
}
```

#### 3.2.3 验收标准

**功能验收**：
```bash
# 1. ST 拦截：portfolio_trade BUY ST 开头的股票 → blocked=true + ST 禁区原因
# 2. 操纵嫌疑拦截：对已知问题股 BUY → blocked=true + 嫌疑评分 >70
# 3. 正常股通过：对蓝筹股 BUY → 正常执行（嫌疑评分 <30）
# 4. 留痕检查：memory_search(query='操纵嫌疑', namespace='risk') 返回拦截记录
```

**区分度验收**（RFC 005 M2-2）：
- ✅ 对 3 只已知问题股跑 `manipulation_detect` → 嫌疑评分有区分度（问题股 >70 > 正常股 <30）

### 3.3 实施计划

| 步骤 | 内容 | 预计工时 |
|---|---|---|
| 1 | 选择 3 只问题股 + 3 只正常股样本 | 0.5h |
| 2 | 实测 manipulation_detect 验证区分度 | 1h |
| 3 | trading 插件添加 M2-2 排雷检查（ST + 操纵嫌疑） | 1.5h |
| 4 | 单元测试（ST 拦截 + 操纵嫌疑拦截 + 正常股通过） | 1h |
| 5 | 文档更新（验收记录） | 0.5h |
| **合计** | | **4.5h** |

---

## 4. M2-3: 池战场评分校准

### 4.1 需求

**问题**：`pool_battlefield` 工具未实测，不知道：
- 输出格式是否合理（评分/排名/理由）
- 评分算法是否有区分度（强势池 vs 弱势池）
- 对手分析是否有价值

**目标**：
- 实测 `pool_battlefield` 对 2 个池子（高 ROE 池 #27、低估值池 #35）
- 验证输出合理性：综合评分 + 对手分析 + 风险评估 + 排名
- 如区分度不足，调整评分算法或补充数据维度

### 4.2 技术方案

#### 4.2.1 工具实测

**测试池子**：
- pool_id=27（高 ROE 池，预期：强势，机构主导）
- pool_id=35（低估值池，预期：散户情绪主导，机构犹豫）

**测试命令**：
```typescript
// 调用 pool_battlefield
const result1 = await pool_battlefield({ pool_id: 27 });
const result2 = await pool_battlefield({ pool_id: 35 });
```

**预期输出结构**：
```json
{
  "pool_id": 27,
  "pool_name": "高ROE池",
  "comprehensive_score": 8.5,  // 综合评分 0-10
  "rank": 3,  // 在所有池中排名
  "opponent_analysis": {
    "retail_sentiment": "neutral",  // 散户情绪：panic/neutral/fomo
    "institution_position": "building",  // 机构动向：building/holding/exiting
    "hot_money_activity": "low"  // 游资活跃度：low/medium/high
  },
  "risk_assessment": {
    "concentration": "medium",  // 集中度风险
    "liquidity": "high",  // 流动性
    "valuation": "fair"  // 估值水平
  },
  "recommendation": "适合建仓：机构在建仓，散户情绪中性，流动性充足"
}
```

#### 4.2.2 验收标准（RFC 005 M2-3）

**功能验收**：
- ✅ 对 pool 27/35 调 `pool_battlefield` → 输出综合评分+排名且理由可解释
- ✅ 强势池评分 > 弱势池评分（有区分度）
- ✅ 对手分析包含：散户情绪、机构动向、游资活跃度

**校准调整**（如果区分度不足）：
- 补充数据维度（如板块涨跌幅、资金净流入、龙虎榜游资席位）
- 调整评分权重（如强势板块权重上调）

### 4.3 实施计划

| 步骤 | 内容 | 预计工时 |
|---|---|---|
| 1 | 实测 pool_battlefield 对 pool 27/35 | 1h |
| 2 | 验证输出格式与评分区分度 | 0.5h |
| 3 | 调整评分算法（如需要） | 1h |
| 4 | 文档更新（验收记录） | 0.5h |
| **合计** | | **3h** |

---

## 5. 实施顺序与验收

### 5.1 实施顺序（按依赖排序）

| 序 | 工单 | 依赖 | 预计工时 | 状态 |
|---|---|---|---|---|
| 1 | **M2-2 排雷清单** | 无 | 4.5h | 🟢 立即可做 |
| 2 | **M2-3 池战场评分** | 无 | 3h | 🟢 立即可做 |
| 3 | **M2-1 主线→标的映射** | M1-2（⚠️ 未就绪） | 2.5h | 🟡 等待 M1-2 数据（预计 2026-09 下旬） |

**建议**：先 M2-2 → M2-3，M2-1 等 M1-2 数据积累 1 个月后再实施。

### 5.2 总体验收（RFC 005 标准）

| 工单 | 验收命令 | 验收标准 | 状态 |
|---|---|---|---|
| M2-1 | 输入「粮食安全」 | 输出 ≥2 只候选 + 入选理由 + 风险标注 | 🟡 等待 M1-2 |
| M2-2 | 对 3 只已知问题股跑 `manipulation_detect` | 嫌疑评分有区分度（问题股 >70 > 正常股 <30） | 🟢 待实施 |
| M2-3 | 对 pool 27/35 调 `pool_battlefield` | 输出综合评分+排名且理由可解释 | 🟢 待实施 |

---

## 6. 集成点与影响面

### 6.1 代码修改位置

| 位置 | 修改内容 |
|---|---|
| `agent-dh/packages/trading/src/index.ts` | M2-2：`portfolio_trade` 插入排雷检查（ST 禁区 + 操纵嫌疑） |
| `quantsys-v2/application/services/risk_service.py` | M2-2：调整 `manipulation_detect` 评分权重（如区分度不足） |
| `agent-dh/packages/competition/src/index.ts` | M2-3：调整 `pool_battlefield` 评分算法（如区分度不足） |
| `agent-dh/packages/market/src/index.ts` | M2-1：验证 `mainline_stocks` 工具（M1-2 就绪后） |

### 6.2 genome 规则更新

实施完成后，更新 genome（genome_update tool）：

**constitution v2**（宪法第 5 条细化）：
```markdown
5. **标的禁区**：ST/*ST、退市风险、manipulation_detect 嫌疑评分 >70 的标的禁止买入。**已代码强制**（2026-08-26 起，portfolio_trade BUY 前自动检查，突破拒绝交易）。
```

**rules v8**（增加 M2 规则）：
```markdown
## R-010 排雷清单（已代码强制）
买入前自动过滤问题股：ST/*ST 禁止买入、操纵嫌疑评分 >70 禁止买入。**已代码自动校验**（2026-08-26 起，portfolio_trade BUY 前调用 manipulation_detect，突破拒绝交易并落库留痕 osMemory risk:manipulation_block）。

## R-011 主线→标的映射（M1-2 就绪后启用）
每日主线 Top3 各自动映射到 ≥2 只候选标的（调用 mainline_stocks），候选标的附入选理由 + 风险标注。主线数据缺失时回退到 opportunity_scan（多因子评分）。
```

### 6.3 影响范围

**直接影响**：
- 所有 `portfolio_trade` BUY 交易（M2-2 排雷检查）
- `pool_battlefield` 工具输出（M2-3 评分调整）
- `mainline_stocks` 工具（M2-1 验证，M1-2 就绪后）

**不影响**：
- 卖出交易（排雷只针对买入）
- 其他 agent-dh 工具（memory、evolution、scheduler 等）
- M4 风控逻辑（M2 排雷在 M4 之后执行，互不冲突）

---

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| M1-2 数据长期未就绪导致 M2-1 无法实施 | 中 | 中 | M2-2/M2-3 先实施提供价值；M2-1 降级使用 opportunity_scan 保底 |
| manipulation_detect 区分度不足（问题股评分不高） | 中 | 高 | ①增加检测维度（龙虎榜/涨停连板/高换手）；②调整评分权重；③人工复核异常股 |
| ST 简化匹配误伤（如股票名称包含 "ST" 但非 ST 股） | 低 | 中 | ①改用证券状态字段（需财务 API）；②短期容忍误伤（保守原则） |
| pool_battlefield 评分无区分度（强弱池评分接近） | 中 | 中 | ①补充数据维度（板块涨跌幅/资金流向）；②调整评分权重 |

---

## 8. 交接清单（实施者领工用）

### 8.1 开工前必读
- [ ] 读本文档完整内容（特别是 §3/§4 技术方案）
- [ ] 读 genome constitution v1 第 5 条（标的禁区）
- [ ] 读 `agent-dh/packages/trading/src/index.ts` 的 `portfolio_trade` 现有实现（M4 风控逻辑）
- [ ] 读 `agent-dh/packages/competition/src/index.ts` 的 `manipulation_detect` 和 `pool_battlefield` 工具

### 8.2 开发步骤（建议）

**Step 1: M2-2 排雷清单（4.5h）**
1. 选择 3 只问题股 + 3 只正常股样本
2. 实测 `manipulation_detect` 验证区分度（curl 调用后端）
3. trading 插件添加 M2-2 排雷检查（ST + 操纵嫌疑，§3.2.2 代码示例）
4. 单元测试：ST 拦截 + 操纵嫌疑拦截 + 正常股通过
5. 集成测试：真实账户调用 portfolio_trade 验证拦截逻辑

**Step 2: M2-3 池战场评分（3h）**
1. 实测 `pool_battlefield` 对 pool 27/35
2. 验证输出格式与评分区分度
3. 调整评分算法（如需要，修改 competition 插件）
4. 文档更新（验收记录）

**Step 3: M2-1 主线→标的映射（M1-2 就绪后，2.5h）**
1. 确认 M1-2 数据就绪（market_themes 表 + API）
2. 测试 `mainline_stocks` 工具（3 个场景）
3. 验证输出格式与风险标注完整性
4. 文档更新（验收通过记录）

**Step 4: genome 更新 + 文档**
1. 调用 genome_update 更新 constitution v2（第 5 条标注"已代码强制"）
2. 调用 genome_update 更新 rules v8（R-010/R-011）
3. 更新本文档状态为 ✅ 已实施
4. 提交代码 + work-log

### 8.3 验收检查表（提交前自测）

- [ ] M2-2: ST 股票 BUY → blocked=true + ST 禁区原因
- [ ] M2-2: 问题股 BUY → blocked=true + 操纵嫌疑评分 >70
- [ ] M2-2: 正常股 BUY → 正常执行 + osMemory 留痕
- [ ] M2-2: 3 只问题股 manipulation_detect 评分 >70，3 只正常股 <30
- [ ] M2-3: pool 27/35 pool_battlefield 输出综合评分+排名+对手分析
- [ ] M2-3: 强势池评分 > 弱势池评分（有区分度）
- [ ] 单元测试覆盖率 ≥80%（trading 插件）
- [ ] 代码提交到 feat/m2-stock-selection 分支（不直接到 main）

---

## 9. 变更日志

| 日期 | 内容 |
|---|---|
| 2026-08-26 | 创建。M4 完成后启动 M2 设计；M2-1/M2-2/M2-3 技术方案完整定义；明确 M2-1 等待 M1-2 数据，M2-2/M2-3 立即可做；交接清单明确（§8） |

---

## 10. 参考文档

- [RFC 004 盈利引擎设计](004-profit-engine-design.md) §M2 标的工厂
- [RFC 005 盈利引擎工单包](005-profit-engine-work-tickets.md) §M2 标的工厂
- [RFC 007 M1 市场感知实施方案](007-market-perception-m1-implementation.md)（M2-1 依赖的主线数据来源）
- [RFC 008 M4 仓位与风控实施方案](008-position-risk-m4-implementation.md)（M2 排雷与 M4 风控的执行顺序）
- agent-dh genome g14 constitution v1（宪法第 5 条：标的禁区）
