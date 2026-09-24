---
requirement_refs: BUG-1, BUG-2
---

# 测试证据 · REQ-260922182505-0924

> 采集时点：2026-09-22T12:34:29.183Z｜环境：agent-dh 仓，Node + vitest 2.1.9

## 证据清单

| # | 证据 | 命令 | 结果 | 文件 |
|---|------|------|------|------|
| E1 | 修前复现：路由在线 | `curl :13080/dashboard/api/reqboard/triage` | 200，含 2 条 resolved | ../baseline-curl.txt |
| E2 | 修前死代码清单 | `grep -rn "triage" src/ --include="*.ts"` | 127 行 / 22 文件 | ../baseline-grep.txt |
| E3 | 回归基线（修前失败集） | `npx vitest run packages/web/dsh-pmboard` | 86 条失败（存量红灯） | ../baseline-test-failures.txt |
| E4 | 编译通过（修后） | `npx tsc --noEmit`（dsh-pmboard） | 0 错误 | — |
| E5 | 删除核验（修后） | `grep -rn "triage" src/ -i` | 仅剩冻结契约+管道+rollup+历史注释 | ../after-grep.txt |
| E6 | .bak 清除 | `ls src/application/internal/*.bak*` | 无文件 | ../after-grep.txt 尾部 |
| E7 | 回归复核（修后，t3 独立重跑） | `npx vitest run packages/web/dsh-pmboard` | 86 条，与 E3 差集为空（comm 双向为空） | ../t3-independent-failures.txt |
| E8 | 部署后 404（新代码实例 :13081） | `curl -X GET/POST 4 个 triage 端点` | 全部 404 not_found | ../t3-deploy-verification.md |
| E9 | 看板服务正常 | `curl :13081/dashboard/api/reqboard/` | 200 | ../t3-deploy-verification.md |
| E10 | 产物无 triage 残留 | `grep -c triage lib/client.js dist/index.mjs` | 0 / 0 | ../t3-deploy-verification.md |
| E11 | 老台账兼容锁定 | `npx vitest run .../tests/migration.test.ts` | 9/9 全绿 | — |

## 回归测试落点（design/test-cases.md 执行回执）

- TC-1 api-client.test.ts：fetchTriage 用例已删 ✅
- TC-2 capture.test.ts / capture-hook.test.ts：hasPendingSuggestion 分支已删，
  shouldCaptureWindow 改为只覆盖 bound/unbound ✅
- TC-3 reqboard.test.ts：「Triage routes with category」describe 整块已删 ✅
- TC-4 其余引用文件：编译/测试零报错，无残留引用 ✅
- TC-5 grep 只剩冻结契约与历史注释 ✅（E5）
- TC-6 部署后 404 ✅（E8）
- TC-7 看板无 triage 入口：产物级证据 ✅（E10）；浏览器目测留人工验收项 ⚠️
- TC-8 失败集差集为空 ✅（E7）
- TC-9 .bak 为空 ✅（E6）
- migration.test.ts（v4 fixture 含 triages）：未改动且 9/9 绿 ✅（E11）

## 存量红灯说明

基线 86 条失败全部为存量已知问题（process.chdir 不支持 worker、RandomIdFactory 格式断言、
acceptance-criteria 治理线等），与本需求无关；本需求边界明确"不动 acceptance-criteria 等
存量红灯测试"。验收口径为"差集为空"而非"全绿"。
