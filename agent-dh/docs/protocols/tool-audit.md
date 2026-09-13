---
id: tool-audit
title: 工具审计清单
type: protocol
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [protocol, tools, audit]
---

# 工具审计清单

**这页回答**：怎么查一个工具"说到的"是不是"做到的"（定期抽查 / 接手陌生插件时用）。

## 结论先行

1. **声明与实现必须一致**：参数写了就要被消费（历史：某工具声明 `dry_run` 模拟执行，后端忽略直接真下单——**声明与实现不符比没有更危险**）。
2. **默认值要安全**：写操作的默认值不能指向别人的账户或真实副作用；缺参时按本实例账户（`agents.json`）执行，而不是代码里写死的历史值。
3. **降级要显式**：返回体必须带 `degraded` / `stale` / `source` / `as_of` 之类字段；没有这些字段的"看起来正常"最危险。
4. **客户端/后端契约要对齐三层**：后端模型 → client 映射 → 工具 validate/prompt/render；只改一层会留下"半通"状态。

## 抽查步骤

```
1) 找工具：packages/*/src/*.ts 里 grep defineTool({ name: '<tool>'
2) 看参数：parameters 每个键，去后端/client 里 grep 是否真的被读
3) 看默认值：默认账户/默认时间窗/默认 dry_run 是否安全且与 docs 一致
4) 看返回：schema 与真实响应结构对得上吗（用真实调用打样，不看类型定义）
5) 看错误：上游挂了会抛错还是兜默认值；空结果是显式报错还是当成功
6) 看降级：degraded/source/as_of 有没有如实传出来
```

## 已发现并修复的典型问题（可作范例）

| 问题 | 教训 |
|---|---|
| `dry_run` 声明未实现，直接真下单 | 校验清单要反向核对"工具承诺的每个参数后端是否真的消费" |
| 后端返回 `orders` 而工具解析 `items` → 静默空 | 字段假设必须真实调用核实 |
| 默认账户写死为 `agent_virtual` | 默认值指错账户 = 用别人的账下单，且静默无声 |
| `algo_execute` 只生成切片计划不真下单（已在描述中标注） | 工具描述必须写清"它到底做不做事" |

## 相关页面

- [工具开发规范](../standards/tool-development.md) · [工具清单](../architecture/TOOLS_INVENTORY.md)
- [数据与降级规范](../standards/data-and-degradation.md)
