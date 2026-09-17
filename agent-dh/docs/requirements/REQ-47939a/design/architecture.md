# REQ-47939a 技术设计 · 架构（分层 / 依赖 / 模式选型 / 代码规范）

> 上游：`../requirement.md`（§4 方案 1、§5 不变量、§7 验收标准）
> 本文件回答：分几层、依赖朝哪、用什么模式、代码怎么写。

## 1. 目标形态（结论先行）

```
                         ┌──────────── shared/protocol.ts ────────────┐
                         │ 对外契约：DTO 类型 + 领域规则再导出（纯）    │
                         └───────────────┬───────────────────────────┘
                                         │ 允许单向依赖 ↓（client 与 host 共用同一条规则源）
   ┌─────────────┐   ┌─────────────────┐   ┌──────────────────────────────┐
   │  domain/    │←──│  application/   │←──│  adapters/                   │
   │  纯领域规则  │   │  用例（端口消费） │   │  端口实现（store / fs / 会话） │
   └─────────────┘   └─────────────────┘   └──────────────────────────────┘
        ↑                    ↑                          ↑
        └──── tools/<Name>Tool（三段式薄壳）· http/（协议转换）· client/（渲染）────┘
```

**一句话**：领域规则只有一处实现（`domain/`），用例只编排不判定（`application/`），I/O 只在 `adapters/`，工具壳与 HTTP 退化成入口适配。

## 2. 依赖方向（可机械检查）

| 层 | 允许 import | 禁止 import |
|----|------------|------------|
| `domain/` | `domain/**`、TS 标准库 | 任何 `node:*`、`@deepseek-ai/*`、`@pi-investment/*`、`../application|adapters|tools|http|client`、`store`、`ctx` |
| `application/` | `domain/**`、`application/ports.ts` | `node:*`、`../adapters/**`、`../tools/**`、`../http/**`、`cordis` |
| `adapters/` | `application/ports.ts`、`domain/**`、`node:*`、`@deepseek-ai/*` | `../tools/**`、`../http/**`、`../client/**` |
| `shared/` | `domain/**`（单向）、TS 标准库 | `node:*`、`application/`、`adapters/`、`tools/`、`http/` |
| `tools/` `http/` `client/` | 任意下层 | 互相直接 import（`tools` 不得 import `http`，反之亦然） |

**机械检查**（对应 acceptance A3 与 INV-2）：新增测试 `tests/layer-boundary.test.ts` 用正则扫描 `src/` 各层文件的 import 语句，逐条断言上表；另断言 `tools/` 与 `http/` 源码中不出现状态字面量比较（`status === '`、`=== 'planning'` 等），状态判断只允许出现在 `domain/`。

> 为什么把 `shared/protocol.ts` 放在 domain 之上：它被 20 个文件（host 14 + client 6）引用，是事实上的契约枢纽。让它**单向再导出** domain 的类型与规则常量，客户端渲染"下一步可推进哪"与宿主判定用**同一份表**——消除"前端口径与后端口径漂移"这类历史事故。代价是 client bundle 会含少量纯函数，可接受（domain 无 I/O，体积小）。

## 3. 目录落位表（旧 → 新）

| 现路径 | 行数 | 去向 |
|--------|------|------|
| `host/agent-tools.ts` | 2,946 | 拆为 `tools/<13→9 个工具>`（壳）+ `application/use-cases/*`（逻辑）+ `domain/**`（规则） |
| `host/routes.ts` | 1,074 | `http/routes.ts` + `http/routers/{requirements,tasks,stages,verdicts,artifacts,triage}.ts`（只做协议转换，复用用例） |
| `host/store.ts` | 223 | `adapters/JsonLedgerRepository.ts`（实现 `ReqboardRepository` 端口） |
| `host/rollup.ts` | 145 | `domain/workflow/RollupSpec.ts`（纯函数：台账快照 → 推进决策） |
| `host/artifact-gates.ts` | 165 | `domain/artifact/ArtifactSpec.ts` |
| `host/verdicts.ts` | 143 | `domain/workflow/AcceptanceSheetSpec.ts`（裁决 + 返工任务生成） |
| `host/sync-artifacts.ts` | 168 | `adapters/FileDocRepository.ts`（扫描/落盘）+ `domain/artifact/ArtifactSpec.ts`（分类规则） |
| `host/capture-hook.ts` | 303 | `adapters/SessionProbeAdapter.ts`（会话事件/工具痕迹）+ `domain/workflow/MilestoneSpec.ts`（提醒判定） |
| `host/stage-prompts.ts` | 151 | `domain/stage/StagePromptSpec.ts`（提示词常量与阶段键仍是纯数据） |
| `host/capture.ts` `classifier.ts` `session-sync.ts` `stage-detail.ts` | 1,019 | 分流：规则进 `domain/`，渲染投影进 `application/query/`，会话 I/O 进 `adapters/` |
| `shared/protocol.ts` | 1,302 | 保留位置；**规则常量迁址 domain 后再导出**，纯 DTO 留在本文件 |
| `client/view.ts` | 2,579 | P1：按视图区分片（见 §6） |
| `client/styles.ts` | 1,886 | P1：分层样式 |

## 4. 设计模式选型（含对比与理由）

| 关注点 | 候选 | 选择 | 理由（含否掉的理由） |
|--------|------|------|---------------------|
| 持久化隔离 | 直调 store / Repository 端口 | **Repository（端口+适配器）** | 现 20 处 `store.mutate` 散在工具壳里，测试必须搭真 store。端口化后用例测试可用内存实现。否掉"直调"：正是 D3/D4 根因 |
| 用例组织 | 巨型 service / 一动作一用例 | **Use Case（一动作一模块）** | 13→9 个工具的动作总量约 12 个；一文件一事让"改一处只碰一处"成立。否掉巨型 service：会重演 agent-tools 的单点膨胀 |
| 复杂判定 | if 嵌套 / Specification | **Specification（返回 verdict 对象）** | done 凭证门、拆分幂等、acceptance 可证伪是"多条件组合判定"，Specification 可独立单测、可组合、返回结构化原因（拒绝理由要回给模型） |
| 状态合法性 | if/switch 散写 / 表驱动状态机 | **表驱动状态机（纯数据 + 两个查询函数）** | `REQ_TRANSITIONS`/`HUMAN_ONLY_*` 已存在于 protocol.ts，天然是表驱动。否掉 xstate：引入运行时依赖换不到收益，且要重写既有台账语义 |
| 产物分支 | 大 if / Strategy | **Strategy（按 `kind` 分派到独立用例）** | `reqboard_submit(kind)` 的 4 个分支各有不同闸门；Strategy 让"壳合并、逻辑不合并"，避免新的大 if（requirement.md §4.3 明文禁止） |
| 工具壳 | 各写各的 / Template Method | **Template Method（`core-tool` 的 BaseTool 三段式）** | 仓库已有规范包与 intelligence 先例；统一 validate/execute/错误码/渲染 |
| 领域事件 | 直接改数组 / 事件回放 | **直接改聚合 + 追加 statusHistory（沿用现状）** | 事件溯源收益（时点重建）当前无人消费，成本（快照/重放/迁移）极高。否掉 |
| DI 容器 | inversify/tsyringe / 手写端口注入 | **手写端口注入（构造参数）** | 依赖数量少且固定；容器会引入装饰器与反射、与 tsx 直载的组合未验证。否掉 |

**框架与库**：不新增任何运行时依赖。复用 `@pi-investment/core-tool`（BaseTool 三段式 + 错误类型）、`@deepseek-ai/dsh-tools`（defineTool）。**明确否掉**：nest/inversify（DI 过重）、xstate（状态机运行时）、zod（现有 normalize* + 手写 schema 已成体系，且 DSH 工具 schema 有自己的 DSL 铁律）。

## 5. 代码规范（本需求范围内强制）

1. **命名**：领域类型 PascalCase 且不带后缀噪声（`Requirement` 而非 `RequirementRecord`——`*Record` 是台账 DTO 的后缀，随 v5 迁到 `adapters` 侧）；规约以 `*Spec` 结尾；用例以动词短语（`MoveRequirement`）；端口以角色命名（`ReqboardRepository`）。
2. **纯函数优先**：`domain/` 内不得出现 `Date.now()`、`Math.random()`——时间与 ID 一律经参数传入（`Clock`/`IdFactory`），否则单测不可复现。
3. **错误**：沿用 `Object.assign(new Error(msg), { code })`；错误码常量集中在 `domain/errors.ts`（`REQBOARD_*`），适配层按 code 映射 HTTP 状态；消息内自带 code 文本（跨包 `instanceof` 不可靠）。
4. **判定返回结构化原因**：Specification 返回 `{ ok: true } | { ok: false; code; reason }`，禁止用 `return false` 丢信息（模型需要知道为什么被拒）。
5. **写操作单点**：台账写入只允许 `ReqboardRepository.mutate(reason, fn)` 一个入口，`reason` 必填（审计与调试用）。
6. **不变量守卫**：聚合上的非法操作抛错（`code=invalid_transition`），不做静默兜底（对齐 `standards/tool-development.md` 的"诚实失败"）。
7. **注释**：保留现有的"为什么"型注释（事故出处、权衡理由），删除与代码重复的"是什么"注释。迁移时**注释随代码一起搬**，不重写。

## 6. 前端设计（P1，纯机械拆分）

- `client/view.ts` 2,579 → `client/views/{board,stage-detail,stage-panel,verification,artifacts,timeline}.ts`（按当前渲染区切分）+ `client/render/dom-utils.ts`。
- `client/styles.ts` 1,886 → `client/styles/{base,board,detail,panel,files}.ts`，由 `styles.ts` 汇总导出（字符串常量合并，保持注入接口不变）。
- **接口不变**：`client/index.ts` 与 `board-mount.ts` 的对外行为、DOM 结构、类名、SSE 订阅方式一律不动。判定方式：`tests/client-view.test.ts` 与 `tests/stage-panel.test.ts` 的 DOM 断言必须全绿，且 `pnpm build:client` + `verify-client-build.mjs` 哨兵通过。
- 客户端可从 `shared/protocol.js` 直接引用 domain 规则（如"下一步可推进项"），消除前端本地复刻。

## 7. 与既有资产的关系

| 资产 | 用法 |
|------|------|
| `@pi-investment/core-tool` | BaseTool 三段式（validate/execute/metadata + prompt）、`ErrorType`、`sanitizeLossless` |
| `packages/intelligence` | 目录形状与命名（`domain/` `services/`→本需求用 `application/` `adapters/` `tools/<Name>Tool/`） |
| `docs/standards/tool-development.md` | schema 铁律、诚实失败、错误码约定 |
| `docs/standards/testing.md` | 测试与门禁规范 |
| `docs/architecture/workflow-stages.md` | 阶段职责唯一定义源（只改工具名引用，不改方法论） |

## 8. 明确不做（对齐 requirement.md N1-N5）

- 不改阶段方法论与流程语义；不改客户端视觉与交互；不新增功能；不引入新依赖；不做多需求并发/多租户。
- 不引入事件溯源、DI 容器、运行时状态机、schema 校验库。
