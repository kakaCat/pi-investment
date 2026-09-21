---
req_id: REQ-4842fe
doc: design/workflow-engine-contract
serves: FR-4, FR-6
status: design
---

# REQ-4842fe 设计附录 · DSH Workflow 引擎契约与踩坑

> 全部条目为 2026-09-20 本窗口在本机实测/实读所得，标注来源文件。**实施者动手前必须先读本附录**——现有 `ctx.subagent` 与 `ctx.tools.workflow` 两处错误都源于对引擎契约的假设。

## 1. 引擎事实清单  `serves: FR-4`

| # | 事实 | 来源 |
|---|---|---|
| 1 | 脚本运行在 worker 线程内的 `node:vm` 上下文，**只注入五个 hook**：`agent` / `parallel` / `pipeline` / `phase` / `log` | `dsh-workflow-worker-thread/lib/worker.cjs`（grep 仅命中这五个） |
| 2 | **没有 `ctx` 全局、没有 `subagent` 函数**——脚本内写 `ctx.subagent(...)` 必然 `ReferenceError` | 同上 + `dsh-workflow/README.md`「Use this package」 |
| 3 | 脚本是**纯 JS 体**（非 TS），支持顶层 `await`，以 `return <JSON>` 结束 | `dsh-workflow/README.md` |
| 4 | `agent(prompt, opts)` 失败解析为 `null`（普通子任务失败不是基础设施错误，脚本自行处理） | 同上 |
| 5 | 脚本**不能调工具**、读不到台账（vm 内无 ctx） | 同上 |
| 6 | **不支持嵌套 run**：脚本没有 `workflow()` hook，官方把 "saved and nested workflows" 列入 Deferred | `dsh-workflow/README.md`「Known Limitations」 |
| 7 | run **阻塞调用方回合**直到 settle；`workflow` 工具因此有 10 分钟级超时约束 | `dsh-tool-workflow/README.md` + 本仓 `domain/limits.ts` timeoutInteractiveMs |
| 8 | 结果是**不 reject** 的：失败 = `stopReason: error`，取消 = `cancelled` | `dsh-workflow/README.md` |
| 9 | 调用方必须 `dispose()`；`dispose()` 幂等，有 `disposeGraceMs` 上限（默认 5000ms） | `dsh-workflow/README.md` + worker-thread README |
| 10 | 脚本返回值经 realm 物化：**只接受 lossless JSON**（拒绝函数 / Symbol / 循环引用 / 稀疏数组 / 非有限数 / 嵌套 undefined） | `dsh-workflow-worker-thread/README.md`「Value boundary」 |
| 11 | 引擎级 caps：`maxConcurrentAgents`（默认按 CPU）、`maxTotalAgents`（默认 1000）、`maxItemsPerCall`（默认 4096） | worker-thread README 配置表 |
| 12 | worker 环境被清洗（不继承 `process.env` 凭据）——**不要把密钥/令牌交给脚本** | 同上「Trust expectations」 |
| 13 | 不是安全边界：逃逸代码仍可触达 Node 权限 | 同上 |

## 2. 本 profile 的加载状态（易错点）  `serves: FR-4`

| 组件 | 活动配置状态 | 结论 |
|---|---|---|
| `workflow-worker-thread`（引擎） | `disabled: false` | **引擎在位**，可直接消费 |
| `tool-workflow`（模型侧工具） | `disabled: true`（2026-09-08 起，随 delegation 组禁用） | **不可调用**；现有 TaskExecuteTool 走它 → 必然失败 |

**决策**：子卡执行**只消费引擎**（`ctx.workflowEngine.start`），不依赖模型侧工具注册——引擎已加载，不触碰 delegation 组禁用策略。

## 3. 正确调用范式  `serves: FR-4, FR-6`

```ts
// adapters/WorkflowEngineRunner.ts（唯一接触引擎的地方）
const run = engine.start({ script, meta, args, parent, signal })
try {
  const settled = await run.result                    // { result, stopReason }
  if (settled.stopReason !== "completed") return { ok: false, reason: settled.stopReason }
  return { ok: true, value: settled.result }
} finally {
  await run.dispose()                                 // 幂等，必调
}
```

脚本模板（子卡级）：

```js
phase("执行");
const out = await agent(prompt, { /* 可选 schema：结构化产出 */ });
return { ok: out !== null, output: out };
```

## 4. 踩坑清单（每条都有真实代价）  `serves: FR-4, FR-6`

| 坑 | 现象 | 教训 |
|---|---|---|
| 用 `ctx.subagent(...)` 写脚本 | 脚本解析通过、执行即 ReferenceError | 脚本的 API 面是五个 hook，不是宿主 ctx |
| 用 `ctx.tools.workflow(...)` 起 run | 本 profile 工具被禁 → 调用即失败 | 消费引擎，不消费被禁的模型侧工具 |
| 用 grep 断言脚本内容做测试 | 字符串里有 `ctx.subagent` 就算过，线上必炸 | 测试必须断言**契约**（hook 白名单 + 无 ctx/工具名），必要时真跑一次 run |
| 期望脚本能改台账 | 脚本内无 ctx、无 FS、无工具 | 状态变更一律由宿主调度器在 run 之外完成 |
| 期望 run 内再起 run | 无 `workflow()` hook，嵌套不支持 | 需要多层就用"宿主调度 + 每次一层 run" |
| 把长链塞进一个 run | 阻塞回合 + 10 分钟超时 | 一卡一 run，事件链分步 |
| 想让脚本返回对象实例 | realm 物化拒绝非 lossless JSON | 只 return 纯 JSON 数据 |
| 忘了 dispose | 子卡链走完后 worker 悬挂 | finally 兜底 dispose |

## 5. 对设计的直接约束汇总  `serves: FR-4`

1. 子卡 = 一次 run（不嵌套、不合并）；
2. 脚本只做"干活 + 返回 JSON"，**所有状态变更在宿主侧**；
3. 失败不抛异常给调用方，由 `stopReason` + `null` 产出表达，宿主翻译成子卡失败；
4. 生成立即校验（hook 白名单门禁），把契约错误挡在下单前；
5. 长链靠事件链分步，不靠单个 run 长跑。
