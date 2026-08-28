# M5 交易执行收口验收清单

| 字段 | 值 |
|---|---|
| 日期 | 2026-08-28 |
| 编制 | agent-dh k3（审计角色） |
| 对象 | RFC 005 M5-1 滑点建模 + M5-2 trade_verify 例行化 |
| 被验代码 | commit `aaa27865`（trading 插件滑点追踪 + slippage_report 工具） |

---

## 🔴 验收前必查：M5-1 可能整体空转（P0）

**发现**：`aaa27865`（08-25 22:07 提交）的滑点落库用的是 `qv2.createMemory`（quantsys-v2 client），但 **08-25 18:47 记忆迁移（`84f65eba`）已决策"quantsys-v2 memory 写入停用"**，且 08-26 `quantsys-v2-client` 的 memory 方法已标注 `@deprecated`（统一走 OsMemoryStore）。即：**滑点代码写在迁移之后，却用了被废弃的旧通道**，且读写两侧（createMemory 写 / searchMemory 读）都在旧通道上，try/catch 会把失败静默吞掉。

### 验收项 0（阻塞性）

```bash
# 0.1 确认旧通道死活：直接调 quantsys-v2 memory 写入端点
curl -s -X POST localhost:5001/api/memory -H 'Content-Type: application/json' \
  -d '{"kind":"episode","scope":"trade:slippage","title":"probe","content":"验收探针","status":"testing"}'
# 0.2 确认 trading 插件当前加载的代码版本（DSH 是否已重启加载 aaa27865）
```

- **0.1 若旧通道已停用/报错** → M5-1 必须改造：滑点读写迁移到 OsMemoryStore（参照 rule_gate 的 osMemory 用法），否则验收终止，打回返工
- **0.2 若 DSH 未加载新代码** → 参照 `051243c0` 的教训：pnpm install 刷新 file: 快照 + 重启 DSH profile（走 stop.sh/start.sh 精确操作）

## M5-1 滑点建模验收项（通道确认可用后执行）

| # | 验收项 | 方法 | 通过标准 |
|---|---|---|---|
| 1 | 端到端滑点记录 | 交易时段（9:30-15:00）模拟盘下一笔小额单（如 100 股低价股），portfolio_trade 返回体应含 `slippage{decision_price, fill_price, slippage_pct, decision_time}` | 返回含 slippage 块，数值合理（\|slippage_pct\| 一般 <1%） |
| 2 | 方向归一正确性 | 一笔 BUY + 一笔 SELL，核对符号规则：滑点正=更差（买贵/卖便宜） | BUY: (fill-decision)/decision×100；SELL: 取负。符号符合定义 |
| 3 | 落库可检索 | `slippage_report` 调用（无参 + 带 symbol 各一次） | 笔数≥实测成交笔数；avg/max/bySymbol 分布数值与落库记录一致 |
| 4 | 非阻塞性 | 静态审查已确认 try/catch 包裹 getQuote 与落库 | 代码审查即可（已✅）；可选：断网/mock 失败验证下单不受影响 |
| 5 | 数据归属正确 | 落库记录 scope=`trade:slippage`、status、payload 字段完整（symbol/action/quantity/decision_price/fill_price/slippage_pct/decision_time/order_id/ts） | 字段齐全，且**落在当前生效的记忆库**（OsMemoryStore 而非废弃通道） |
| 6 | reason 透传 | 落库 content 含下单理由 | R-005 联动成立 |

## M5-2 trade_verify 例行化验收项

| # | 验收项 | 方法 | 通过标准 |
|---|---|---|---|
| 7 | 例程挂载 | 盘后例程（每日 15:35 或 16:00）自动调用 `trade_verify`，挂到**当前可用的调度体系**（注意 Agent OS 稳定性问题，参照 M1 教训） | 调度任务可见，且宿主服务在线 |
| 8 | 自动运行证据 | **连续 3 个交易日**对账记录（created_at 时间戳为证，拒绝手动补跑冒充） | 3 天连续、时间在盘后窗口 |
| 9 | 异常处理能力 | 无交易日返回"无成交无异常"；有异常时输出异常清单且触发告警/记录 | 两种路径都有记录 |

## 验收规则提醒（新增，本次起生效）

凡"每日自动"类能力：必须提供**连续 3 个交易日自动运行证据**（以 created_at 时间戳为准），手动 curl 补跑不计入。——源自 M1"宣称闭环实为手动"教训。

## 已知关联风险

- Agent OS 当前不稳定（08-27 15:30 在线、23:59 宕机）：若 M5-1 迁到 OsMemoryStore，Agent OS 宕机时滑点落库会失败——try/catch 会吞掉，**建议在 catch 里加 structlog/console 告警日志**，避免静默丢失
- K线同步管线缺陷（08-26/27 不完整）不影响 M5 验收，但影响 M6-2 归因精度

## 变更日志

| 日期 | 内容 |
|---|---|
| 2026-08-28 | 创建。基于 `aaa27865` 代码静态审查 + 记忆迁移（`84f65eba`）冲突分析 |
