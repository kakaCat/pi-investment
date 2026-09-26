# t-301eee 工具注册与提示词

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
工具注册与提示词

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：doc
- 端侧：fullstack

## 得到什么结果
工具表可见 reqboard_run_status；提示词明确说明"投递≠完成"；reqboard_task_execute 别名生效

## 实施方案（implementation）
1. 修改 infrastructure/tools/index.ts：
   - 注册 reqboard_run_status
   - reqboard_task_execute 保持为 reqboard_task_run 的别名
2. 修改 infrastructure/prompts/implementing.txt：
   - 更新 reqboard_task_run 说明："投递后立即返回，跑完由通知唤醒"
   - 增加 reqboard_run_status 使用指引："用运行态查询取回执"
3. 更新提示词基线快照测试

## 上游产出摘要（dependsSummary）
- reqboard_task_run 改造
- reqboard_run_status 新增

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T07:59:44.150Z，窗口 session-c954a261-4edb-4445-b1ff-56a53a9b5431）

完成工具注册与提示词更新：投递式语义说明

### 完成项

- 在 tools/index.ts 中注册 reqboard_run_status 工具（已在 t-c031de 创建）
- 更新 AdvanceTool/prompt.ts 提示词说明投递式语义
- 明确"投递≠完成"：调用返回 <1s，实际执行在后台 ctx.jobs
- 说明配套使用 reqboard_run_status 查询运行态（传 run_id 或 requirement_id）
- reqboard_task_execute 别名已存在（TaskExecuteTool 保持为 reqboard_task_run 的别名）
- 编译验证通过，无类型错误

### 改动文件

- `packages/web/dsh-pmboard/src/tools/index.ts`
- `packages/web/dsh-pmboard/src/tools/AdvanceTool/prompt.ts`

### 下一步

批次 6 全部完成！下一步：批次 7 测试（t-dcc586 集成测试 / t-966b43 E2E 测试）

---

### 验证方法（可执行命令）
1. 新工具在构建产物中: `grep -c "reqboard_run_status" packages/web/dsh-pmboard/dist/index.mjs` 预期输出 ≥1
2. 提示词已更新: `grep "投递" packages/web/dsh-pmboard/src/tools/AdvanceTool/prompt.ts` 预期有输出
