# 测试证据 · REQ-260922182638-0777

> 全部命令在 agent-dh 目录执行，执行时间 2026-09-22 21:20–21:55。

## 1. 单测（本需求新增/更新）

```
$ pnpm vitest run packages/web/dsh-pmboard/tests/artifact-labels.test.ts
Tests  17 passed (17)      # TC-001 全表/枚举护栏 + TC-002 未知兜底 + TC-003 文件名映射/段边界
                           # + TC-004 任务卡两分支 + TC-005 effectiveDesignDocs 防漂移

$ pnpm vitest run packages/web/dsh-pmboard/tests/stage-panel.test.ts
Tests  53 passed (53)      # 含新增 TC-006a 逐张带名称展开 / TC-006b 降级编号
                           # / TC-006c 未知文件名中文兜底 / TC-006d 缺失红字保留
```

## 2. T-2 验收命令（design/test-cases.md）

```
① $ pnpm vitest run .../artifact-labels.test.ts .../stage-panel.test.ts
   Test Files  2 passed (2) | Tests  70 passed (70)

② $ grep -rn "'需求文档'" packages/web/dsh-pmboard/src
   src/shared/artifact-labels.ts: 2 处（KIND_LABELS + DOC_FILE_LABELS）——定义只剩一个文件

③ $ cd packages/web/dsh-pmboard && pnpm typecheck        → exit 0
   $ pnpm build                                            → BUILD_EXIT=0
     dist/index.mjs 682.22 kB；lib/client.js wrapped 232427 bytes
     [verify-client] OK  bundle=247251 bytes, 关键符号齐全, styles.ts 括号配对

④ $ grep -rn "ARTIFACT_KIND_LABELS|SUBMIT_KIND|ARCHIVE_DOC_KIND_LABELS|DOC_KIND_META" src
   → 旧映射表名零命中；残留仅为工具参数枚举 SUBMIT_KINDS（非中文表）与
     验收允许保留的兼容导出 DOC_KIND_META
```

## 3. 浏览器实际加载物核验（:13080）

```
$ grep -c "架构文档" packages/web/dsh-pmboard/lib/client.js      → 1
$ grep -c "任务卡 · "                                             → 1
$ grep -c "产物（"                                                → 1
$ grep -c "任务卡×"                                               → 0   # 折叠逻辑已消失
$ ls -la node_modules/dsh-pmboard                                  → 指向仓库源码的符号链接
```
即刷新 :13080 页面即加载新产物；像素级目视核对留人工验收单。

## 4. 全量回归归因（1669 条 / 4 红，均非本需求）

| 红灯 | 归因证据 | 结论 |
|------|---------|------|
| client-view 归档栏 dsh-pm-archived-bar 缺失 | git diff board.ts = 另一窗口未提交改动（-55 行，含归档栏逻辑） | 非本需求 |
| repository RandomIdFactory 期望 REQ-[0-9a-f]{6} | 实际 REQ-260922215203-6fc1 = 新 ID 方案；CaptureRequirement.ts 等他人改动 | 非本需求 |
| layer-boundary diag-log.ts import node:fs | 该文件非本需求触碰（git status 无我方记录） | 非本需求（主干存量） |
| size-budget src/index.ts 416 行 | git diff index.ts = 他人 1 行改动 | 非本需求 |

> 环境说明：vitest 默认 workers 下 process.chdir 一族报 ERR_WORKER_UNSUPPORTED_OPERATION（92 条），
> 加 `--pool=forks` 后降为上述 4 条；故 92 条为运行环境特征，非代码缺陷。

## 5. 覆盖链路修复验证

```
$ reqboard_status
  clause_receive_status: FR-1 done[t-85eedd,t-3d33c3,t-67a5c9,t-86ae1e]
                         FR-2 done[t-3d33c3,t-67a5c9,t-86ae1e,t-9d9cf9]
                         FR-3 done[t-85eedd,t-9d9cf9]
                         FR-4 done[t-bdbab2]  FR-5 done[t-bdbab2]
  unreceived_clauses: []
```
