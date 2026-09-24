---
requirement_refs: [FR-2, FR-3, FR-7, FR-8, FR-12, FR-13]
---

# 架构设计（REQ-260922213356-4a45）

> 读者：工程/agent。本份讲"模板地址怎么进节点提示词、经过哪些模块、压缩后为什么还在"。
> 一句话目标：在**不改注入通道**的前提下，让每次节点注入的文本里带上「本节点要产什么（模板地址）」
> 与「开工前要读什么（上游产物地址）」，且空集时与改造前逐字节一致。

## 整体架构 <!-- serves: FR-2, FR-3, FR-7 -->

```
   templates/ 模板包（既有 23 份，插件包内）
        │  （相对名，静态引用；不运行时扫盘）
        ▼
┌──────────────────────────────────────────────┐
│ domain/template（纯函数，零 I/O）              │
│  ├ NODE_TEMPLATES  节点×类型 → TemplateRef[]   │
│  ├ resolveNodeTemplates(stage, category)       │
│  ├ resolveUpstreamDocs(req, stage, task?)      │
│  └ renderAddressSection(input)                 │
└──────────────────────────────────────────────┘
        │  地址段文本（空集 = 空串）＋ templateRoot（组合根注入的绝对路径）
        ▼
┌──────────────────────────────────────────────┐
│ application（装配，不新增通道）                │
│  augmentResolvedPrompt(resolved, input)        │
│   = resolved.text + 地址段（空集恒等）         │
└──────────────────────────────────────────────┘
        │
        ├──────────────► ① capture-section.boundSectionText（系统提示词段，每回合重装）
        ├──────────────► ② gate/handlers/h3-inject（闸门后置链；先判 verdict）
        └──────────────► ③ internal/node-input-package（节点边界后的唯一可见面）
        │
        ▼
   模型可见面 = 系统段 + 输入包/唤醒消息（两处都含同一份地址段）

   守护单测 tests/template-address.test.ts
     ├ 逐条 relPath existsSync
     ├ 映射与门禁文档集（effectiveDesignDocs）逐项一致
     └ templates/ 下未被任何条目引用 → 报红（漏配）
```

关键性质（可证伪）：
- **不改注入通道**：HANDLER_ORDER 不变、不新增系统提示词段、不引入运行时读盘。
- **单源**：三处注入点共用一个纯函数（无第二份文案），地址映射与门禁同源（FR-7）。
- **两路径同址**：压缩开/关两条路径拿到的地址段逐字一致（FR-8）。

## 技术选型 <!-- serves: FR-1, FR-13 -->

### 地址来源：代码内静态映射表（不是构建期生成器） <!-- serves: FR-1 -->

**选型**：`src/domain/template/registry.ts` 一张按「节点 × 类型」组织的静态常量表；相对名 + 配置的模板根 → 绝对路径。

**理由**：
- 注入用的是**地址字符串**，不需要跑任何脚本即可产出 → 生成器的产物（路径索引常量）对目标无增量。
- 生成器唯一的价值是"防死链 / 防漏配"，这两点由一个守护单测即可覆盖（复杂度更低）。
- 表格内容与门禁文档集（`effectiveDesignDocs` 等）逐项对齐即可保证不漂移（FR-7）。

**替代方案对比**：

| 方案 | 优点 | 缺点 | 为什么不选 |
|---|---|---|---|
| 构建期生成器（扫 templates/ 生成常量 + check 脚本） | 源改未重跑可被 CI 拦 | 多两个脚本、多一份生成物、多一条"忘了重跑"的失败路径 | 目标只要地址；死链/漏配用单测即可拦，砍掉更简单 |
| 运行时扫盘（fs.readdir(Sync)） | 永远与磁盘一致 | 注入点变成有 I/O、需要 fs 白名单、domain 层被污染 | 注入点必须是纯函数；且浏览器端不可用 |
| 手写地址散落在各注入点 | 无新模块 | 三处各写一份必然漂移（本仓"两份真相"教训） | 与 FR-7 同源要求直接冲突 |

**技术风险与缓解**：
- 风险：模板改名/新增时忘了同步映射表 → 注入指向不存在的文件。
- 缓解：守护单测三条断言（存在性 / 与门禁一致 / 漏配）直接变红，红灯替代构建期脚本。

### 交付形态：指针段（skill 式），不是模板全文 <!-- serves: FR-13 -->

**选型**：常驻注入的只有「人读名 + 一句话用途 + 绝对地址」（指针行），模板正文由窗口按需 `read` 打开。

**理由**：模板包 107KB，全文进提示词会在每次压缩后重放（成本不恒定）；指针段 < 2KB 且**不随模板体量增长**（FR-13）。

**替代方案对比**：

| 方案 | 优点 | 缺点 | 为什么不选 |
|---|---|---|---|
| 模板全文进提示词 | 窗口不必再打开文件 | 单次约 65KB（≈2 万 token）；压缩后仍需重放 | 成本不恒定，且与本需求的"地址"目标无关 |
| 模板落盘到需求目录 | 文档就地可读 | 属另一窗口在途改造；会与模板包形成两份真相 | 超出本需求边界（非目标 N2） |
| 指针段 + 按需 read（选中） | 成本恒定、地址可核验 | 依赖窗口真的去 read | 不装"强制读取门禁"（无法机械证伪，见 N3）；靠纪律句 + 验收实读 |

## 模块职责 <!-- serves: FR-2, FR-3, FR-7 -->

### 地址解析层：`src/domain/template/` <!-- serves: FR-2, FR-5, FR-7 -->

**做什么**：
1. 按 `(stage, category)` 从 `NODE_TEMPLATES` 取该节点该类型应产出的模板条目；
2. 按 `(requirement, stage, task)` 从台账投影取上游必读产物（requirement.md / design/*.md / decomposition.md / 任务卡）；
3. 用 `templateRoot + relPath` 拼绝对路径，渲染成指针行文本。

**不做什么**：
- 不读盘（存在性由守护单测覆盖）；
- 不 import `node:` / `@deepseek-ai/`、不碰时间与随机数（domain 层硬约束，`tests/layer-boundary.test.ts` 机械检查）；
- 不读环境变量（`templateRoot` 由组合根注入）；
- 不决定"要不要注入"（节点是否启用由调用方先过 `stageEnabledFor` 闸）。

**对外接口**：`resolveNodeTemplates` / `resolveUpstreamDocs` / `renderAddressSection`（签名见 interfaces.md）。
**依赖关系**：弱依赖门禁规则模块的类型常量（`effectiveDesignDocs` / `STAGE_ARTIFACT_REQUIREMENTS`，只读语义，单向）。
**状态管理**：无状态。

### 注入段装配层：`src/application/internal/injection-address.ts` <!-- serves: FR-3, FR-4, FR-8 -->

**做什么**：把地址段拼进 `ResolvedPrompt`（`augmentResolvedPrompt`），使留痕的 `charCount` 含地址段；
空集时**原样返回**（同一对象引用或等值对象），保证 FR-4 逐字节兼容。

**不做什么**：不新增注入通道、不改 HANDLER_ORDER、不碰预算裁剪默认值。

**依赖关系**：强依赖 domain/template；被三个注入点调用。

### 三个注入点（改动点） <!-- serves: FR-3, FR-8, FR-12 -->

| 注入点 | 现状 | 改动 |
|---|---|---|
| `application/internal/capture-section.ts` `boundSectionText` | 阶段纪律 `resolved.text` 直接入段 | 纪律文本后追加地址段；留痕 `charCount` 用增强后的值 |
| `application/gate/handlers/h3-inject.ts` | 一律按 `ctx.to` 取词 | ① 先判 `ctx.verdict`：非肯定项 → `skip(negative_verdict)`，不取词、不写 scratch、不留痕；② 肯定项取词后追加地址段 |
| `application/internal/node-input-package.ts` `buildNodeInputPackage` | 内容 = 路由提示词 + 需求文档投影 + 台账投影 | 追加「本节点文档（模板地址 / 上游必读）」小节（同一纯函数产出） |
| `application/gate/handlers/h4-resume.ts`（配套） | 非肯定项也附"阶段纪律已随输入包给出"兜底句 | 非肯定分支**不附任何纪律块**，只发作答摘要 + 用户意见（FR-10） |

### 守护单测：`tests/template-address.test.ts` <!-- serves: FR-1, FR-6, FR-7 -->

**做什么**：断言映射表三条性质（路径存在 / 与门禁文档集逐项一致 / 目录内无未引用模板）。
**不做什么**：不在运行时代偿（运行时遇缺失只返回空集 + 留痕，不臆造地址）。

## 部署架构 <!-- serves: FR-3, FR-8 -->

- **落点**：一切改动都在 `packages/web/dsh-pmboard` 包内，无新服务、无新端口、无新进程。
- **模板根解析**：组合根（`src/index.ts`）按自身模块位置解析包根下 `templates/`（源码态 `src/index.ts` → `../templates`；构建态 `dist/index.mjs` → `../templates`，两态同解）；
  可被插件配置 `templateRoot`（绝对路径）覆盖，便于 worktree / 多实例部署。
- **配置项**：`templateRoot?: string`、`addressSectionEnabled?: boolean`（默认 `true`）。关闭 = 完全回退到改造前行为。
- **生效路径**：改源码后 dsh-pmboard 从 `dist/index.mjs` 加载（`package.json main` 指向 dist）→ 须 `pnpm build` 后重启，光重启无效。
- **扩缩性**：单进程内存常量，无扩展性问题；不引入跨实例状态。

## 安全考量 <!-- serves: FR-2, FR-5 -->

- **鉴权**：无网络边界（进程内纯函数），不涉及鉴权；上游地址的越权面沿用既有 reqboard 工具层。
- **输入来源**：地址只由**代码常量 + 配置根**产生，不拼接任何用户输入 → 无注入面。
- **路径遍历**：相对名固定于映射表，不含 `..`；守护单测可加断言拒绝含 `..` / 绝对路径的相对名。
- **敏感数据**：地址段只含模板与需求文档路径，不含业务数据、凭证或持仓。
- **不执行内容**：模板正文不进入进程、不被求值，只作为地址字符串交付。

## 监控与告警 <!-- serves: FR-8, FR-10 -->

| 观测面 | 指标 | 现状 | 目标 |
|---|---|---|---|
| 注入留痕（`state/prompt-injection-log.json`） | `charCount` 是否含地址段 | 不含 | 含；单次增量 < 2KB |
| 注入留痕 | 地址段是否出现在系统段与输入包两处 | 无地址段 | 两路径逐字一致 |
| 闸门链 | 非肯定项取词跳过（BUR-3） | 未记录 | 非肯定作答 100% `skip(negative_verdict)` |
| 守护单测 | 映射漏配 / 死链失败次数（BUR-2） | 0（无测试） | 期望 0；红即问题暴露 |
| 告警 | 映射漏配 → 开发期红灯；不新增运行时告警 | — | 运行时不因地址缺失告警（空集是合法态，走既有降级留痕） |

## 实现落点校准（T-8，2026-09-22 实施后回填） <!-- serves: FR-6 -->

落点与本文的差异以本表为准（图与代码一致由此校准）：

| 设计名 | 实际落点 | 说明 |
|---|---|---|
| S-1/S-2 resolve | `src/domain/template/resolve.ts` | 纯函数；**门禁同源由守护单测断言**（表只登记启用组合，禁用组合自然空集），未运行时 import `stageEnabledFor`/`effectiveDesignDocs`（跨层，见下） |
| S-3 render | `src/domain/template/render.ts` | 空集返空串；非绝对 `templateRoot` 响亮抛错 |
| S-4 augment | `src/application/internal/injection-address.ts` | 空集返原引用 |
| S-5 模板根 | `src/adapters/TemplateRoot.ts`（`resolveTemplateRoot` / `resolveAddressInjection`） | `node:path` 仅在此；`address_section_disabled` 留痕 |
| S-6 verdict 分流 | `src/application/gate/handlers/h3-inject.ts` 内联（`ctx.verdict !== 'affirmative' → skip(negative_verdict)`） | 未单独导出 `resolveStagePromptForGate`；语义与 I-5 一致 |
| S-7 输入包地址节 | `src/application/internal/node-input-package.ts` `renderAddressFor` + `IsolateNodeContext.ts` 传参 | 位于「## 需求文档」之后 |
| 类型契约 | `src/domain/template/types.ts`（`TemplateRef`/`DocRef`/`UpstreamSource`/`AddressSectionInput`） | 上游投影用 **domain 局部结构类型**（不 import shared，保持层边界） |
| 守护单测 | `tests/template-address.test.ts`（26 例）、`tests/template-address-injection.test.ts`（10 例） | 存在性 / 同源 / 漏配 / 矩阵对照 / 注入一致性 |

**层边界修正（为什么不是运行时同源）**：`stageEnabledFor` 在 `shared/protocol.ts`、`effectiveDesignDocs` 在
`application/internal/`，二者都不在 `domain/` 允许的依赖方向内（`tests/layer-boundary.test.ts`）。
故同源改为「表只登记启用组合（表成员即门禁）+ 守护单测双向断言」，等价性由 `tests/template-address.test.ts`
的矩阵对照与 `(design,*) == effectiveDesignDocs` 断言机械保证。
