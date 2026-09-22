# t-fb688e [FR-1~FR-5] 全量回归与实证验收（含兼容性验证）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
[FR-1~FR-5] 全量回归与实证验收（含兼容性验证）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：fullstack

## 得到什么结果

cd agent-dh 逐条执行：①npx vitest run packages/web/dsh-pmboard/tests/capture-tool.test.ts packages/web/dsh-pmboard/tests/requirement-doc-path.test.ts packages/web/dsh-pmboard/tests/state-workspace-root.test.ts → 全部 passed；②npx vitest run packages/web/dsh-pmboard → 记录失败文件清单，与 git worktree @ main 基线同命令的失败清单比对，差集必须为空（即无本需求新引入失败；主干存量红灯不算本需求失败）；③npx vitest run apps/web/tests/plugin-schema.smoke.test.ts → passed；④curl -s http://127.0.0.1:13080/dashboard/api/reqboard/state | jq '{workspaceRoot,homeDir}' → 返回 /Users 开头绝对路径；⑤grep -n "nodeIsolation: true" config/cordis.yml → 有命中行。

## 实施方案（implementation）
cd agent-dh && npx vitest run packages/web/dsh-pmboard；逐条核对 requirement.md「验收判定」1-6 并留证据；schema 冒烟 npx vitest run apps/web/tests/plugin-schema.smoke.test.ts。

## 上游产出摘要（dependsSummary）
- [FR-1] 更新 capture-tool.test.ts 为四问口径
- [FR-2] requirementDocPath 消费 docBasePath + 单测
- [FR-3] cordis.yml 开启 nodeIsolation 并重启验证
- [FR-4] state 端点暴露 workspaceRoot/homeDir + 客户端绝对路径打开与显示
- [FR-5] 立项拒绝粘滞：rejected 落痕 + 弹框前置检查 + 提示词纪律

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-22T03:38:48.959Z，窗口 session-9faaac35-2641-473c-a5dc-ea6e6d11efbf）

全量回归与验收核对完成：需求六条验收判定全部有证据；91 条全量失败经 worktree 基线实证全部为主干存量红灯（与本需求无关），本需求触碰面 0 失败

### 完成项

- 判定1 capture-tool 15/15 ✓
- 判定2 requirement-doc-path 6/6 ✓
- 判定3 cordis.yml+活动配置 nodeIsolation:true ✓
- 判定4 state 端点 workspaceRoot/homeDir curl 实证 ✓
- 判定5 FR-5 前置检查不弹框（单测断言 ask 未调用）✓
- 判定6 全量回归：91 失败全部存量（6 文件 chdir-in-workers 环境特征 + 4 文件 main worktree 基线同红）
- plugin-schema.smoke 20/20 ✓
- typecheck exit 0 ✓

### 下一步

提交验收材料（reqboard_submit kind=verification）

---
