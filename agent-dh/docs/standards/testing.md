---
id: std-testing
title: 测试与门禁规范（真实数据 / 故障注入 / 线上证据）
type: standard
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [standards, testing, gates]
---

# 测试与门禁规范

**这页回答**：什么算"测过了"；哪些自证清白的方式其实不算数。

## 结论先行

1. **字段假设必须用真实数据核实**——对上游返回结构的任何假设（`orders` vs `items`、
   `max_drawdown` vs `maxDrawdown`、`shares` vs `quantity`），先真实调用一次再写代码。
2. **故障注入是必测项**：只测成功路径等于没测（历史：金丝雀自动还原因子路径必败而无人发现，
   直到故障注入测试才抓住）。
3. **源码级绿灯 ≠ 线上生效**：`vitest` 通过只证明源码合法；"某功能是否在运行实例生效"必须取
   **线上证据**——工具能否绑定 / 接口是否返回 / 页面是否渲染。别拿源码测试当线上证据。
4. **样本门槛**：经验蒸馏类结论要求样本 ≥7（R-016）；样本不足只能登记线索，不许升格为规律。
5. **数值结论必须能被复算**：写清数据区间、口径与来源（R-013）。

## 门禁清单（agent-dh）

| 门禁 | 命令 | 拦什么 |
|---|---|---|
| 工具 schema 冒烟 | `cd agent-dh && npx vitest run tests/plugin-schema.smoke.test.ts` | schema 铁律违规（启动即崩那类） |
| 包级单测 | `cd agent-dh/packages/<pkg> && npx vitest run` | 逻辑回归（如 dsh-pmboard 187 例） |
| 类型检查 | `cd agent-dh && npx tsc --noEmit`（与基线逐条比对**差异**，不是看绝对数） | 新引入的类型错误（基线噪声要与 main 对比） |
| 产物校验 | `ls dist/... && grep -c <符号>` | 构建"假成功" |
| 数据卫生探针 | `python3 quantsys-v2/scripts/data_hygiene_probe.py`（退出码 1 = 有问题） | 悬空引用 / 数据契约违约 |
| 文档 wiki 探针 | `python3 agent-dh/scripts/wiki_probe.py` | 死链 / 孤儿页 / 缺 front-matter |

## 依据

- 字段假设事故：多处"解析失败 → 静默回退默认值 → 看起来在工作"；
- 金丝雀还原路径必败未被发现（无故障注入）；
- dist 陈旧时"源码测试全绿但线上没有该工具"的误判；
- 样本不足（4 < 7）时自动蒸馏给的结论被规则层拒绝采纳（R-016）。

## 自检清单

- [ ] 新增/修改的假设，用真实调用验证过（贴出命令与输出）？
- [ ] 失败路径有没有测（上游超时 / 空结果 / 字段缺失）？
- [ ] 我提供的"已生效"证据是线上证据还是源码级绿灯？
- [ ] 类型检查是与基线**比对差异**，还是只看了总数？
- [ ] 涉及经验的结论，样本量够不够（≥7）？

## 相关页面

- [工具开发规范](tool-development.md)
- [构建与发版规范](build-and-release.md)
- [数据与降级规范](data-and-degradation.md)
