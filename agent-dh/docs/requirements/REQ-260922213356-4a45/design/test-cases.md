---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-8, FR-9, FR-10, FR-12]
---

# 测试用例（REQ-260922213356-4a45）

> 读者：实现与验证本需求的 agent/开发。本文只写「要测什么」；执行证据（命令+输出）在实施节点写
> `test-evidence.md`。用例从设计推导：**被测对象**列必须是 backend（S-x）/ interfaces（I-x）/
> data-model（T-x）/ use-cases（UC-x）里的真实编号——没有设计落点的用例 = 测空气。

## 测试数据设计方法 <!-- serves: FR-1 -->

- **等价类划分**：`(stage, category)` 划分为「该类型有模板 / 无模板 / 节点未启用」三类；
  `verdict` 划分为「affirmative / negative / undefined」三类。
- **边界值分析**：空集与单条目（0 vs 1 条模板）、地址段长度上限（< 2KB）、`relPath` 形态（合法 vs `..`）。
- **正交组合**：`{压缩开, 压缩关} × {肯定, 非肯定} × {有模板, 无模板}` 取关键组合，不穷举。
- **数据隔离**：测试用**临时目录**造模板文件与 `templateRoot`，不依赖生产 `templates/` 内容。
- **数据清理**：每条用例明细注明清理（删除临时目录 / 还原配置开关），避免污染。
- **真实映射表**：存在性/同源/漏配三条守护断言**必须对仓库真表跑**（不许用假表自证）。

## 优先级分级口径 <!-- serves: FR-1 -->

| 等级 | 定义 | 执行策略 |
|---|---|---|
| P0 | 核心链路：地址能产出、能读、不丢、非肯定不注入 | 每次必跑，阻塞发布 |
| P1 | 主流程关键功能：空集兼容、同源、记账 | 每次必跑 |
| P2 | 异常场景 / 边界：配置缺失、路径形态、并发 | 全量回归时跑 |
| P3 | 低概率 / 兼容性：legacy 需求、开关组合 | 版本发布前跑一轮 |

## 场景分类口径 <!-- serves: FR-1 -->

| 类型 | 说明 | 本需求示例 |
|---|---|---|
| 正向 | 正常走完的核心路径 | feature design 注入 5 份地址并被 read 成功 |
| 反向 | 输入错误、状态不合法、依赖不可用 | `templateRoot` 不可用、映射死链、非肯定项作答 |
| 边界 | 临界值、极值、空值 | 空集返空串、单条目、指针段长度上限 |
| 兼容回归 | 存量数据、历史版本、向后兼容 | legacy 无 artifacts 的需求；改造前基线逐字节比对 |

## 覆盖矩阵 <!-- serves: FR-1, FR-3, FR-4, FR-8 -->

| 功能点（FR-x） | 设计对象（I/S/T-x） | 覆盖用例（TC-x） | 单元测试 | 集成测试 | 故障注入 | 性能 | 安全 |
|---|---|---|---|---|---|---|---|
| FR-1 映射集中一处 | T-1, T-3 | TC-4, TC-5, TC-6 | ✅ | — | ✅ 漏配/死链 | N/A | — |
| FR-2 按节点与类型给地址 | S-1, I-1, T-3 | TC-1, TC-2, TC-3 | ✅ | — | ✅ 未启用节点 | N/A | ✅ 枚举收窄 |
| FR-3 与纪律同批送达 | S-3, S-4, I-3, I-4 | TC-9, TC-10 | ✅ | ✅ 三注入点 | ✅ 空集 | N/A | — |
| FR-4 空集不扰动 | I-3, I-4 | TC-8, TC-13 | ✅ | ✅ 基线比对 | ✅ 类型无模板 | N/A | — |
| FR-5 上游必读地址 | S-2, I-2 | TC-7 | ✅ | ✅ 台账投影 | ✅ 未登记产物 | N/A | ✅ 不跨需求读取 |
| FR-8 压缩后不丢且记账 | S-4, UC-3 | TC-9, TC-11 | ✅ | ✅ 两路径 | ✅ 系统段不可得 | ✅ 增量 < 2KB | — |
| FR-9 先答后确认 | UC-4 | TC-14 | ⚠️ 措辞断言 | ✅ 对话链路 | ✅ 超时不重弹 | N/A | — |
| FR-10 需修改不推着走 | S-6, I-5 | TC-10 | ✅ | ✅ 链路 | ✅ verdict=undefined | N/A | — |
| FR-12 压缩后再注入 | UC-3 | TC-11 | ✅ | ✅ 输入包 | ✅ 空集不追加 | N/A | — |

（说明：单元=函数级；集成=跨模块/注入点级；故障注入=降级路径/门禁/异常分支；性能=增量与时延；安全=越权/注入/路径穿越。N/A 均已注明理由。）

## 用例表 <!-- serves: FR-1, FR-2, FR-5, FR-9, FR-10 -->

| 用例 | 类型 | 优先级 | 被测对象 | 前置条件 | 步骤（简述） | 预期结果（可证伪） | serves | 责任人 | 自动化 | 实际文件 |
|---|---|---|---|---|---|---|---|---|---|---|
| TC-1 feature 设计节点给出 5 份模板地址 | 正向 | P0 | S-1 / I-1 | category=feature | 调 resolveNodeTemplates('design','feature') | 返回 5 条，含 architecture/data-model/interfaces/test-cases/use-cases，不含 migration | FR-2 | @窗口 | ✅ | tests/template-address.test.ts |
| TC-2 类型差异（refactor/bug） | 正向 | P0 | S-1 / I-1 | category=refactor / bug | 同上换类型 | refactor=architecture+migration；bug=空数组 | FR-2 | @窗口 | ✅ | tests/template-address.test.ts |
| TC-3 未启用节点返回空集 | 边界 | P1 | S-1 / I-1 | spike 的 design 节点禁用 | 调 resolveNodeTemplates('design','spike') | 返回 []（且不抛错） | FR-2 | @窗口 | ✅ | tests/template-address.test.ts |
| TC-4 映射表每条路径存在 | 正向 | P0 | T-1 / T-3 | 仓库真表 | 遍历全部 relPath 断言 existsSync | 全部为真；有一条假 → 失败 | FR-1 | @窗口 | ✅ | tests/template-address.test.ts |
| TC-5 映射与门禁文档集一致 | 正向 | P0 | T-1 / T-3 | 仓库真表 | 与 effectiveDesignDocs 双向比对 | 完全一致（多/少各报一条） | FR-1, FR-7 | @窗口 | ✅ | tests/template-address.test.ts |
| TC-6 漏配检测 | 反向 | P1 | T-1 / T-3 | 临时目录多一份未引用模板 | 跑漏配断言 | 报出该文件名（失败信息含路径） | FR-1 | @窗口 | ✅ | tests/template-address.test.ts |
| TC-7 实施节点上游必读地址齐全 | 正向 | P0 | S-2 / I-2 | 台账有 requirement+design+plan+任务卡 | 调 resolveUpstreamDocs(req,'implementing',task) | 四类地址齐全，且 path 全部 ∈ 台账 | FR-5 | @窗口 | ✅ | tests/template-address.test.ts |
| TC-8 空集返空串 | 边界 | P0 | I-3 / I-4 | 无模板且无上游 | 渲染并 augment | render=''；augment 返回**同一对象引用** | FR-4 | @窗口 | ✅ | tests/template-address.test.ts |
| TC-9 三注入点地址段逐字一致 | 正向 | P0 | S-4 / I-4 | 同一 (stage,category,req) | 分别取系统段/H3/输入包三处文本 | 三处地址段逐字节相等 | FR-3, FR-8 | @窗口 | ✅ | tests/template-address-injection.test.ts |
| TC-10 非肯定项不注入下一节点纪律 | 反向 | P0 | S-6 / I-5 | ctx.verdict=negative | 跑 H3 与 H4 | H3=skip(negative_verdict) 且 scratch.promptText 未写；H4 文本不含纪律特征串 | FR-10 | @窗口 | ✅ | tests/template-address-injection.test.ts |
| TC-11 压缩后再注入含同一地址 | 正向 | P0 | S-7 / UC-3 | 压缩开/关两路径 | 取两路径的模型可见面 | 两路径地址段逐字一致；留痕 charCount 含地址段 | FR-8, FR-12 | @窗口 | ✅ | tests/template-address-injection.test.ts |
| TC-12 地址可读性（真 read） | 正向 | P0 | I-3 | 渲染出的每条地址 | 对每条路径执行 read | 全部成功打开（非空内容） | FR-2 | @窗口 | ✅ | tests/template-address.test.ts |
| TC-13 老基线逐字节不变 | 兼容回归 | P1 | I-3 / I-4 | 空集场景 | 比对改造前后注入文本（含既有 tests/prompt-baseline.test.ts 快照不变） | sha256 相等 | FR-4 | @窗口 | ✅ | tests/template-address.test.ts |
| TC-14 提问先答、弹框只在闸门一次 | 正向 | P1 | UC-4 | 有进行中需求、产物未定稿 | 用户连问 3 次；随后文字"确认" | 提问 3 次弹框 0 次；文字确认落章推进且零弹框 | FR-9 | @窗口 | ⚠️ | tests/template-address-injection.test.ts |

（自动化口诀：✅可自动化 / ⚠️半自动（需人工确认措辞或真实弹框通道） / ❌只能手动。）

## 用例明细 <!-- serves: FR-1, FR-4, FR-8, FR-12 -->

### TC-4 映射表守护（存在性 / 同源 / 漏配） <!-- serves: FR-1, FR-7 -->

- **测试数据**：
  - 仓库真表 `NODE_TEMPLATES`（不 mock）；
  - 临时目录 fixture：`tmp/tpl/design/architecture.md`（存在）、`tmp/tpl/design/ghost.md`（表引用但不存在）、`tmp/tpl/design/orphan.md`（存在但无人引用）。
- **步骤**：
  1. 对真表逐条断言 `existsSync(path.join(realRoot, relPath))`；
  2. 对真表与 `effectiveDesignDocs(category, sides)` 双向比对（表 ⊆ 门禁 且 门禁 ⊆ 表）；
  3. 用 fixture 跑"死链"与"漏配"两条断言，确认会失败（故障注入）。
- **断言点**：
  1. ✅ 全部 relPath 存在；
  2. ✅ 与门禁文档集一致（差异逐条列出，非布尔吞掉）；
  3. ✅ fixture 死链 → 失败信息含 `ghost.md` 与完整路径；
  4. ✅ fixture 漏配 → 失败信息含 `orphan.md`；
  5. ✅ 测试耗时 < 200ms（纯文件存在性检查）。
- **清理**：删除临时 fixture 目录；不改真表。

### TC-9 三注入点一致性 <!-- serves: FR-3, FR-8 -->

- **测试数据**：合成需求 `REQ-test`（artifacts 含 requirement.md 与 design/*.md）、`templateRoot='/tmp/tpl'`、`stage=design`、`category=feature`。
- **步骤**：
  1. 取系统段：`boundSectionText(ledger, context, injectionLog)`；
  2. 取 H3：跑 `createH3InjectHandler`，读 `scratch.promptText`；
  3. 取输入包：`buildNodeInputPackage({...})`；
  4. 三处分别抽地址段（以「## 本节点文档」起、至段末）。
- **断言点**：
  1. ✅ 三处地址段字符串完全相等（含标点与换行）；
  2. ✅ 三处均出现同一组绝对地址（`templateRoot` 前缀一致）；
  3. ✅ 留痕记录 `charCount` = 增强后文本长度（≠ 原 `resolved.charCount`）；
  4. ✅ 空集输入下三处都**不出现**「## 本节点文档」标题。
- **清理**：删除合成需求与临时 `templateRoot`。

### TC-11 压缩后再注入 <!-- serves: FR-8, FR-12 -->

- **测试数据**：同 TC-9 的合成需求；`nodeIsolation` 分别设 false/true（两轮）。
- **步骤**：
  1. 压缩关：走 H3 → H4 全文路径，取投递文本；
  2. 压缩开：走 H2 压缩 → `buildNodeInputPackage`，取输入包文本；
  3. 抽两处地址段比对。
- **断言点**：
  1. ✅ 两路径地址段逐字相等；
  2. ✅ 输入包文本含「## 本节点文档」小节，且位于「## 需求文档」之后；
  3. ✅ 系统段路径与输入包路径的地址**同时**存在（双落点）；
  4. ✅ 模拟"系统段不可得"（boundSectionText 返回 ''）→ 输入包仍带地址段。
- **清理**：还原 `nodeIsolation` 配置到测试前值。

## 验收命令（可执行） <!-- serves: FR-1, FR-4, FR-10 -->

~~~bash
cd packages/web/dsh-pmboard

# ① 地址解析 + 映射表守护（TC-1~8、TC-12、TC-13）
npx vitest run tests/template-address.test.ts

# ② 三注入点 / 压缩两路径 / 非肯定分流 / 确认门守卫（TC-9~11、TC-14）
npx vitest run tests/template-address-injection.test.ts

# ③ 兼容基线：空集时老提示词逐字不变（应保持绿）
npx vitest run tests/prompt-baseline.test.ts tests/stage-prompts.test.ts

# ④ 肯定分支防修反：G1 确认后仍注入 design 档
npx vitest run tests/h3-inject.test.ts

# ⑤ 若改了 fragments 源，生成物必须同步
node scripts/check-prompt-fragments.mjs

# ⑥ 类型门禁
pnpm typecheck
~~~

**期望输出**：① ~ ⑥ 全绿（P0 全过；④⑤⑥ 为配套回归门）。

**反面验收（必做的故障注入，不通过即为验收不完整）**：
1. 把 `templateRoot` 由绝对路径改为仓库根相对（如 `'templates'`）→ ① 的 TC-12 必须**变红**；
2. 删掉映射表里一条 `relPath` 对应的模板文件 → ① 的 TC-4 必须**变红**（不是运行时兜底）；
3. 临时给 `templates/` 放一份无人引用的 `.md` → ① 的 TC-6 必须**变红**；
4. 把地址段只挂 H3、不挂输入包 → ② 的 TC-11 必须**变红**；
5. 令 `ctx.verdict='negative'` → ② 的 TC-10 必须断言到 `skip(negative_verdict)` 且 `scratch.promptText` 未写。

## 故障注入 <!-- serves: FR-2, FR-4, FR-8, FR-10, FR-12 -->

### 参数异常 <!-- serves: FR-2, FR-4 -->

| 注入点（挂设计编号） | 故障场景 | 注入方式（怎么造故障） | 预期行为（系统怎么处理） | 实测结果 |
|---|---|---|---|---|
| S-1 resolveNodeTemplates | stage 非法值 | 传 `'design2'` | 收窄失败 → **响亮抛错**（不静默当通配） |  |
| S-1 | category 非法值 | 传 `'feature2'` | 响亮抛错 |  |
| S-3 renderAddressSection | relPath 含穿越 | fixture 表里放 `'../../etc/passwd'` | 渲染前断言拒绝（失败信息含该串） |  |
| S-3 | templateRoot 非绝对路径 | 传 `'templates'`（相对） | 组合根判不可用 → 整段不注入 + `address_section_disabled` 留痕 |  |

### 状态异常 <!-- serves: FR-10 -->

| 注入点 | 故障场景 | 注入方式 | 预期行为 | 实测结果 |
|---|---|---|---|---|
| S-6 H3 分流 | verdict undefined | 构造 `ctx` 不设 verdict | 按 negative 处理：skip，不注入 |  |
| S-6 | verdict negative | 令台账 status ≠ ctx.to | skip(negative_verdict)；scratch.promptText 保持 undefined |  |
| S-2 | 需求已完成/归档 | 传 status=done 的需求 | 上游清单为空（合法态），不报错 |  |

### 依赖异常 <!-- serves: FR-5, FR-8 -->

| 注入点 | 故障场景 | 注入方式 | 预期行为 | 实测结果 |
|---|---|---|---|---|
| S-1 | 映射表指向文件不存在 | 临时改表加一条死链 | 守护单测红（TC-4）；运行时返回该条但不兜底 → 由红灯暴露 |  |
| S-2 | 台账产物未登记 | 造 artifacts=[] 的 legacy 需求 | 上游清单为空，地址段只含模板块（或全空） |  |
| 组合根 S-5 | 包根解析失败 | mock 模块位置指向不存在目录 | `templateRoot=undefined` → 地址段整体不注入 + 留痕；不抛崩 |  |

### 并发 / 幂等 <!-- serves: FR-3, FR-8 -->

| 注入点 | 故障场景 | 注入方式 | 预期行为 | 实测结果 |
|---|---|---|---|---|
| S-3/S-4 | 同一输入重复渲染 | 连续调 3 次 | 输出逐字节相同（纯函数幂等） |  |
| S-4 | 空集重复调用 | 连续调 3 次 | 每次都返回**同一入参引用** |  |
| S-6 | 同一闸门重复触发链 | 同 (windowKey,gate) 触发 2 次 | 既有幂等保证下只注入一次（不重复弹框、不重复留痕） |  |

### 权限异常 <!-- serves: FR-5 -->

| 注入点 | 故障场景 | 注入方式 | 预期行为 | 实测结果 |
|---|---|---|---|---|
| S-2 resolveUpstreamDocs | 跨需求读取 | 传入非本窗口绑定需求的 requirement | 上游只从传入对象取；工具层越权在既有 reqboard 校验，本函数不额外放行 |  |
| S-3 | 地址泄露他人需求路径 | 同上 | 测试断言：地址段只含传入需求的 path |  |

### 网络异常 <!-- serves: FR-3 -->

| 注入点 | 故障场景 | 注入方式 | 预期行为 | 实测结果 |
|---|---|---|---|---|
| 全链 | N/A | 本需求全为进程内纯函数，无网络依赖 | 不适用（无网络可注入） | N/A |

## 非功能测试（按需填写） <!-- serves: FR-3, FR-13 -->

| 维度 | 用例 | 指标 | 结果（实施时回填） |
|---|---|---|---|
| 性能 | TC-P1 单次注入增量 | 地址段长度 < 2KB（feature design 6 条 + 上游 4 条） |  |
| 性能 | TC-P2 解析+渲染耗时 | < 1ms（纯函数、零 I/O） |  |
| 兼容 | TC-C1 legacy 需求 | artifacts 为空时不报错且地址段合法（模板块可空） |  |
| 兼容 | TC-C2 基线逐字节 | 空集场景 sha256 与改造前一致 |  |
| 安全 | TC-S1 路径穿越 | `..` / 绝对路径 relPath 被拒 |  |
| 安全 | TC-S2 越权读取 | 地址段只含传入需求的 path |  |
| 容灾 | TC-R1 templateRoot 不可用 | 不崩、不静默：留痕 + 回退改造前行为 |  |

---
## 评审记录 <!-- serves: FR-1 -->

- **评审人**：
- **评审日期**：
- **评审结论**：通过 / 修订后通过 / 打回
- **评审意见**：
