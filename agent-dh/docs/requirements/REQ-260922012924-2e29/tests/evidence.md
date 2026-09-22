# 测试证据 · REQ-260922012924-2e29

> 全部命令在 agent-dh 目录执行（PATH=/opt/homebrew/bin），执行时间 2026-09-22。

## 单测（本需求新增/更新）

```
$ vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts
Tests  15 passed (15)          # FR-1 四问同步 9 例 + FR-5 拒绝粘滞 6 例

$ vitest run packages/web/dsh-pmboard/tests/requirement-doc-path.test.ts
Tests  6 passed (6)            # FR-2 docBasePath 四分支 + docLinks 优先 + 缺省一致

$ vitest run packages/web/dsh-pmboard/tests/state-workspace-root.test.ts
Tests  7 passed (7)            # FR-4 state 端点字段 + 客户端绝对化 + 地址构造
```

## 关联回归（触碰面）

```
$ vitest run stage-panel output-contract verdicts-and-rework apply-wiring isolate-node-context h2-compact prompt-cost prompt-baseline stage-prompts capture capture-hook tools-schema
→ 全部通过（唯一 layer-boundary 失败经 git show HEAD 实证为主干存量 diag-log.ts 违规）

$ vitest run apps/web/tests/plugin-schema.smoke.test.ts
Tests  20 passed (20)

$ tsc --noEmit -p packages/web/dsh-pmboard/tsconfig.json → exit 0
```

## 线上实证

```
$ curl -s http://127.0.0.1:13080/dashboard/api/reqboard/state | jq '{workspaceRoot, homeDir}'
→ /Users/yunpeng/pi-investment/agent-dh /Users/yunpeng     # 新 dist 已加载的直接证据

$ grep -c "nodeIsolation: true" config/cordis.yml .dsh-data/profiles/agent-dh/cordis.patch.yml
→ 1 / 1                                                    # 模板与活动配置双命中

$ ./scripts/restart-with-build.sh --build-only
→ dist 产物校验 20/20 通过；relink 24/24 symlink-ok
```

## 全量回归与存量红灯实证

```
$ vitest run packages/web/dsh-pmboard
Test Files  10 failed | 126 passed (136)
Tests  91 failed | 1567 passed (1658)

存量证明：
- 6 个失败文件含 process.chdir（"process.chdir() is not supported in workers" 环境特征）；
- git worktree @ main 基线跑 repository/client-view/layer-boundary/size-budget → 4 文件同红；
- layer-boundary 违规行：git show HEAD:.../diag-log.ts 第 12-13 行 import node:fs/node:path。
- 本需求改动文件差集比对：我引入的新失败 = 0。
```

## 待人工实证项

- 在工作区=dsh-pmboard 的会话（如本会话 w-9faaac35）的项目看板点开需求文档链接——
  修复前必现打不开，修复后应经官方右侧栏打开（客户端绝对化单测已绿，浏览器点击属人工验收步）。
- FR-5 端到端：capture 弹框点"✖️ 不需要立项"后 30 分钟内重触发 → 不再弹框（单测已绿，线上待自然发生）。
