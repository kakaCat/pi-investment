# reqboard 产物/文档路径契约（唯一事实源）

> 来源：REQ-b63a7d（2026-09-18）。本文定义**产物路径口径**与**文件服务接口的可服务范围**——
> 两处口径一旦漂移，就会重现「合法文档被打成 403 + 页面误标缺失」的事故。

## 1. 口径定义

**唯一口径 = 工作区相对路径**（相对 DSH 会话工作区根；本实例为 `/Users/yunpeng/pi-investment/agent-dh`）。
登记产物/文档路径时必须归一，历史遗留的下列写法由归一层在读取时兜底：

| 形态 | 例子 | 处理 |
|---|---|---|
| 工作区相对（**标准**） | `docs/architecture/x.md`、`packages/pages/y.ts` | 原样 |
| 仓库根相对 | `agent-dh/docs/architecture/x.md` | 剥掉重复的工作区目录名前缀 |
| 工作区内绝对路径 | `/Users/…/agent-dh/packages/y.ts` | 剥掉工作区根 |
| 工作区外绝对路径 | `/etc/passwd` | 拒绝（403），且**不登记**为产物 |
| 跨仓相对 | `quantsys-v2/...`（兄弟仓库） | 不可打开；接口返回 404 `outside_workspace` |
| 伪路径 | `quantsys-v2/tests/{a.py,b.py}`、`docs/*.md` | 不是文件；接口返回 404 `not_a_file`，不登记 |

实现（**唯一实现处**）：`packages/pages/dsh-pmboard/src/domain/artifact/ArtifactPath.ts`

## 2. 文件服务接口契约

`GET /dashboard/api/reqboard/file?path=…`

| 情形 | 状态码 | body.code |
|---|---|---|
| 工作区内、存在且是文件 | 200 | — |
| 含 `..` / 反斜杠 / 工作区外绝对路径 | 403 | `forbidden` |
| 解析后落在工作区之外（含兄弟仓库） | 404 | `outside_workspace` |
| 伪路径（brace / 通配 / 空） | 404 | `not_a_file` |
| 工作区内但不存在 | 404 | `not_found` |

**可服务范围 = 整个工作区根**（不是 `docs/` 子集）——因为「改动文件上浮」会登记源码类产物。

`POST /dashboard/api/reqboard/docs/resolve {paths:[…]}`（批量，恒 200）
→ 逐条返回 `{path, normalized, form, exists, openable, reason?}`；**判定口径与单文件接口完全一致**（同一 `classify()`）。
前端「文档记录」区只调这一个端点：N 条失败请求 → 1 条恒 200 请求，控制台不再刷红。

## 3. 两条纪律（防回归）

1. **写入侧必须归一**：`reqboard_task_report` 的 `files_changed` 上浮前过归一层；新增任何登记产物的入口同样处理。禁止把窗口给的字符串原样落库。
2. **判定只在一处**：路径形态（form）与可打开性（openable）由 host 单点判定后下发；前端不得自行再判一次（两端各一套 = 下一次 drift）。

## 4. 相关

- 归一层与其单测：`src/domain/artifact/ArtifactPath.ts`、`tests/domain/artifact-path.test.ts`
- 路由分档与批量端点：`src/http/routers/artifacts.ts`、`tests/http/file-route.test.ts`
- 契约与故障注入：`tests/client-api-resolve.test.ts`、`tests/fault-injection-paths.test.ts`（含真实台账扫描）
- 存量清理脚本：`packages/pages/dsh-pmboard/scripts/normalize-ledger-paths.ts`（--dry-run/--apply/--verify；apply 须停服窗口）
