# REQ-f0579a 接口变化（审计整改）

## 行为变化（用户/调用方可感知）

1. **POST /reqboard/requirements/:id/verdicts（confirm_override 路径）**：覆盖通过现在写 acceptanceOverride 留痕（台账字段 + 评论 + 状态事件），且不再在无材料时伪造 verification 记录。「覆盖即可通过」语义不变（REQ-327bdf）。
2. **reqboard_task_execute 输出**：output.schema 增声明 stages / next_step / error（返回体本就带这些键，此前绑定层有拒收风险）。
3. **reqboard_task_status 输出**：output.schema 增声明 workflow / error。
4. **renderMarkdown**：链接只放行 http/https/mailto/相对路径；javascript:/data: 渲染为纯文本标签（不再是可点链接）。
5. **看板 lanes 视图**：done 需求重新归入验收泳道；底部归档条恢复；产物标签恢复为「种类可读名 · 文件名」。

## 新增内部接口（不外露）

- src/domain/task/TaskStatus.ts：isWorkflowRunCompleted(status) ——状态判断单点，tools-dispatch 门禁禁止工具壳出现任何 status === 比较；
- src/gate-wiring.ts：assembleGatePostChain(deps) / registerCaptureGuidance(ctx, deps)——从 index.ts 抽出的装配函数（尺寸门禁）。