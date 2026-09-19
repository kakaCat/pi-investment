---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5]
---

# REQ-640a55 技术设计 · 架构

> 本文回答「门禁挂在哪一层、为什么挂在那个时刻、为什么是这个批次顺序」。

## 现状：三处失效的形态（serves: FR-1, FR-3, FR-4）

| 失效 | 代码位置 | 形态 | 实测 |
|---|---|---|---|
| 三要素门禁未接线 | `content-gates.ts:224` `checkTaskCardTriad` | 纯函数 + 单测齐全，**零生产调用方** | `task_card_incomplete` 全仓无产出点 |
| 跳号判据失效 | `content-gates.ts:278` | 正则位数写成字面字符 d | `re.exec('FR-1') === null` |
| 重复判据失效 | `content-gates.ts:307`（输入来自 `:20-31`） | 上游 `Set` 去重之后再判重 | 每个编号计数恒 ≤1 |

三者的共同点：**不报错、不告警、测试全绿**——这正是本需求要修的形态。

## 分层不改（serves: FR-1, FR-2）

既有分工：判定（零 IO 纯函数）在 `application/internal/content-gates.ts`；文件读取与组装在
`content-gate-wiring.ts`；工具壳（`tools/*Tool.ts`）**只调用与拒绝，禁止出现状态字面量**。
新增的三要素门禁严守同一条线：`checkTaskCardTriad` 一行不改，接线函数负责读卡、解析、汇总缺口。

## 调用点与触发时机（serves: FR-1）

为什么挂在「出口」与「结单」，而不是「入库」：

- `decomposing → implementing`（`MoveTool` 壳、`mutate` 之前）：此时卡已全部产出、实施尚未开始。
  拦在这里的代价是改一段 markdown；拦在交付后的代价是重做。
- `task_move(to=done)`（`TaskMoveTool` 壳、`executeMoveTask` 之前）：防止卡在拆分后被改坏或被覆盖。

两条都复用**异步预检 + 同步 mutate** 的既有形态（`TaskMoveTool.ts:117-130` 已有同款先例），
不修改 `support.ts` 的同步结单校验（该文件正被另一窗口占用）。

## 判据与跳过规则（serves: FR-1, FR-5）

硬拦只看两件事：字段**缺失**（undefined）与字段**为空**（空串）。
标题像工程名词堆叠 → 只进 warnings，不阻断（保持既有取向，避免形式主义）。

跳过三条（防误伤）：目标态不符 / 卡文件不存在 / 需求不属于本窗口绑定集合。
三条都是为了「门禁只在该判定的时刻判定」。

## 批次与依赖顺序（serves: FR-1, FR-2, FR-3, FR-4, FR-5）

批次 1（FR-3 / FR-4）纯函数、零接线风险 → 批次 2（FR-2）骨架直出 → 批次 3（FR-1 / FR-5）接线与兼容。

**FR-1 依赖 FR-2**：骨架不产出三要素节时，接上线会把所有新卡拦死。顺序不可颠倒。

## 回滚与不误伤（serves: FR-5）

- 回滚 = 移除两个调用点，行为回到今天；wiring 函数不写台账、无副作用。
- 存量：台账 10 条非终态需求 / 19 张在途卡**均已过 `decomposing` 出口** → 新门禁实测零误伤；
  仅在「重新打开再结单」时受约束，那时正好补三要素。
