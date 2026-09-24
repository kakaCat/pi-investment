# 回归基线 · REQ-260922182505-0924（t1 复现卡产物）

> 采集时点：2026-09-22T12:11:34.342Z（实施前主干现状）

## 1. triage 死代码现状（复现）

- `grep -rn "triage" src/ --include="*.ts"`（排除 .bak）：127 行命中，分布 22 个文件（含 3 处纯注释）。全量清单见 baseline-grep.txt。
- 部署实例（:13080）`GET /dashboard/api/reqboard/triage` 返回 **200**，响应体含 `pending:[]` 与 2 条 resolved 历史记录（curl 证据见 baseline-curl.txt）——旧流程接口仍在装配运行，复现成立。
- `src/application/internal/support.ts.bak2/.bak3/.bak4` 三个无引用备份文件存在。

## 2. 全量测试基线（删除前的失败集）

命令：`npx vitest run packages/web/dsh-pmboard`（agent-dh 根目录）

汇总：**Test Files 10 failed | 127 passed (137)；Tests 91 failed | 1571 passed (1662)**

失败测试文件（10 个）：
- packages/web/dsh-pmboard/tests/acceptance-criteria.test.ts
- packages/web/dsh-pmboard/tests/application/repository.test.ts
- packages/web/dsh-pmboard/tests/artifact-gates.test.ts
- packages/web/dsh-pmboard/tests/client-view.test.ts
- packages/web/dsh-pmboard/tests/e2e-triad-gate.test.ts
- packages/web/dsh-pmboard/tests/handoff.test.ts
- packages/web/dsh-pmboard/tests/layer-boundary.test.ts
- packages/web/dsh-pmboard/tests/size-budget.test.ts
- packages/web/dsh-pmboard/tests/task-report.test.ts
- packages/web/dsh-pmboard/tests/triad-gate.test.ts

逐条失败用例清单（91 条去重排序）：baseline-test-failures.txt

注：基线失败多为存量红灯（process.chdir 不支持 worker、RandomIdFactory 格式断言等已知治理线问题），与本需求无关——t2/t3 的验收口径是"失败集差集为空"，即不新增失败、也不强求修复存量红灯（需求边界已声明不动 acceptance-criteria 等存量治理线）。
