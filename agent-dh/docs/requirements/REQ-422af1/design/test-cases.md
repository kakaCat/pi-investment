# REQ-422af1 技术设计 · 测试用例

> 阶段：planning · 窗口 w-41e7e4cd · 配套：architecture.md / fragments.md
> 纪律：每条用例写"跑什么、看到什么算过"；每条门禁必须**故障注入证明它变红**（本仓铁律：只测成功路径等于没测）。

## 1. 路由与解析（INV-1 / INV-2）

| # | 用例 | 断言（可执行） |
|---|------|---------------|
| T1 | 精确命中 | resolve(brainstorming, heavy, bug) → routeKey=brainstorming/heavy/bug，hitLevel=exact |
| T2 | 难度档回退 | 存在 (brainstorming, heavy)；无 (brainstorming, heavy, chore) → hitLevel=②，fragmentIds 含 brainstorming/heavy |
| T3 | 类型档回退 | 存在 (brainstorming, 星, bug)；无 (brainstorming, heavy, bug) → hitLevel=③ |
| T4 | 节点兜底 | 只有 (brainstorming, 星, 星) → hitLevel=④ |
| T5 | 全局铁律 | 任何 stage 都并入 common/iron-rules（hitLevel=⑤ 合并，非替代） |
| T6 | 覆盖完备（门禁 1） | 遍历 6 stage × 2 difficulty × 6 category，全部返回非空 text（0 例空串） |
| T7 | 唯一入口（INV-1） | 静态扫描：src 下 STAGE_PROMPTS[ 直取命中数 = 0；resolveStagePrompt 调用点 = 注入点（2 处） |

## 2. 预算与保底（INV-3）

| # | 用例 | 断言 |
|---|------|------|
| T8 | 预算裁剪非保底 | 构造超预算场景（预算=light 值）→ trimmed 非空，且 floor 片段仍在 fragmentIds |
| T9 | 保底永不裁 | 预算极小时：若"保底仍超限"则返回 error/超限标记（**不得**静默丢掉 floor 片段） |
| T10 | 去重 | 两个引用同一 id 的 include → fragmentIds 中该 id 出现 1 次 |
| T11 | 预算上界 | heavy 档默认预算下 charCount ≤ 8000（实测值写入断言，避免漂移） |

## 3. 留痕（INV-6）

| # | 用例 | 断言 |
|---|------|------|
| T12 | 留痕字段完整 | 每条记录含 at/windowKey/stage/difficulty/category/routeKey/hitLevel/fragmentIds/charCount |
| T13 | ring buffer 有界 | 写入 N+100 条 → 文件条数 = N（不无限增长） |
| T14 | 可读回 | 看板读取接口返回最近 k 条，字段与写入一致 |

## 4. 链声明与工具名（INV-4 / INV-5）

| # | 用例 | 断言 |
|---|------|------|
| T15 | 每节点含下一步 | 遍历全部分片：每个 (stage,*,*) 兜底档文本含"下一步："（0 例缺） |
| T16 | next 合法 | 解析出的 next stage ∈ 状态机允许后继（非法后继 → 测试红） |
| T17 | 工具名一致（门禁 2） | 注入文本中所有 reqboard_* ⊆ 注册集合；注入非法名 reqboard_legacy_probe → 红 |

## 5. 源/产物同步与孤岛（门禁 4 / 6）

| # | 用例 | 断言 |
|---|------|------|
| T18 | 产物同步 | 跑生成器后再比对：generated/fragments.ts 与 fragments/**.md 逐字节一致；改 md 不跑生成 → 红 |
| T19 | 无孤岛 | 每个分片 id 至少被一次解析命中（遍历测试枚举全部 id 反查） |
| T20 | id 唯一 | 分片 id 无重复（构建期断言） |

## 6. P0 零行为变更（INV-7，回归最重要）

| # | 用例 | 断言 |
|---|------|------|
| T21 | 文本等价 | 对 6 个 stage 逐一比对"改造前冻结快照 vs 改造后 resolve 结果"，逐字一致（含空白与换行） |
| T22 | 既有测试不动 | tests/stage-prompts.test.ts 断言**不修改**且全绿 |
| T23 | 快照冻结 | 仓库内保留基线快照文件（作为 T21 的对照物，随 P0 提交） |

## 7. 同窗口 surface 替换（G7）

| # | 用例 | 断言 |
|---|------|------|
| T24 | 输入包内容 | 节点输入包文本 == 路由结果 + 文档/台账投影；**不得**含前序对话摘录（INV-9 静态检查：不含历史消息标记） |
| T25 | 边界不平衡拒执行 | 构造两端未配对（tool 调用无结果）→ 替换**不发生**，返回结构化错误 + 留痕 |
| T26 | 活动轮次拒执行 | 模拟 agent 忙碌 → 不替换、留痕、不抛未捕获异常 |
| T27 | 先落盘后遗弃 | 顺序断言：产物写入事件 seq < 替换事件 seq |
| T28 | 失败降级 | 触达为 false 时：走弹框路径（返回"请开新窗口 + 输入包文本"），**不静默跳过** |

## 8. 自足性（INV-8，G6）

| # | 用例 | 断言 |
|---|------|------|
| T29 | 五字段齐备 | 需求文档与任务卡模板含 当前节点/上游结论/未决问题/下一步/证据指针（缺任一 → 红） |
| T30 | 冷启动可续跑（人工/A7） | 只给"路由提示词 + requirement.md"，回答：当前节点、上游已定结论、下一步用什么工具（三问全对算过） |

## 9. 门禁故障注入清单（每条都必须能红）

| 门禁 | 注入的故障 | 期望 |
|------|-----------|------|
| 1 覆盖 | 删 brainstorming 兜底分片 | 测试红 |
| 2 工具名 | 文本里插 reqboard_legacy_probe | 测试红 |
| 3 预算 | 预算调至极小并断言"必须报超限" | 测试红（若不报） |
| 4 孤岛/唯一 | 加一个无人引用的分片 / 重复 id | 测试红 |
| 5 链声明 | 删某分片的"下一步"行 | 测试红 |
| 6 同步 | 改 md 不跑生成器 | 测试红 |
| 7 自足 | 删需求文档的"未决问题"字段 | 测试红 |
| 既有 4 条 | layer-boundary / size-budget / typecheck / message-hygiene | 全绿（不得回退） |
