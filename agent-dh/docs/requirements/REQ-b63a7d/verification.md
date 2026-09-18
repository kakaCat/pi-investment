# REQ-b63a7d 验收材料（t7 已完成）

> 重启时间 2026-09-18 23:51:52（pid 32032 起，之前 pid 2266）；检查点分支 `agent-self/20260918-235136`。

## 一、交付内容

| 层 | 改动 | 作用 |
|---|---|---|
| domain | `src/domain/artifact/ArtifactPath.ts`（新） | 路径归一唯一实现：剥工作区名前缀/绝对前缀、判伪路径、判逃逸 |
| application | `use-cases/ReportTask.ts` | 写入侧归一：files_changed 上浮前过归一层；伪路径/工作区外绝对路径不入清单 |
| http | `http/routers/artifacts.ts`（重写）+ `http/routes.ts` | allowlist 放宽到工作区根；穿越仍 403；跨仓 404 outside_workspace；伪路径 404 not_a_file；新增 POST docs/resolve |
| client | `client/api.ts` + `client/board-mount.ts` | 预检从逐条 GET 改为一次批量解析（host 单点判定），按 reason 标注 |
| scripts | `scripts/normalize-ledger-paths.ts`（新） | 存量台账清理：apply 114 条 + verify 0 + 幂等 0 |

## 二、线上核验实测（2026-09-18 23:52，重启后）

| 断言 | 命令 | 实测 |
|---|---|---|
| A1a 仓库根相对前缀 | `GET /file?path=agent-dh/docs/architecture/documentation-standard.md` | **200**（修复前 403 — 即用户报的那条） |
| A1b 工作区相对 | `GET /file?path=docs/architecture/documentation-standard.md` | **200** |
| A1c 源码类产物 | `GET /file?path=packages/pages/dsh-pmboard/src/index.ts` | **200**（修复前 403：docs-only 白名单） |
| A2a 穿越 | `GET /file?path=../../etc/passwd` | **403** forbidden（防护未放宽） |
| A2b 工作区外绝对路径 | `GET /file?path=/etc/passwd` | **403** |
| A3 跨仓（真实存在的兄弟仓文件） | `GET /file?path=quantsys-v2/CLAUDE.md` | **404 outside_workspace**：`{"error":"文件在工作区之外（跨仓路径，本工作区接口不可服务）","code":"outside_workspace"}` |
| A3b 工作区内缺失 | `GET /file?path=quantsys-v2/main.py`（该文件确实不存在） | 404 not_found（诚实区分，不冒充权限问题） |
| A4 伪路径 | `GET /file?path=quantsys-v2/tests/{a.py,b.py}` | **404 not_a_file** |
| A5 批量端点 | `POST /docs/resolve {paths:[…]}` | **200**，逐条返回 `normalized/form/exists/openable`（两条 workspace 均 openable=true） |
| 台账清理存活 | `normalize-ledger-paths.ts --verify`（重启后复跑） | **OK —— 0 条**（apply 结果跨重启保留） |

**A6（浏览器控制台）**：见「三、未覆盖项」。

## 三、未覆盖项（诚实标注，不冒充已验证）

- **浏览器控制台无 403** 只能由人硬刷新后确认（Cmd+Shift+R）：本次已在**端点层**证明原 403 路径返回 200、批量端点恒 200（前端不再产生失败请求），但「页面控制台干净」未在浏览器实测。请硬刷新后看一眼；若有异常按 §二 命令复现。
- 页面插件由浏览器加载 `lib/client.js`，硬刷新可避免旧 bundle 缓存。

## 四、自测证据（重启前后一致）

- 本次新增/相关用例合计 **57 例全绿**：`tests/domain/artifact-path.test.ts`(16)、`tests/application/report-task-path.test.ts`(6)、`tests/http/file-route.test.ts`(13)、`tests/client-api-resolve.test.ts`(3)、`tests/fault-injection-paths.test.ts`(10，含真实台账扫描)、`tests/layer-boundary.test.ts`(9)。
- 全量：**1197 passed / 6 failed**；6 个失败全部落在 `capture-section.ts`/`acceptance-criteria`/`board-info-fixes`/`message-hygiene`/`typecheck`，这些文件在本窗口动手前即为 dirty（另一窗口在飞），**与本次改动无关**。
- `pnpm build:client` + `verify-client-build`：OK（bundle=227289 bytes，WRAP_SENTINEL 未命中）。
- `python3 scripts/relink-profile.py --check`：25/25 symlink-ok（排除硬链接副本静默过期）。

## 五、遗留（不阻塞本需求）

1. `MoveRequirement.ts:56` 用未按分类过滤的 `ARTIFACT_CONFIRM_GATES`（与分类感知的 `confirmGateKindFor()` 不同源）→ bug 需求声明「免需求分析门」却仍被要求 `kind=requirement` 确认。建议单独立项。
2. 台账清理已 apply；备份 `.dsh-data/dsh-reqboard.json.bak-normalize-1789746666479` 保留待观察。
