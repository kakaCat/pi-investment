# REQ-b63a7d 需求文档（bug · 复现定位 + 修复方案）

> bug 分类免"需求分析门"：本文件即"业务文档 + 复现定位"，与修复方案合并。

## 1. 现象

需求详情页/看板打开时，浏览器控制台报：

```
GET http://127.0.0.1:13080/dashboard/api/reqboard/file?path=agent-dh%2Fdocs%2Farchitecture%2Fdocumentation-standard.md 403 (Forbidden)
```

## 2. 复现与证据（R-013 标注来源与时点）

| 步骤 | 命令/位置 | 结果 |
|---|---|---|
| 复现 403 | `curl -i 'http://127.0.0.1:13080/dashboard/api/reqboard/file?path=agent-dh%2Fdocs%2Farchitecture%2Fdocumentation-standard.md'`（2026-09-18 15:24 本机实测） | 403 `{"success":false,"error":"仅允许访问工作区 docs/ 目录","code":"forbidden"}` |
| 对照 | 同端点 `?path=docs%2Farchitecture%2Fdocumentation-standard.md` | **200** |
| 排除鉴权 | 同端点无任何 token/cookie 参数 | **200**（另有 `/dashboard/api/reqboard/` 同为 200） |
| 文件确实存在 | `ls docs/architecture/documentation-standard.md` | 36116 字节，存在 |
| 进程工作区 | `lsof -p 2266`（:13080 LISTEN pid） | `cwd=/Users/yunpeng/pi-investment/agent-dh` |

**结论：与 token 无关。** 插件里的"token"指 LLM token 用量（🪙 Token tab，REQ-a33899），与鉴权无关。

## 3. 根因

两端口径不一致：

1. **服务端**：`packages/pages/dsh-pmboard/src/http/routers/artifacts.ts` 的 `handleFileRead()` 只允许 `<cwd>/docs/**`，且**先判白名单后读文件** → 不在 docs 下一律 403（即便文件真实存在）。
2. **登记端**：`src/application/use-cases/ReportTask.ts`（第 134-143 行）把 `files_changed` **原样**登记为 `task_output` 产物，无口径归一。
3. **前端**：`src/client/board-mount.ts` 的 `verifyDocExistence()` 对每个 `[data-doc-path]` 发预检 → 把 403 当作"缺失"，并留下控制台报错。

## 4. 范围（台账实测：142 条非合规路径）

`.dsh-data/dsh-reqboard.json`（schemaVersion 6 / revision 1420）扫描结果：

- **A 工作区名前缀**：`agent-dh/docs/...`、`agent-dh/packages/...`（REQ-a33899 / REQ-d3e61a）
- **B 绝对路径**：`/Users/yunpeng/pi-investment/agent-dh/packages/...`（REQ-422af1）
- **C 跨仓相对路径**：`quantsys-v2/...`（REQ-c9f899）——位于工作区之外，本接口永远不可服务
- **D 伪路径（brace-glob 汇总写法）**：`quantsys-v2/tests/{a.py,b.py}`——根本不是文件

外加**合规但非 docs 的源码路径**（`packages/...`、`tests/...`）：REQ-2e9473 t12"改动文件上浮"引入了源码类产物，而唯一能读文件的接口只认 `docs/` → **全量源码类产物都会被判"缺失"+报错**。

## 5. 修复方案（详见 plan.md §四）

1. 登记口径统一为**工作区相对路径**；新增 domain 归一层 `normalizeArtifactPath`。
2. **可打开性由 host 单点判定**并随产物下发；前端只对 openable 产物预检/可点击。
3. 文件接口 allowlist 由 `<cwd>/docs` 放宽到 **`<cwd>`（工作区根）**，保留穿越防护；工作区外返回 **404 + outside_workspace**（不再用 403 冒充权限问题）。
4. 存量一次性归一 + 剔除伪路径（备份 + 报告 + 幂等）。

## 6. 验收（可证伪）

- A1 `?path=agent-dh/docs/architecture/documentation-standard.md` → 200（与 `docs/...` 同结果）
- A2 `?path=../../etc/passwd`、`?path=/etc/passwd` → 仍 403
- A3 `?path=quantsys-v2/main.py` → 404 + `outside_workspace`
- A4 详情页源码类产物不再被标 `is-missing`，控制台无 403
- A5 新 `task_report` 写入路径 100% 工作区相对
- A6 存量扫描"非工作区相对 + 非伪路径"计数为 0
- A7 `npx vitest run` 全绿 + `build:client` 门禁通过

## 7. 附带发现（不同源，登记为线索，不并入本需求范围）

**分类流程档案与门禁强制点口径不一致**：`CATEGORY_FLOW_PROFILES.bug` 声明"免需求分析门"，`confirmGateKindFor()`（protocol.ts:326-333）也是分类感知的；但 `application/use-cases/MoveRequirement.ts:56` 直接用**未过滤**的 `ARTIFACT_CONFIRM_GATES[from>to]`，导致 bug 需求推进时仍被要求 `kind=requirement` 人工确认门（本窗口 2026-09-18 实测被拒：`REQBOARD_HUMAN_GATE`）。与 artifact-gates.ts:127 的判定不同源。建议单独立项，不在本需求内改。
