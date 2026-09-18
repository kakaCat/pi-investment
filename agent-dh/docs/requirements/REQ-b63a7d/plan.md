# REQ-b63a7d 实施计划：reqboard 文档路径口径统一（消除 403 误报与产物路径错层）

> 分类：bug（`CATEGORY_FLOW_PROFILES.bug`：免需求分析门；业务文档 + 复现定位即上下文，并入本修复方案）。

## 一、现象与复现（证据）

控制台报错：

```
GET http://127.0.0.1:13080/dashboard/api/reqboard/file?path=agent-dh%2Fdocs%2Farchitecture%2Fdocumentation-standard.md 403 (Forbidden)
```

- 服务端响应体（curl 实测）：`{"success":false,"error":"仅允许访问工作区 docs/ 目录","code":"forbidden"}` —— 是白名单守卫，**不是**鉴权/缺 token。
- 对照实测：同一文件用 `docs/architecture/documentation-standard.md` 请求 → **200**；同一端点无任何 token 参数也返回 200。
- 触发方：`packages/pages/dsh-pmboard/src/client/board-mount.ts` 的 `verifyDocExistence()`（第 563-586 行，构建产物 `lib/client.js:678`），对详情页每个 `[data-doc-path]` 发存在性预检。

## 二、根因

`packages/pages/dsh-pmboard/src/http/routers/artifacts.ts` 的 `handleFileRead()`：

1. 只允许 `<进程 cwd>/docs/**`（第 29-33 行），且**先判白名单、后读文件** —— 路径不落在 `docs/` 内一律 403，即便文件真实存在。
2. 实测 DSH 实例 cwd = `/Users/yunpeng/pi-investment/agent-dh`（pid 2266，`lsof`）。
3. 台账 `.dsh-data/dsh-reqboard.json` 里的产物路径由 `reqboard_task_report` 把 `files_changed` **原样**上浮（`src/application/use-cases/ReportTask.ts` 第 134-143 行），无任何口径归一 → 仓库根相对/绝对/跨仓/伪路径全都进了台账。

于是 `agent-dh/docs/...` 被解析成 `<cwd>/agent-dh/docs/...`：既落白名单外、文件也不存在 → 403（而非 404）。

**真实缺陷是"产物路径口径"与"文件接口可服务范围"两端不一致**：REQ-2e9473 t12 让`改动文件上浮`把**源码文件**也登记为产物，而唯一能读文件的接口只认 `docs/` —— 所以这不是一条脏数据，而是**全量源码类产物都会被判"缺失"+控制台报错**。

## 三、范围盘点（台账实测，142 条非合规路径）

| 形态 | 样例 | 来源 | 后果 |
|---|---|---|---|
| A 工作区名前缀 | `agent-dh/docs/...`、`agent-dh/packages/...` | REQ-a33899 / REQ-d3e61a | 解析多套一层 → 403 |
| B 绝对路径 | `/Users/yunpeng/pi-investment/agent-dh/packages/...` | REQ-422af1 | 403 |
| C 跨仓相对路径 | `quantsys-v2/adapters/...` | REQ-c9f899 | 位于工作区外，本接口永远不可服务 |
| D 伪路径（brace-glob 汇总写法） | `quantsys-v2/tests/{a.py,b.py}` | REQ-c9f899 | 不是文件，永远 404/403 |

另有**合规但非 docs** 的源码路径（`packages/...`、`tests/...`）—— 它们同样被 docs-only 白名单拒绝。

## 四、设计口径（建议方案）

1. **登记口径统一**：产物路径一律登记为**工作区相对路径**（相对 DSH 会话工作区根）。
2. **归一层（domain 纯函数）** `normalizeArtifactPath(raw)`：反斜杠→`/`；剥离绝对前缀（工作区根/仓库根）；剥离重复的工作区名前缀；判定伪路径（含 `{}`、`*`）→ 标记 `pseudo` 而非静默保留。
3. **可打开性由 host 单点判定**：host 用同一解析器算出 `openable` 并随产物下发；前端**只对 openable 产物**做存在性预检与可点击渲染（消除双端两套口径，也消除噪声根源）。
4. **文件接口语义修正**：allowlist 由 `<cwd>/docs` 放宽到 **`<cwd>`（工作区根）**，保留"仅相对路径 + 拒 `..`/`\\`/绝对路径"的穿越防护；解析后不在工作区内 → **404 + code=outside_workspace**（不再用 403 冒充权限问题）；归一兜底以兼容存量记录。
5. **存量清理**：一次性归一 + 剔除伪路径（备份 + 报告 + 幂等），保留正确前缀的那一份去重。

## 五、任务表

见提交的计划任务表（t1–t7）。

## 六、验收判据

- A1：`?path=agent-dh/docs/architecture/documentation-standard.md` 与 `?path=docs/architecture/documentation-standard.md` 均 200（同一文件）。
- A2：`?path=../../etc/passwd`、`?path=/etc/passwd` 仍 403（穿越防护未被放宽）。
- A3：`?path=quantsys-v2/main.py`（工作区外）返回 404 + `outside_workspace`，不再 403。
- A4：详情页源码类产物不再被标 `is-missing`、控制台无 403；不可打开的跨仓/伪路径以纯文本 + 原因呈现，且**不发预检请求**。
- A5：新 `reqboard_task_report` 写入的产物路径 100% 为工作区相对真实路径（写入侧归一使然）。
- A6：存量台账归一后，全量扫描"非工作区相对 + 非伪路径"计数为 0；备份与报告留痕。
- A7：`npx vitest run` 全绿（含新增故障注入）；`pnpm build:client` + `verify-client-build.mjs` 通过。

## 七、风险与协调

- **同包在飞**：REQ-47939a（本包分层重构）、REQ-d3e61a（任务卡门禁）。改动集中在本包 `src/`；按最小 hunk 落点，避开在飞文件；冲突以对方为准并 rebase。
- **放宽 allowlist 的安全面**：仍限工作区内、仍拒绝对路径与穿越；接口仅本地 dashboard 暴露，不新增外网面。
- **部署会中断会话**：本包改动需重启 :13080 才生效（launchd 托管），须先落 pending-resume（既有机制）再重启，重启后核验 A1–A4。
- 不改动 quantsys-v2 仓库；跨仓路径（形态 C）只做"不可打开"的诚实例外呈现。
