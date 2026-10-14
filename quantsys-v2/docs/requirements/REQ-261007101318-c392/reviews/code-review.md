# 评审报告（REQ-261007101318-c392）

**评审方式**：本次无独立评审人（单窗口交付），故本报告是**自查式评审**——按
`design/` 五份文档逐条对照实现，并对每条结论给出可复核命令。**不声称"第三方评审"**。

## 一、逐条对照（设计 ↔ 实现）

| 设计条目 | 期望 | 实测 | 结论 |
|---|---|---|---|
| `architecture.md` 落点：闸门在 `tick()` 且与 `run_forever` 同入口 | `_resolve_trading_day` 唯一 | 全仓仅 2 处调用（`engine.py:324` / `:388`），无第二份日历口径 | ✅ |
| `architecture.md` 判定失败纪律 | 一律保守判非交易日 | `injected-error` / `compute-error` 两条路径均返回 `False` | ✅ |
| `architecture.md` 级别与闭环解耦 | 级别恒有；闭环承诺按开关 | `_notify_level` 已无 `todo_service is None` 早退；门控点在 `_skeleton_lines` / `_summary_line` / `render_p1` | ✅ |
| `data-model.md` 一通知一行 upsert | `ON CONFLICT (notification_id)` | 仓储第 42 行即该语句；用例 `test_audit_is_upsert_not_append` 断言两次 save 仍 1 行 | ✅ |
| `data-model.md` 不建 ORM 模型 | 避免漂移门 | 未加模型；`tests/test_orm_db_drift.py` 通过 | ✅ |
| `interfaces.md` §2 名称契约 | `name` 永不等于 symbol | `notifier.py:190` 为 `name=payload.name or None` | ✅ |
| `interfaces.md` §4 卡面四段契约 | 名称/意图/处置级别/下一步 + 尾注 | 实发卡与本地渲染均齐备（用户 D-9 目视认可） | ✅ |
| `interfaces.md` §5 审计失败不打挂 | 自吞不上抛 | 仓储第 70-73 行；`test_audit_failure_never_breaks_notification` | ✅ |
| `test-cases.md` §6 未覆盖项 | t5 补齐三项 | run_forever 整环 / 留痕去重 / 装配降级均有用例 | ✅ |

## 二、评审发现（如实列出，含未修项）

1. **子卡验收模板跨仓**（流程问题，非代码问题）：自动生成的子卡阶段文本写
   `npx vitest run tests/` / `pnpm test` / `npx tsc --noEmit`，而本仓是 Python/pytest。
   处理：按本仓栈执行等价命令，并在每张子卡汇报里显式标注不一致（不改卡文）。
2. **`sender_id` host 段写法不一**（已知瑕疵）：launchd 侧 `192.168.1.109`、终端侧 mDNS 名。
   跨机分辨不受影响；同机按 host 聚合会分裂。**未修**，已登记在 `design/interfaces.md` §3.1 与验收材料局限节。
3. **审计覆盖上限**：绕过 `NotificationService` 直接 POST 飞书 webhook 的发送方抓不到。
   设计已声明为能力上限；**未修**（需跨仓统一发送入口，属独立需求）。
4. **t6 以演练替代真实回执**（D-12）：证据强度弱于真实交易日回执，已在
   `verification.md`、`requirement.md` D-12、`notes/t6-receipt-rehearsal.md` 三处声明。

## 三、回归与安全

- 定向：228 → **232 passed**（新增 4 条）；key 扫描：**621 passed**；
- `notify-guard intercepted=0 egress=0 offenders=[]` —— 全程**零真实外发**；
- 变异测试：拆掉 `run_forever` 日级门 → 新用例立刻 `1 failed`（证明用例非空断言），文件已字节级还原；
- 演练 SQL 走**可回滚事务**：`ROLLBACK` 后 2026-10-08 残留 0/0（生产库零污染）。

## 四、评审结论

**通过**（含上述 4 条如实登记的未修项/限定）。四条 FR 与设计一致、可跑判据齐备、
失败路径均按"响亮不静默"实现；建议归档时重点复核 D-12（演练替代）与第 3 条能力上限。
