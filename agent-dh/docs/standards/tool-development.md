---
id: std-tool-development
title: 工具开发规范（defineTool / schema 铁律 / 诚实失败）
type: standard
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [standards, tools, schema]
---

# 工具开发规范

**这页回答**：给 agent 加一个工具时，哪些是硬约束、违反会怎样、怎么自检。

## 结论先行（违反 = 不算完成）

1. **每个 `type: 'object'` 节点必须显式写 `additionalProperties: true | false`**——包括
   `parameters` / `output.schema` 的任意嵌套层级（properties 里的、items 里的，无一例外）。
   漏了 → **DSH 启动即崩（UNSUPPORTED_SCHEMA）**，不是运行时才报错。
2. 对象节点只允许 `type` / `properties` / `additionalProperties` + 注解键（`description` / `title` /
   `default` / `examples`）；**没有 `required: []` 数组**，必填在参数属性上写 `required: true`。
3. 写完**必须**跑冒烟：`cd agent-dh && npx vitest run tests/plugin-schema.smoke.test.ts`
   （新插件要加进该测试的 PLUGINS 列表，否则等于没测）。
4. **诚实失败**：拿不到数据就报错或显式降级标注，**禁止静默兜底**把"没生效"伪装成"在工作"
   （历史事故：字段名假设错 → 回退到默认值 → 工具天天返回看似正常的结果）。
5. 工具的 `description` 是给模型看的**用法说明**：写"用于什么场景、什么时候别用"，
   不要写实现细节。

## 关键机制（怎么写）

- 插件 = cordis `Service`：`static inject = ['tools']`（或惰性 `(ctx as any).inject([...], cb)`），
  构造函数里注册工具；`output.render` 用 `JSON.stringify(value, null, 2)` 让模型可读。
- 参数校验放在 `execute` 内（`normalizeTitle` 之类的入口校验），非法输入抛带 `code` 的错误。
- 错误对象：`Object.assign(new Error('...'), { code: 'xxx' })`；路由层按 code 映射 HTTP 状态。
  消息里自带 code 文本（工具层读的是 message，跨包时 `instanceof` 不可靠）。
- 工具**不要**建 HTTP 服务、不要读全局单例状态；需要服务就用 `inject` 拿。

## 依据（谁定的 / 哪次事故）

- 2026-08-19：`investment` / `market` 插件 schema 缺 `additionalProperties` → **全量启动崩溃**，
  之后新增 `tests/plugin-schema.smoke.test.ts` 作为门禁；
- 静默兜底事故：后端字段名与假设不符（`orders` vs `items`、`shares` vs `quantity`）→ 工具返回默认值，
  看起来"在工作"，实际全错；
- 声明与实现不符的事故：某工具的 `dry_run` 参数后端根本没消费，声明"模拟执行"实际真下单。

## 自检清单（提交前逐条过）

- [ ] 每个 object 节点都有 `additionalProperties`？`npx vitest run tests/plugin-schema.smoke.test.ts` 绿？
- [ ] 新工具加进 PLUGINS 列表了？工具名/描述能在真机 `self_info` 或工具清单里看到？
- [ ] 对后端返回结构的假设，用**真实调用**核实过（不是照抄类型定义）？
- [ ] 失败路径：上游挂了会返回什么？会不会被我兜成一串默认值？
- [ ] 默认值安全吗（如账户名默认值、dry_run 默认值）？写操作是否显式要求传参？

## 相关页面

- [插件与页面插件规范](plugin-and-pages.md)
- [构建与发版规范](build-and-release.md)
- [测试与门禁规范](testing.md)
- [工具清单](../architecture/TOOLS_INVENTORY.md)
