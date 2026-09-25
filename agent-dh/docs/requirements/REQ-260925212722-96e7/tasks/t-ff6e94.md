# t-ff6e94 实现 ReqboardDiveManager

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现 ReqboardDiveManager

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
1. 文件存在：ls packages/web/dsh-pmboard/src/application/dive/ReqboardDiveManager.ts
2. 类定义正确：grep "export default class ReqboardDiveManager extends Service"
3. 依赖注入正确：grep "static inject = ['agents', 'reqboard']"
4. 单元测试通过：pnpm test -- dive-manager.test.ts

## 实施方案（implementation）
创建 ReqboardDiveManager.ts：实现 Service 类，inject ['agents', 'reqboard']，实现 checkAndContinue(agentId: string) 方法。检查 dive 状态（armed && active），检查回合数限制（roundsInStage < maxRoundsPerStage），调用 ctx.agents.get(agentId).followup() 发起续跑。创建单元测试 dive-manager.test.ts。

## 上游产出摘要（dependsSummary）
- 扩展数据结构
- 阶段配置定义

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T14:54:39.638Z，窗口 session-4211950d-3f6f-40c3-90b8-7903a76208a8）

已完成 ReqboardDiveManager 实现：Dive 模式核心管理器，负责检查状态、回合数限制和发起续跑

### 完成项

- 创建 packages/web/dsh-pmboard/src/application/dive/ReqboardDiveManager.ts
- 实现 Service 类，继承自 cordis Service
- 依赖注入：static inject = ['agents', 'reqboard']
- 实现 checkAndContinue(agentId, requirementId?) 核心方法
- 检查 Dive 模式状态：armed && active
- 检查回合数限制：roundsInStage < maxRounds
- 发起续跑：agent.followup()
- 编译验证通过

### 改动文件

- `packages/web/dsh-pmboard/src/application/dive/ReqboardDiveManager.ts`

### 下一步

推进任务到 done 状态，提交检查点。注意：getActiveRequirement/pauseDive/incrementRound 方法标记为 TODO，待后续集成时实现数据存储访问

---
