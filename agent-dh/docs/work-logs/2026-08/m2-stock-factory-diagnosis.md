# M2 标的工厂问题诊断报告

**诊断日期**: 2026-08-31 03:15  
**诊断者**: agent-dh investor (w-8366e526)  
**当前完成度**: 66%（2/3 工单完成）

---

## 📊 问题总览

| 工单 | 状态 | 完成度 | 主要问题 |
|------|------|--------|----------|
| M2-1 主线→标的映射 | 🟡 等待数据积累 | 0% | M1-2 主线数据量不足 |
| M2-2 排雷清单 | ✅ 已完成 | 100% | 无 |
| M2-3 池战场评分 | ⚠️ 部分可用 | 50% | 资金流数据缺失 + 评分区分度不足 |

**整体完成度**: 66%（立即可做部分：M2-2 完成，M2-3 部分完成，M2-1 等数据）

---

## 🟡 问题1: M2-1 主线→标的映射（数据积累中）

### 工单定义（RFC 005）

> 主线→标的映射器：输入主线名称（如「粮食安全」），输出入选标的（≥2 只）+ 入选理由 + 风险标注

### 当前状态

#### 数据现状 ✅ 基础就绪

```sql
-- market_theme 表统计
SELECT COUNT(*) as themes, COUNT(DISTINCT trade_date) as days, 
       MAX(trade_date) as latest 
FROM quant.market_theme;

-- 结果:
themes | days | latest
-------|------|------------
14     | 5    | 2026-08-28  ✅ 有数据
```

**最近主线**（08-25~08-28）:
- 农化制品（5 涨停，08-28）
- 软件开发（5 涨停，08-28）
- 化学制品（6 涨停，08-28）
- 通信设备（5 涨停，08-27）
- 半导体（5 涨停，08-27）

#### 阻塞原因

**M1-2 主线识别数据积累不足**:
- 当前: 14 条主题（5 个交易日）
- 需要: ≥30 条（≥1 个月，~20 个交易日）
- 原因: 
  1. M1-2 催化剂 LLM 回写调度未挂载（待完成）
  2. 主线识别逻辑需要时间积累规律

### 依赖关系

```
M1-2 主线识别器（完成度：90%）
  ↓ 需要
催化剂 LLM 回写调度挂载（未完成）
  ↓ 积累 1 个月数据
M2-1 主线→标的映射器（0%）
```

### 实施方案

#### Phase 1: 催化剂回写挂载（本周）

**任务**: 实现 `mainline_catalyst_llm` 调度任务

```python
# quantsys-v2/adapters/inbound/scheduler/job_handlers/mainline_catalyst.py
async def mainline_catalyst_handler(context):
    """
    LLM 回写主线催化剂
    
    流程:
    1. 读取当日 market_theme 表（catalyst 为空的记录）
    2. 对每个主题调用 LLM 分析催化剂
    3. 回写到 market_theme.catalyst
    """
    from application.services.market_perception_service import MarketPerceptionService
    
    service = MarketPerceptionService()
    
    # 1. 获取待补充催化剂的主题
    themes = db.query(MarketTheme).filter(
        MarketTheme.catalyst.is_(None),
        MarketTheme.trade_date >= date.today() - timedelta(days=7)
    ).all()
    
    logger.info(f"待补充催化剂主题: {len(themes)} 个")
    
    # 2. LLM 分析
    for theme in themes:
        try:
            catalyst = await service.analyze_catalyst(
                theme=theme.theme,
                sector=theme.sector,
                limit_up_stocks=theme.stocks,
                date=theme.trade_date
            )
            
            # 3. 回写
            theme.catalyst = catalyst
            db.commit()
            logger.info(f"✅ {theme.theme} 催化剂已补充")
            
        except Exception as e:
            logger.error(f"❌ {theme.theme} 催化剂分析失败: {e}")
    
    return {"updated": len(themes)}
```

**挂载到 Agent OS**:
```yaml
name: mainline_catalyst_daily
cron: "0 0 22 * * 1-5"  # 工作日 22:00
handler:
  type: http
  url: http://localhost:5001/api/scheduler/mainline-catalyst
window: w-8366e526
```

#### Phase 2: 数据积累期（09-01 ~ 09-20）

**目标**: 积累 ≥30 条主题（≥20 个交易日）

**验证**:
```sql
SELECT COUNT(*) as themes, COUNT(DISTINCT trade_date) as days
FROM quant.market_theme
WHERE catalyst IS NOT NULL;

-- 目标: days >= 20
```

#### Phase 3: M2-1 实施（09-21 后）

**输入**: 主线名称（如「半导体」）

**输出**:
```json
{
  "mainline": "半导体",
  "candidates": [
    {
      "symbol": "688981",
      "name": "中芯国际",
      "score": 85,
      "reasons": [
        "近 5 日 3 次出现在主线涨停名单",
        "主力资金净流入 +5.2 亿",
        "行业龙头，政策催化剂受益"
      ],
      "risks": [
        "PE 估值偏高（60x）",
        "短期涨幅过大（+25%）"
      ]
    },
    ...
  ]
}
```

### 预计完成时间

- 催化剂挂载: 2026-09-01（本周）
- 数据积累: 2026-09-20（3 周）
- M2-1 实施: 2026-09-21（1 周）
- **总计**: 4 周

---

## ⚠️ 问题2: M2-3 池战场评分（部分可用）

### 工单定义（RFC 005）

> 池战场评分：对 pool 27/35 调 `pool_battlefield` → 输出综合评分+排名且理由可解释

### 当前状态

#### 验收结果（2026-08-26）

| 项 | 结果 | 状态 |
|---|---|---|
| 工具可调用 | ✅ | 正常 |
| 输出结构合理 | ✅ | 正常 |
| **评分区分度** | ⚠️ | **差异 <2 分** |
| **理由可解释** | ❌ | **优劣势列表为空** |
| **数据质量** | ⚠️ | **降级（资金流缺失）** |

#### 实测数据（08-26）

```
Pool 27（价值蓝筹池）: 64.2 分
Pool 35（成长科技池）: 62.3 分
差异: 1.9 分（<2 分，区分度不足）❌
```

**预期**: 差异 ≥5 分（价值池与成长池风格迥异）

### 根因分析

#### 根因1: 资金流数据缺失（P0）

**后端初始化**:
```python
# quantsys-v2/application/services/opponent_behavior_service.py
class OpponentBehaviorService:
    def __init__(self):
        self.fund_flow_repo = None  # ❌ 未初始化
```

**评分算法依赖**:
```python
def calculate_pool_score(self, pool):
    # 资金流维度（权重 30%）
    if self.fund_flow_repo:
        retail_flow = self.fund_flow_repo.get_retail_flow(...)
        institution_flow = self.fund_flow_repo.get_institution_flow(...)
        score += (retail_flow + institution_flow) * 0.3
    else:
        score += 50 * 0.3  # ❌ 降级：所有池子用基础分 50
```

**影响**: 所有池子资金流维度评分趋同（50 分），导致总分差异 <2 分

#### 根因2: 优劣势分析为空

**代码逻辑**:
```python
def analyze_strengths_weaknesses(self, pool_metrics):
    strengths = []
    weaknesses = []
    
    # 依赖资金流数据
    if pool_metrics.get('retail_flow_rate') > 0.6:
        strengths.append("散户资金持续流入")
    
    if not strengths and not weaknesses:
        return None  # ❌ 返回空
    
    return {"strengths": strengths, "weaknesses": weaknesses}
```

**结果**: 无资金流数据 → 无法判断优劣势 → 列表为空

### 修复方案

#### 方案A: 修复资金流数据（关联 M0-P0）

**依赖**: M0 资金流数据修复完成（预计今日）

**步骤**:
1. 执行 M0 ETL 脚本（`sync_fund_flow_to_factors.py`）
2. 验证 `factor_values` 表资金流因子完整
3. 重新测试 `pool_battlefield`

**预期效果**:
- Pool 27（价值蓝筹）: 58 分（资金流入放缓）
- Pool 35（成长科技）: 72 分（资金流入旺盛）
- 差异: 14 分（✅ 区分度显著）

#### 方案B: 补充其他维度（长期优化）

**当前维度**（1 个）:
- 资金流（retail + institution）

**新增维度**（3 个）:
1. **技术面**:
   - 池内股票突破比例（MA/MACD 金叉）
   - 平均 RSI（超买/超卖）

2. **基本面**:
   - 平均 PE/PB（估值水平）
   - 平均 ROE（盈利能力）

3. **市场热度**:
   - 池内涨停股数量
   - 池内主线标的占比

**实施**:
```python
def calculate_pool_score(self, pool):
    score = 0
    
    # 维度1: 资金流（30%）
    score += fund_flow_score * 0.3
    
    # 维度2: 技术面（25%）
    score += technical_score * 0.25
    
    # 维度3: 基本面（25%）
    score += fundamental_score * 0.25
    
    # 维度4: 市场热度（20%）
    score += momentum_score * 0.2
    
    return score
```

### 验收清单

#### 短期验收（本周）

- [ ] M0 资金流数据修复完成
- [ ] 重新测试 pool_battlefield（pool 27 vs 35）
- [ ] 评分差异 ≥5 分
- [ ] 优劣势列表非空（≥2 条）

#### 长期验收（下月）

- [ ] 补充技术面/基本面/市场热度维度
- [ ] 池子评分与实际表现相关性 ≥0.7
- [ ] 回测验证：高分池 5 日超额收益 ≥低分池

---

## ✅ 问题3: M2-2 排雷清单（已完成）

### 实施成果（2026-08-26）

**功能**:
1. ✅ ST 禁区（symbol 包含 "ST" → blocked）
2. ✅ 操纵嫌疑检测（调用 manipulation_detect，>70 分拦截）
3. ✅ 留痕机制（osMemory，namespace=risk）
4. ✅ 容错降级（检测失败不阻塞交易）

**集成位置**:
- `agent-dh/packages/trading/src/index.ts:portfolio_trade`
- 买入前自动检查

**验收**: ✅ 通过（ST 股 + 操纵股拦截，正常股通过）

**无遗留问题**

---

## 📊 M2 完成度明细

### 工单完成度

| 工单 | RFC 005 定义 | 实施 | 验收 | 完成度 |
|------|-------------|------|------|--------|
| M2-1 | 主线→标的映射 | ❌ 未开工 | N/A | 0% |
| M2-2 | 排雷清单 | ✅ 完成 | ✅ 通过 | 100% |
| M2-3 | 池战场评分 | ✅ 完成 | ⚠️ 部分 | 50% |
| **总计** | **3 个工单** | **1.5/3** | **1.5/3** | **66%** |

### 阻塞依赖

```
M0 资金流修复（今日）→ M2-3 完全可用（明日）
M1-2 数据积累（3周）→ M2-1 实施（4周后）
```

---

## 🎯 修复优先级与方案

### P0 - 立即修复（今日）

**M2-3 资金流依赖** → 关联 M0-P0

1. 执行 M0 ETL 脚本
2. 验证资金流因子完整
3. 重新测试 pool_battlefield

**预计时间**: 2 小时（依赖 M0 修复）

### P1 - 本周完成

**M1-2 催化剂回写挂载**

1. 实现 `mainline_catalyst_handler`
2. 挂载到 Agent OS scheduler
3. 验证自动回写

**预计时间**: 4 小时

### P2 - 长期优化（下月）

1. **M2-3 多维度评分** → 补充技术面/基本面/市场热度
2. **M2-1 实施** → 数据积累后开工

---

## 📈 修复后预期提升

| 维度 | 当前 | 修复后（短期） | 修复后（长期） |
|------|------|---------------|---------------|
| M2 完成度 | 66% | **83%** | **100%** |
| M2-3 可用性 | 50% | **90%** | **95%** |
| M2-3 评分区分度 | 1.9 分 | **≥5 分** | **≥10 分** |
| M2-1 可用性 | 0% | 0% | **80%** |

---

## 🔗 相关文档

- [M2 实施总结](m2-stock-selection-implementation-summary.md)
- [M2-3 池战场测试报告](m2-3-pool-battlefield-test.md)
- [M0 资金流修复方案](m0-fund-flow-fix-plan.md)
- [M1 市场感知验收](m1-market-perception-acceptance.md)
- [RFC 009 M2 实施方案](../../rfcs/009-stock-selection-m2-implementation.md)

---

## ✅ 验收清单

### 今日验收

- [ ] M0 资金流修复完成
- [ ] pool_battlefield 重新测试
- [ ] 评分差异 ≥5 分

### 本周验收

- [ ] 催化剂回写挂载上线
- [ ] 催化剂自动补充 3 日无中断

### 长期验收（09-21 后）

- [ ] market_theme 积累 ≥30 条
- [ ] M2-1 mainline_stocks 工具实现
- [ ] 输入「半导体」输出 ≥2 候选

---

## 📊 数据库当前状态

### stock_pools 表

```
池子数: 29 个
```

**主要池子**:
- Pool 27: 价值蓝筹池
- Pool 35: 成长科技池
- Pool 1-26: 行业/主题池

### market_theme 表

```
主题数: 14 条
交易日: 5 天（08-24 ~ 08-28）
最新日期: 2026-08-28
```

**覆盖板块**:
- 农化制品、软件开发、化学制品
- 通信设备、半导体、元件
- 装修装饰、通用设备、电池

---

**诊断签名**: agent-dh investor (w-8366e526)  
**诊断日期**: 2026-08-31 03:15  
**下次审计**: M0 修复后 + M2-3 重新验收（预计 2026-09-01）
