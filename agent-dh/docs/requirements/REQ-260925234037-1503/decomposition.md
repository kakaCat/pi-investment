---
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6
---

# REQ-260925234037-1503 拆分计划

> 需求：简化 REQ 流水线工具集，全面拥抱 Dive Armed 模式  
> 类型：feature | 难度：expert | 拆分日期：2026-09-25

## 一、目标与范围

### 核心目标

基于 REQ-260925212722-96e7 的 Dive Armed 自动模式，删除过时的手动工具，简化工具集，让 Agent 和用户全面使用自动流程。

### 改动范围概览

1. **删除工具** - 3 个手动工具及其代码
2. **删除 use-case** - 3 个应用层用例
3. **配置修复** - accepting 阶段自动归档
4. **文档更新** - 全面 Dive-first 化

## 二、代码改动盘点

### 2.1 删除的工具（packages/web/dsh-pmboard/src/tools/）

#### DecomposeTool/
- **删除** `DecomposeTool/index.ts` - reqboard_decompose 工具定义
- **删除** `DecomposeTool/prompt.ts` - 工具提示词
- **理由** - Dive Armed 模式下自动拆分，无需手动工具

#### MoveTool/
- **删除** `MoveTool/index.ts` - reqboard_move 工具定义
- **删除** `MoveTool/prompt.ts` - 工具提示词
- **理由** - 状态推进由 Dive 自动管理

#### TaskMoveTool/
- **删除** `TaskMoveTool/index.ts` - reqboard_task_move 工具定义
- **删除** `TaskMoveTool/prompt.ts` - 工具提示词
- **理由** - 任务状态由子卡链自动推进

### 2.2 删除的应用层用例（packages/web/dsh-pmboard/src/application/use-cases/）

#### Decompose.ts
- **删除** 完整文件（~24KB）
- **功能** - 拆分需求为任务卡
- **替代** - Dive Armed 后台自动拆分

#### MoveRequirement.ts
- **删除** 完整文件（~10KB）
- **功能** - 推进需求状态
- **替代** - Dive 自动状态机

#### MoveTask.ts
- **删除** 完整文件（~11KB）
- **功能** - 推进任务状态
- **替代** - 子卡链自动推进

### 2.3 修改的文件

#### packages/web/dsh-pmboard/src/tools/index.ts
- **修改** - 移除 3 个工具的导出
- **删除行**：
  ```typescript
  export { DecomposeTool } from './DecomposeTool';
  export { MoveTool } from './MoveTool';
  export { TaskMoveTool } from './TaskMoveTool';
  ```

#### packages/web/dsh-pmboard/src/application/dive/stage-configs.ts
- **修改** - accepting.autoExecute: false → true
- **位置** - `accepting` 阶段配置
- **效果** - 验收通过后自动归档

### 2.4 文档更新

#### docs/guides/dive-mode-usage.md
- **重写** - 全面 Dive-first 方案
- **删除** - 手动模式章节
- **删除** - armed vs disarmed 对比

#### docs/architecture/reqboard-tools.md（如存在）
- **更新** - 工具列表移除已删除工具
- **添加** - 工具使用频率表

## 三、任务拆解

### T1: 删除过时工具目录

**覆盖需求条款**: FR-1

- **key**: t1
- **title**: 删除 DecomposeTool/MoveTool/TaskMoveTool 目录
- **phase**: implement
- **side**: backend
- **depends_on**: []
- **implementation**:
  1. 删除 `packages/web/dsh-pmboard/src/tools/DecomposeTool/` 完整目录
  2. 删除 `packages/web/dsh-pmboard/src/tools/MoveTool/` 完整目录
  3. 删除 `packages/web/dsh-pmboard/src/tools/TaskMoveTool/` 完整目录
  4. 验证：`ls packages/web/dsh-pmboard/src/tools/ | grep -E '(Decompose|Move|TaskMove)' || echo "Deleted successfully"`
- **acceptance**: 
  运行命令 `ls packages/web/dsh-pmboard/src/tools/ | grep -E '(Decompose|Move|TaskMove)'`，
  返回空（或"Deleted successfully"），证明 3 个工具目录已删除。

### T2: 删除应用层 use-case 文件

**覆盖需求条款**: FR-1

- **key**: t2
- **title**: 删除 Decompose.ts/MoveRequirement.ts/MoveTask.ts
- **phase**: implement
- **side**: backend
- **depends_on**: []
- **implementation**:
  1. 删除 `packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts`
  2. 删除 `packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts`
  3. 删除 `packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts`
  4. 验证：`ls packages/web/dsh-pmboard/src/application/use-cases/ | grep -E '(Decompose|MoveRequirement|MoveTask)'` 返回空
- **acceptance**:
  运行命令 `ls packages/web/dsh-pmboard/src/application/use-cases/ | grep -E '(Decompose|MoveRequirement|MoveTask)' || echo "All deleted"`，
  返回"All deleted"，证明 3 个 use-case 文件已删除。

### T3: 从 tools/index.ts 移除已删除工具的导出

**覆盖需求条款**: FR-1

- **key**: t3
- **title**: 从 tools/index.ts 移除已删除工具的导出
- **phase**: implement
- **side**: backend
- **depends_on**: [t1]
- **implementation**:
  1. 编辑 `packages/web/dsh-pmboard/src/tools/index.ts`
  2. 删除以下 3 行：
     ```typescript
     export { DecomposeTool } from './DecomposeTool';
     export { MoveTool } from './MoveTool';
     export { TaskMoveTool } from './TaskMoveTool';
     ```
  3. 保存文件
  4. 验证：`grep -E '(DecomposeTool|MoveTool|TaskMoveTool)' packages/web/dsh-pmboard/src/tools/index.ts` 返回空
- **acceptance**:
  运行命令 `grep -E '(DecomposeTool|MoveTool|TaskMoveTool)' packages/web/dsh-pmboard/src/tools/index.ts || echo "No references found"`，
  返回"No references found"，证明已删除工具的导出已移除。

### T4: stage-configs.ts 设置 accepting.autoExecute = true

**覆盖需求条款**: FR-6

- **key**: t4
- **title**: stage-configs.ts 设置 accepting.autoExecute = true
- **phase**: implement
- **side**: backend
- **depends_on**: []
- **implementation**:
  1. 编辑 `packages/web/dsh-pmboard/src/application/dive/stage-configs.ts`
  2. 找到 `accepting` 阶段配置
  3. 修改 `autoExecute: false` → `autoExecute: true`
  4. 验证：`grep -A 10 'accepting:' packages/web/dsh-pmboard/src/application/dive/stage-configs.ts | grep 'autoExecute: true'`
- **acceptance**:
  运行命令 `grep -A 10 'accepting:' packages/web/dsh-pmboard/src/application/dive/stage-configs.ts | grep 'autoExecute: true'`，
  返回匹配行（含 `autoExecute: true`），证明 accepting 阶段已配置为自动执行。

### T5: 构建 dsh-pmboard 包，验证无编译错误

**覆盖需求条款**: FR-1

- **key**: t5
- **title**: 构建 dsh-pmboard 包，验证无编译错误
- **phase**: test
- **side**: backend
- **depends_on**: [t1, t2, t3, t4]
- **implementation**:
  1. 进入 dsh-pmboard 目录：`cd packages/web/dsh-pmboard`
  2. 清理旧构建：`rm -rf dist/`
  3. 运行构建：`pnpm build`
  4. 检查构建结果：构建成功且无错误
  5. 验证工具注册：`grep -r 'reqboard_decompose\|reqboard_move\|reqboard_task_move' dist/ || echo "No deprecated tools in dist"`
- **acceptance**:
  在 `packages/web/dsh-pmboard` 目录下运行 `pnpm build`，
  退出码为 0（构建成功），且运行 `grep -r 'reqboard_decompose\|reqboard_move\|reqboard_task_move' dist/ || echo "Clean"` 返回"Clean"，
  证明已删除的工具未出现在构建产物中。

### T6: 启动 DSH 实例，验证工具列表正确

**覆盖需求条款**: FR-1, FR-2, FR-3

- **key**: t6
- **title**: 启动 DSH 实例，验证工具列表正确
- **phase**: test
- **side**: fullstack
- **depends_on**: [t5]
- **implementation**:
  1. 停止现有 DSH 实例（如有）：`cd agent-dh && ./scripts/stop.sh`
  2. 重新链接插件（确保符号链接）：`python3 scripts/relink-profile.py`
  3. 启动测试实例（独立端口）：`./scripts/start.sh --port 13081`
  4. 等待启动（约 30 秒）
  5. 访问 http://127.0.0.1:13081，检查工具列表
  6. 验证：reqboard_decompose/move/task_move 不在工具列表中
  7. 验证：其他 reqboard 工具（status/task_run/ask_confirm 等）正常存在
  8. 停止测试实例
- **acceptance**:
  启动 DSH 实例后，访问 http://127.0.0.1:13081 的工具列表页面，
  确认 `reqboard_decompose`、`reqboard_move`、`reqboard_task_move` 三个工具**不存在**，
  且 `reqboard_status`、`reqboard_task_run`、`reqboard_ask_confirm` 等其他工具正常显示。
  截图或复制工具列表文本作为证据。

### T7: 重写文档为 Dive-first 方案

**覆盖需求条款**: FR-5

- **key**: t7
- **title**: 重写文档为 Dive-first 方案
- **phase**: doc
- **side**: doc
- **depends_on**: []
- **implementation**:
  1. 备份现有文档：`cp docs/guides/dive-mode-usage.md docs/guides/dive-mode-usage.md.bak`
  2. 重写文档内容：
     - 删除"手动模式"章节
     - 删除"armed vs disarmed 对比"章节
     - 强调 Dive Armed 是**唯一**工作方式
     - 更新工具使用示例（只保留 task_run/clear_pause）
     - 添加工具频率表：
       - 高频：status/task_run/ask_confirm
       - 低频：clear_pause（仅紧急）
       - 已删除：decompose/move/task_move
  3. 保存文档
  4. 验证：`grep -i '手动模式\|manual mode' docs/guides/dive-mode-usage.md || echo "No manual mode mentioned"`
- **acceptance**:
  打开 `docs/guides/dive-mode-usage.md`，
  确认文档不再提及"手动模式"或"armed vs disarmed 对比"，
  且明确说明 Dive Armed 是唯一工作方式。
  运行 `grep -i '手动模式\|manual mode\|armed.*disarmed' docs/guides/dive-mode-usage.md || echo "Dive-first only"` 返回"Dive-first only"。

### T8: 完整需求流程测试（无手动工具）

**覆盖需求条款**: FR-2, FR-4, FR-6

- **key**: t8
- **title**: 完整需求流程测试（无手动工具）
- **phase**: test
- **side**: fullstack
- **depends_on**: [t6, t7]
- **implementation**:
  1. 创建测试需求（reqboard_create）
  2. 提交需求文档（reqboard_submit kind=requirement）
  3. 确认需求（reqboard_ask_confirm target=artifact kind=requirement）
  4. 推进到设计阶段（自动或 ask_confirm）
  5. 提交设计文档（reqboard_submit kind=design）
  6. 确认设计（reqboard_ask_confirm target=artifact kind=design）
  7. 推进到拆分阶段
  8. 提交拆分计划（reqboard_submit kind=plan）
  9. 批准拆分计划（reqboard_ask_confirm target=plan）
  10. **验证点**：拆分计划批准后，Dive 自动拆分并进入实施（无需 decompose 工具）
  11. 执行任务（reqboard_task_run）
  12. 验收通过后**自动归档**（无需手动 move）
  13. 全流程记录截图或日志
- **acceptance**:
  完成一个完整的测试需求流程（从 create 到 archived），
  过程中**未使用** reqboard_decompose/move/task_move 任何一个已删除工具，
  且验收通过后需求自动归档（accepting.autoExecute = true 生效）。
  提供流程日志或截图，证明全流程仅使用保留的工具（status/task_run/ask_confirm/clear_pause）。

## 四、依赖关系图

```
t1 (删除工具目录) ──┐
                    ├──> t3 (更新工具注册) ──┐
t2 (删除 use-case) ─┤                        ├──> t5 (编译验证) ──> t6 (运行时验证) ──┐
                    │                        │                                        ├──> t8 (E2E测试)
t4 (修复配置) ──────┘                        │                                        │
                                              │                                        │
t7 (更新文档) ────────────────────────────────┴────────────────────────────────────────┘
```

## 五、风险与缓解

### 风险 1：删除工具后现有 Agent 可能仍尝试调用
- **影响**：工具不存在会导致调用失败
- **缓解**：系统提示词已更新为 Dive-first，新对话不会尝试调用已删除工具；现有对话可通过 clear_pause 重置

### 风险 2：accepting.autoExecute 改动可能影响现有验收流程
- **影响**：验收通过的需求可能未预期地自动归档
- **缓解**：这是需求预期行为（FR-6），且仅影响新进入验收的需求；已在验收中的需求不受影响

### 风险 3：文档更新可能导致用户不知道如何操作
- **影响**：用户找不到手动工具文档
- **缓解**：文档明确说明 Dive Armed 是唯一方式，并提供清晰的工具使用指南

## 六、验收检查清单

- [ ] **代码层面**
  - [ ] DecomposeTool/MoveTool/TaskMoveTool 目录已删除（T1）
  - [ ] Decompose.ts/MoveRequirement.ts/MoveTask.ts 已删除（T2）
  - [ ] tools/index.ts 不再导出已删除工具（T3）
  - [ ] stage-configs.ts accepting.autoExecute = true（T4）
  - [ ] 编译通过，dist/ 不含已删除工具（T5）

- [ ] **运行时验证**
  - [ ] 工具列表不包含 decompose/move/task_move（T6）
  - [ ] 保留工具（status/task_run 等）正常工作（T6）

- [ ] **文档层面**
  - [ ] dive-mode-usage.md 为 Dive-first 方案（T7）
  - [ ] 不再提及手动模式或 armed/disarmed 对比（T7）

- [ ] **E2E 验证**
  - [ ] 完整需求流程无需已删除工具（T8）
  - [ ] 验收通过后自动归档（T8）

## 七、回滚方案

如果发现重大问题需要回滚：

1. **恢复工具代码**：从 git 历史恢复 DecomposeTool/MoveTool/TaskMoveTool 及其 use-case
2. **恢复工具注册**：在 tools/index.ts 添加回导出
3. **恢复配置**：stage-configs.ts accepting.autoExecute 改回 false
4. **恢复文档**：从备份恢复 dive-mode-usage.md

**回滚命令**：
```bash
git checkout HEAD~1 -- packages/web/dsh-pmboard/src/tools/{DecomposeTool,MoveTool,TaskMoveTool}
git checkout HEAD~1 -- packages/web/dsh-pmboard/src/application/use-cases/{Decompose,MoveRequirement,MoveTask}.ts
git checkout HEAD~1 -- packages/web/dsh-pmboard/src/tools/index.ts
git checkout HEAD~1 -- packages/web/dsh-pmboard/src/application/dive/stage-configs.ts
git checkout HEAD~1 -- docs/guides/dive-mode-usage.md
```

## 八、后续工作

本需求完成后的后续改进（不在本次范围内）：

1. **清理单元测试**：删除已删除工具的测试文件
2. **清理类型定义**：移除已删除工具的 TypeScript 类型导出
3. **性能优化**：基于 Dive Armed 唯一化后的简化架构，优化状态推进性能
4. **监控告警**：添加 Dive 流程卡住的监控与告警

---

**拆分完成日期**：2026-09-25  
**预计实施周期**：2-3 天（8 个任务，含测试与文档）

## 需求可追溯矩阵（RTM）

| 任务编号 | 任务标题 | 根编号 |
|---------|---------|--------|
| T-1 | 删除 DecomposeTool/MoveTool/TaskMoveTool 目录 | FR-1 |
| T-2 | 删除 Decompose.ts/MoveRequirement.ts/MoveTask.ts | FR-1 |
| T-3 | 从 tools/index.ts 移除已删除工具的导出 | FR-1 |
| T-4 | stage-configs.ts 设置 accepting.autoExecute = true | FR-6 |
| T-5 | 构建 dsh-pmboard 包，验证无编译错误 | FR-1 |
| T-6 | 启动 DSH 实例，验证工具列表正确 | FR-1 |
| T-6 | 启动 DSH 实例，验证工具列表正确 | FR-2 |
| T-6 | 启动 DSH 实例，验证工具列表正确 | FR-3 |
| T-7 | 重写文档为 Dive-first 方案 | FR-5 |
| T-8 | 完整需求流程测试（无手动工具） | FR-2 |
| T-8 | 完整需求流程测试（无手动工具） | FR-4 |
| T-8 | 完整需求流程测试（无手动工具） | FR-6 |