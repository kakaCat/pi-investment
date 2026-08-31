# M7-1 opponent_behavior 数据源交付（2026-09-01）

> 署名：investor w-8366e526
> 状态：✅ 完成（M7 完成度 0% → 33%）

---

## 1. 诊断结论

M7-1 的核心缺口不是"没有工具"，而是**数据源未接线**：

| 层次 | 现状 | 问题 |
|------|------|------|
| 后端服务 | `OpponentBehaviorService` 已实现（散户/机构/游资行为 + 市场阶段 + 机会地图） | **fund_flow_repo 未注入** → 散户/机构行为全部 degraded（`'NoneType' object has no attribute 'get_market_aggregate_flow'`） |
| 后端 API | `GET /api/game/market/opponent-behavior` 已存在 | 返回 degraded 空数据 |
| Agent 工具 | competition 插件只有 `competition_analysis` 一个工具 | **缺 opponent_behavior 工具注册**（CLAUDE.md 声明的 3 个能力只有 1 个） |

## 2. 修复内容

### 2.1 后端：fund_flow_repo 兜底注入（quantsys-v2）

`OpponentBehaviorService.__init__` 未注入时自动自建 `FundFlowORMRepository`（与 AttributionService 连接模式一致，向后兼容）。

**修复前**（全 degraded）：
```
散户: unknown, 机构: unknown, 市场阶段: unknown, 博弈机会: 0
```

**修复后**（真实数据驱动）：
```
散户: neutral（净流入 +21.2 亿，情绪 50）
机构: accumulating（净流入 +645 亿，目标: 电子设备/软件/专用设备/通用设备/银行）
游资: inactive（估算，龙虎榜未接入）
市场阶段: consolidation | 风险偏好: medium | 博弈机会: 1 | degraded: False
```

### 2.2 Agent 工具注册（agent-dh competition 插件 1→3 个）

新增两个工具（M7 全部能力落地）：

| 工具 | 功能 | 对应工单 |
|------|------|----------|
| `opponent_behavior` | 市场对手行为分析（散户/机构/游资 + 阶段 + 机会） | M7-1 ✅ |
| `manipulation_detect` | 个股操纵迹象检测（异常放量/拉高出货/对倒） | M7-3 基础 |

均遵循 BaseTool 模式 + ToolPrompt 纯 JSON Schema（每层 `additionalProperties` 显式声明）。

## 3. 验证结果

| 验证项 | 结果 |
|--------|------|
| schema 冒烟（全部插件构造） | ✅ 19/19 通过 |
| 新工具单测（tests/competition-game-tools.test.ts） | ✅ 11/11 通过（校验/映射/默认值/异常） |
| 后端 API 真实调用 | ✅ 返回真实数据（degraded=False） |
| 数据源字段核实 | ✅ `stock_fund_flow` 表列名与 repo 映射一致（main_net_inflow/small_net_inflow…） |

## 4. 备注

- 游资行为仍为估算值（龙虎榜数据未接入）——属已知降级，`estimated: true` 显式标记
- M7-3 操纵检测后端已有 `GET /api/game/market/manipulation-detect`，Agent 工具已注册，待实战验证检测逻辑
- 下一步：M7-2 散户恐慌代理指标（基于 emotion_index/涨跌家数/量能的恐慌指数）
