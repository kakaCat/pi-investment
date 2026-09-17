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
| 文档 wiki 探针 | `cd <repo-root> && python3 agent-dh/scripts/wiki_probe.py`（**必须从仓库根跑**：从 `agent-dh/` 跑会把相对链接双前缀化，报出 `docs/INDEX.md -> work-logs/README.md` 这类**假死链**——实测 2 条，换 cwd 即消失） | 死链 / 孤儿页 / 缺 front-matter。判读要点：**只有"现行页"的死链/孤儿计数才计失败**，档案页（work-logs）的只报告不计失败；`exit=1` 可能来自历史档案缺 front-matter（与死链无关，别混为一谈） |
| 文档索引重生 | `cd <repo-root> && python3 agent-dh/scripts/docs_index.py`（**必须从仓库根跑，且连跑两次**：首轮刷新 README 自动区会改变 INDEX 的输入，二轮才收敛） | 索引与文档不一致（探针会提示"跑一次"，但一次不够） |
| **类型检查（页面插件）** | `cd packages/pages/dsh-pmboard && pnpm typecheck`（等价 `npx tsc --noEmit -p tsconfig.json`） | 引用不存在的名字（TS2304）/ 类型不匹配 / 必填字段缺失。**这是唯一能在"运行前"拦住整类错误的门**——见下方事故 |
| 工具输出契约审计（全仓） | `node agent-dh/scripts/audit-tool-output-contract.mjs`（退出码 1 = 有可疑项；`--list` 自证覆盖） | 工具返回键未在 `output.schema` 声明 → 绑定层拒收，**副作用发生了但回执丢给调用方** |
| 层边界机械检查（页面插件） | `cd packages/pages/dsh-pmboard && npx vitest run tests/layer-boundary.test.ts` | 依赖方向倒置 / 适配层复写状态判断 |

## 依据

- 字段假设事故：多处"解析失败 → 静默回退默认值 → 看起来在工作"；
- 金丝雀还原路径必败未被发现（无故障注入）；
- dist 陈旧时"源码测试全绿但线上没有该工具"的误判；
- 样本不足（4 < 7）时自动蒸馏给的结论被规则层拒绝采纳（R-016）；
- **"既有测试全绿"不等于"没坏"：没有类型门禁 + 没有接口级冒烟 = 重构盲区**（2026-09-17，REQ-47939a）：
  dsh-pmboard 分层重构后，`src/http/routers/stages.ts` 引用了两个**不存在的符号**
  （`OPEN_STATUSES`——状态集合被搬走并改名；`TASK_ORDER`——从未定义）。三个门全部漏过：
  ① **没有 tsconfig、没有 tsc 门禁**——tsx 剥类型、vitest 不跑类型检查，TS2304 这类错误**运行前无人拦**；
  ② **该接口零测试覆盖**——`GET /dashboard/api/reqboard/session/:id/progress` 从没被测过，所以"全绿"是假象；
  ③ 注意力被"既有测试全绿"占据。后果：**会话框上的流程节点整块不显示**（运行时 500），由用户发现。
  补测后立刻又抓出同一处理器里的**第二个**同类符号——即"补一个接口冒烟测试"本身就是最高性价比的投入。
  纪律：**改动了某条请求路径，就必须给它补一个接口级冒烟测试；引入新包/新目录，就必须配 tsconfig + 类型门禁。**
- **工具输出契约三次踩同一个坑**（2026-09-17，dsh-pmboard）：`output.schema` 是
  `additionalProperties: false` 时，返回体多一个字段就被绑定层整条拒收——用户已经确认、
  台账已经改了，agent 只收到一条 `invalid output` 错误。共 6 个工具中招（ask_confirm 的
  `requirement_id`、move/decompose/task_move/confirm_artifact/verify_submit 的条件字段）。
  两个教训：① 契约测试必须覆盖**成功路径**（此前只测拒绝路径，所以成功回执坏了没人知道）；
  ② 静态扫描必须能看见**条件展开字段** `...(cond ? { k } : {})` 与**回调实参区**（mutate 回调
  也 return 对象，但不属于工具响应）。两条都已固化为 `tests/output-contract.test.ts` 内
  带自证断言的扫描器 + 本页的全仓审计脚本。

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
