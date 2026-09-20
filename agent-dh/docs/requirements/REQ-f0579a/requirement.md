# REQ-f0579a dsh-pmboard 审计整改：verdicts 覆盖留痕 + 客户端回归 + 架构门禁

## 背景

2026-09-20 w-dd6cfa29 对 dsh-pmboard 做全面审计（vitest 1404 用例 / 113 文件），发现
**17 个失败测试（10 个文件）已在 HEAD 上**，且线上实例（:13080）跑的正是这份代码。
最近提交 e25d6c8b 自称「dist/lib 已构建核验」——构建了，但没跑测试。

## 复现步骤

```bash
cd agent-dh/packages/pages/dsh-pmboard
npx vitest run
# 实测（2026-09-20 17:56）：Test Files 10 failed | 103 passed；Tests 17 failed | 1387 passed
```

失败分五群：
- verify-override×2、acceptance-archive×2、e2e-accept-override×1（覆盖通过留痕缺失）
- client-view×2（done 需求从泳道消失、底部归档条消失、「待归档」旗标不现）
- board-info-fixes×3（产物种类可读标签缺失×1；验收态操作条含 move-req×2）
- output-contract×2、layer-boundary×1、tools-dispatch×1、message-hygiene×2、size-budget×1（门禁债）

## 根因

### FR-1 verdicts.ts 覆盖通过丢留痕（真功能 bug）
`src/http/routers/verdicts.ts:52-89`：REQ-327bdf 引入的早退分支——只要带
`confirm_override` 就直接归档，**从不写 `r.acceptanceOverride`**（违反 REQ-a8d582 FR-4
「覆盖必须台账/评论/状态事件三处留痕」）；下方 91-159 行的完整校验路径对覆盖场景整体成为
死代码；无材料时还会伪造一份 verification 记录（下游会把合成材料当真证据）。

### FR-2 客户端看板回归（基线归一提交 972b2262 覆盖丢失）
f215753f → HEAD 的 diff 证实：wip 基线归一把旧版视图盖掉新版，丢了三处：
① toReqCards 把 done 需求也过滤（设计是「done（待归档）归入验收泳道」，REQ-6f39b5）；
② 底部归档条（dsh-pm-archived-bar）整段渲染消失（M3 起就在，CSS 还在）；
③ collectReqDocs 的产物标签从「种类可读名」改成裸文件名（af8a2ac0 修追溯链时引入），
与「产物种类带可读标签」契约冲突。

### FR-3 操作条断言冲突（两个用户裁定打架）
b2b37d9b 按用户裁定给全在途态加「立项取消」（data-action=move-req），
board-info-fixes 两条用例仍按旧裁定断言「验收态操作条无任何 move-req」。
新裁定覆盖旧裁定，断言需精确化：验收态不允许**阶段推进类** move-req，
但「立项取消」（破坏性、仅人）允许存在。

### FR-4 架构门禁债（新增工具未登记）
- output-contract：defineTaskExecuteTool / defineTaskStatusTool 未登记 RESPONSE_SOURCES；
- layer-boundary + tools-dispatch：TaskExecuteTool(.ts/types.ts)/TaskStatusTool 内含
  状态字面量（'failed' / 进度表 todo..done），状态词汇应单点在 domain；
- message-hygiene：pagination.ts:52 拼接消息使 client 98→99 超棘轮；
  TaskExecuteTool timeoutMs: 600000 裸数字（须用 LIMITS.timeoutInteractiveMs）；
- size-budget：src/index.ts 432 行、src/client/styles/base.ts 408 行，超 400 行门禁。

### FR-5 杂项
- src/adapters/CaptureHook.ts.backup（16KB 死文件）入库；
- renderMarkdown 链接不过滤 javascript:/data: 协议（低危 XSS 面）。

## 修复方案

按根因分 5 个任务（详见 plan.md）：t1 删早退分支走统一留痕路径；t2 恢复看板三处
（done 泳道/归档条/产物标签=种类名·文件名）；t3 操作条断言精确化（只许 canceled）；
t4 门禁债（契约登记/状态词汇下沉 domain/LIMITS/拼接改模板串）；t5 尺寸拆分+杂项+全量终验。

## 验收标准

1. `npx vitest run` 全绿（0 失败）；
2. `npx tsc --noEmit` 绿；
3. `pnpm build` + verify-client-build 通过（WRAP_SENTINEL 哨兵在位）；
4. 覆盖通过路径写 acceptanceOverride 留痕（verify-override 用例为证）；
5. 看板 lanes 视图：done 需求归验收泳道、底部归档条回归、产物标签=种类名+文件名。

## 回归

每处修复配既有失败用例转绿为证（17 例全部回归）；t3 修改的两条断言在测试内注释
写明「为什么从严格断言改为精确断言」（两条用户裁定的合并点），防下次再被当 bug 改回。

## 边界

- 不重构 663 行的 stage-panel.ts / 627 行的 board-mount.ts / 1114 行 protocol.ts
  （已有白名单与独立后续任务）；
- 不动 REQ-327bdf 的「覆盖即可通过」语义本身，只补留痕；
- 不动立项取消按钮的「全在途态渲染」裁定（2026-09-20 用户裁定），只精确化旧断言；
- 不重启线上实例（重启由用户执行 launchctl kickstart）；
- 本需求只修 dsh-pmboard 包内问题；审计中发现的包外观察项（profile 目录过时、
  cordis.yml 飞书 webhook 明文）不在本需求范围，另行处理。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已完成（有证据） | t-b96644 |
| FR-2 | ✅ 已完成（有证据） | t-f54dcc |
| FR-3 | ✅ 已完成（有证据） | t-632e7c |
| FR-4 | ✅ 已完成（有证据） | t-0c3303 |
| FR-5 | ✅ 已完成（有证据） | t-cee913 |

> 无未接收条款（5 条全部有落点）。

<!-- reqboard:marks:end -->
