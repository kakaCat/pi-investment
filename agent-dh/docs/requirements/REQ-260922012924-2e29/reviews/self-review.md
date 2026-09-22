# 评审报告 · REQ-260922012924-2e29（实施方自评）

> 评审人：w-9faaac35（investor，即实施窗口）｜ 日期：2026-09-22
> 性质：实施完成后的自评复核；正式验收以人工审核为准。

## 对照设计逐条复核

| 条款 | 设计承诺 | 落地核验 | 结论 |
|------|---------|---------|------|
| FR-1 | 四问断言同步，测试转绿 | capture-tool.test.ts 15/15 绿（原 4 红清零，含名称题首项 ✖️ 断言） | ✅ |
| FR-2 | docBasePath 被消费，缺省逐字节一致 | requirementDocPath 改造 + 6 用例（含 <REQ>/无占位符/尾斜杠/docLinks 优先/缺省一致） | ✅ |
| FR-3 | cordis.yml 开启压缩，重启验证 | 模板+活动配置双命中；dist 20/20 构建校验；重启后 state 端点实证新代码 | ✅ |
| FR-4 | workspaceRoot 暴露 + 绝对路径打开/显示 | handleState 增两字段（curl 实证）；open-doc 缓存+绝对化；4 处按钮 title；capture 回执绝对路径 | ✅ |
| FR-5 | rejected 落痕 + 前置检查 + 提示词纪律 | capture-rejections 纯逻辑+适配器+用例接线+提示词；6 用例（含写失败/读损坏降级） | ✅ |

## 发现与如实记录

1. **全量回归 91 条失败全部为主干存量**（非本需求引入）：6 个失败文件含 process.chdir（vitest workers 环境特征）；repository/client-view/layer-boundary/size-budget 在 main worktree 基线同红；layer-boundary 违规行 git show HEAD 实证（diag-log.ts import node:fs）。建议另立需求治理存量红灯。
2. **一处证据口径自纠**：走查期曾以 PTC 子进程 env 判 NODE_ISOLATION 未设——该 env 与服务进程无关（R-013 级教训）。后改以"活动配置文件 + 留痕 windowKey + 进程 env"三重证据定论：13080 常驻进程此前确为关（本会话零压缩留痕），其他窗口的手动调试运行写入了早期留痕。
3. **可观测性遗留**：插件 logger.info 的"压缩开关 NODE_ISOLATION=" 装配行未进 manual.out.log（cordis logger 路由），不影响功能证据；G0 门 doc_not_ready 跳过行为将在下次自然立项时于 isolation-trace 可见。
4. **门禁交互记录**：设计阶段 G2 曾按模板拦下（requirement.md 缺必填节 + design 五份未交），已按 category-doc-sets 契约补齐后过门——门禁行为符合预期。
