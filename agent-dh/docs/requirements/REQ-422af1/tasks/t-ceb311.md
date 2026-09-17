# t-ceb311 编写类型档（六节点 × 六类型）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
编写类型档（六节点 × 六类型）

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
tests/prompt-categories.test.ts 全绿：同一 (stage,difficulty) 下 (stage,*,bug) 与 (stage,*,feature) 解析出的文本不同；各类型档分别包含必要关键词（bug：先复现、回归测试；refactor：行为等价；feature：接口与数据契约；spike：回答一个问题；doc：只改文档；chore：最小改动）——每类型断言通过；孤岛门禁全绿（不存在写了却没被路由命中的类型档）。验证命令：npx vitest run tests/prompt-categories.test.ts（在 packages/pages/dsh-pmboard 下）；不通过则本卡不完成。

## 实施方案（implementation）
按 design/fragments.md §6 编写 src/domain/prompt/fragments/<stage>/{bug,refactor,feature,spike,doc,chore}.md（六节点各六份，共 36 份，内容短、只写该类型差异化要求）；跑生成器与全部门禁；确认回退链层级 ① 命中。

## 上游产出摘要（dependsSummary）
- 编写六节点 light/heavy 分片内容与要素门禁

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T14:59:17.722Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

六个节点 × 六个类型档（36 份）全部落地并走回退链 ①（精确命中），(stage,*,category) 在 ③ 层仍可用、无孤岛；父窗口已复核（36 份齐备、tsc 0、同步门禁 exit 0、断言改动实为更严）。

### 完成项

- 36 份类型档源文件（六节点 × bug/refactor/feature/spike/doc/chore，decomposing 为自写档）
- 生成器扩展：include-only 路由壳 <stage>/<difficulty>/<category>，使 ① 命中 = 节点档 + 类型档 + ⑤ 铁律；未改 router 契约
- tests/prompt-categories.test.ts 160 tests 全绿（类型文本两两不同 + 逐类型关键词 + ① 命中且两类档同在 fragmentIds + ③ 层可用 + 无孤岛）
- 父窗口复核：36 份源文件齐备、tsc 0 错误、check-prompt-fragments exit 0
- 父窗口检查其唯一测试改动：改为同 category 对照（toContain(resolveStagePrompt({stage:implementing,category:spike}).text)），属更严而非放松

### 改动文件

- `/Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/src/domain/prompt/fragments/brainstorming/bug.md`
- `/Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/scripts/inline-prompt-fragments.mjs`
- `/Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/src/domain/prompt/index.ts`
- `/Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/src/domain/prompt/generated/fragments.ts`
- `/Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/tests/prompt-categories.test.ts`
- `/Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/tests/fixtures/stage-prompts-baseline-p1.json`
- `/Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/tests/stage-prompts.test.ts`

### 下一步

剩 t9/t10/t11 同窗口 surface 替换三卡（风险最高，父窗口亲做）

---
