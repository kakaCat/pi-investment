# REQ-2e9473 执行链加固交付记录

**窗口**：w-41e7e4cd（session-41e7e4cd）｜**需求类型**：feature｜**交付日期**：2026-09-17

## 交付范围（W1-W8，19 任务）

| 工作流 | 交付 | 关键文件 |
|---|---|---|
| W1 确认弹框原子化 | `reqboard_ask_confirm`（弹框→落章→推进一次完成）+ 闸门问题卡 + submit note 改指向 + 里程碑超时提醒 + 文字确认核验 | agent-tools.ts / capture-hook.ts / stage-prompts.ts |
| W2 实施防假完成 | done 凭证门四重校验（汇报前置/真实动作/批量节流/构建新鲜度） | agent-tools.ts:assertDoneEvidence |
| W3 拆分幂等与告警 | decompose 幂等守卫 + rollup 阻塞 blockers | agent-tools.ts / sync |
| W4 产物自动登记 | REQ 目录落盘即产物 + task_output 上浮 + evidence 存在性 + 归档漏登 | sync-artifacts.ts / routes.ts |
| W5 实施卡 | PlanTask.implementation + 薄卡拒落 + 开工送达任务卡 | protocol.ts / agent-tools.ts |
| W6 验收单 | 逐项验收单 + 断点续验 + 返工回路 + 逐项 UI | protocol.ts / routes.ts / stage-panel.ts |
| W7 阶段边界与规范 | tasks 可选的 plan + 创作型 decompose + STAGE_PROMPTS 重写 + workflow-stages.md 六要素 | agent-tools.ts / stage-prompts.ts / workflow-stages.md |
| W8 文档留痕 | change_note 强制 + 下游待同步标记 + 销标 | protocol.ts / agent-tools.ts |

## 验证证据

- 全量回归：**467/468**（唯一失败 `board-info-fixes.test.ts` 验收态操作条为**存量问题**，经 git stash 隔离验证与本次改动无关）
- 故障注入：`tests/fault-injection.test.ts` 七类事故（A-G）逐条复现全绿
- 构建门禁：`pnpm build:client` + `verify-client-build.mjs` OK（bundle 含新 UI 符号）
- 新增测试文件 10 个（ask-confirm / confirm-evidence / verification-sheet / verdicts-and-rework / stage-boundary / doc-sync / fault-injection / sync-artifacts / task-output-and-evidence / decompose-tools 扩充）

## 过程教训（已进任务卡留痕）

1. **关门先跑全量**：t03 首次只跑相关测试就关任务，全量抓出 21 个 fixture 未跟上新规则的失败。
2. **测试隔离**：多个测试文件共用 cwd 相对路径 `docs/requirements/REQ-abc123/` 并行互踩 → 独立 id。
3. **schema 声明要与参数一致**：decompose 的 tasks schema `additionalProperties:false` 漏声明 `implementation` → ToolArgsError（DSH schema 铁律又一实例）。
4. **返回体形状相似易改错位**：doc_sync_warning 首次误加到 task_move（与 move 形状相近）。
5. **措辞锁定测试是防回退资产**：改写阶段纪律会触发断言失败，属预期维护成本。

## 相关文档

- 需求/计划：`docs/requirements/REQ-2e9473/`
- 阶段语义事实源：`docs/architecture/workflow-stages.md`（§各阶段职责规范）
- RFC：`docs/rfcs/014-requirement-board.md`（§14 执行链加固）
