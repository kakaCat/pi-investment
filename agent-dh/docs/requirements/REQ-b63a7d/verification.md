# REQ-b63a7d 验收材料（t7 进行中）

> 状态：**重启前草稿**。重启 :13080 后由续跑会话填入 A1–A4 实测结果并提交验收。

## 一、交付内容

| 层 | 改动 | 作用 |
|---|---|---|
| domain | `src/domain/artifact/ArtifactPath.ts`（新） | 路径归一唯一实现：剥工作区名前缀/绝对前缀、判伪路径、判逃逸 |
| application | `use-cases/ReportTask.ts` | 写入侧归一：files_changed 上浮前过归一层；伪路径/工作区外绝对路径不入清单 |
| http | `http/routers/artifacts.ts`（重写）+ `http/routes.ts` | allowlist 放宽到工作区根；穿越仍 403；跨仓 404 outside_workspace；伪路径 404 not_a_file；新增 POST docs/resolve 批量端点 |
| client | `client/api.ts` + `client/board-mount.ts` | 预检从逐条 GET 改为一次批量解析（host 单点判定），按 reason 标注 |
| scripts | `scripts/normalize-ledger-paths.ts`（新） | 存量台账清理（已 apply 114 条 + verify 0 + 幂等 0） |

## 二、重启后待填的线上核验（A1–A4）

```bash
B=http://127.0.0.1:13080/dashboard/api/reqboard/file
curl -s -o /dev/null -w 'A1a %{http_code}\n' "$B?path=agent-dh%2Fdocs%2Farchitecture%2Fdocumentation-standard.md"   # 期望 200
curl -s -o /dev/null -w 'A1b %{http_code}\n' "$B?path=docs%2Farchitecture%2Fdocumentation-standard.md"                 # 期望 200
curl -s "$B?path=quantsys-v2%2Fmain.py" | head -c 200                                                                   # 期望 404 outside_workspace
curl -s -o /dev/null -w 'A2a %{http_code}\n' "$B?path=..%2F..%2Fetc%2Fpasswd"                                          # 期望 403
curl -s -o /dev/null -w 'A2b %{http_code}\n' "$B?path=%2Fetc%2Fpasswd"                                                 # 期望 403
curl -s -X POST -H 'Content-Type: application/json' -d '{"paths":["packages/pages/dsh-pmboard/src/index.ts","quantsys-v2/main.py"]}' \
  http://127.0.0.1:13080/dashboard/api/reqboard/docs/resolve | head -c 300                                               # 期望 200，openable 分别 true/false
```

A4（浏览器）：硬刷新（Cmd+Shift+R）→ 打开需求详情页「文档记录」→ 控制台**无 403**；源码类产物不再被标「缺失」。

## 三、本次交付的自测证据（重启前已通过）

- `npx vitest run` 全量：**1197 passed / 6 failed**。6 个失败全部落在 `capture-section.ts` / `acceptance-criteria` / `board-info-fixes` / `message-hygiene` / `typecheck`，这些文件在本窗口动手前即为 dirty（另一窗口在飞），**与本次改动无关**。
- 本次新增/相关用例：`tests/domain/artifact-path.test.ts`（16）、`tests/application/report-task-path.test.ts`（6）、`tests/http/file-route.test.ts`（13）、`tests/client-api-resolve.test.ts`（3）、`tests/fault-injection-paths.test.ts`（10，含真实台账扫描）、`tests/layer-boundary.test.ts`（9）。合计 57 例全绿。
- `pnpm build:client` + `verify-client-build`：OK（bundle=227289 bytes，关键符号齐全，WRAP_SENTINEL 未命中）。
- `python3 scripts/relink-profile.py --check`：25/25 symlink-ok（排除「硬链接副本静默过期」导致重启加载旧 bundle）。
