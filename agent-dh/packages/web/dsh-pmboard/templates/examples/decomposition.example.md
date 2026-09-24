# 拆分计划（REQ-example）

> 目标：让 17 类文档模板随插件分发、进节点自动落骨架。
> 做法：构建期把 md 源内联成字符串常量（照抄 prompt fragments 模式），转移后置钩子幂等落盘。
> 本计划经人批准后落任务卡。

## 编号口径

| 编号 | 出自 | 指什么 |
|---|---|---|
| FR-x | requirement.md 功能点表 | 需求条款 |
| I-x | interfaces.md 接口清单 | 接口 |
| P-x / C-x | frontend.md 页面与组件（类型列） | 页面 / 组件 |
| S-x | backend.md 服务与接口实现 | 服务/模块 |
| T-x | data-model.md 表/实体 | 表/实体（按需） |
| UC-x | use-cases.md 场景总览 | 用户场景（按需） |
| M-x | migration.md 迁移步骤 | 迁移步骤（按需） |
| TC-x | test-cases.md 用例表 | 测试用例 |
| t-x | 本文档任务表 | 任务 |

T/UC/M 是按需扩展——涉及数据模型/场景/迁移时才编号；本例未涉及，故下方对照未出现。

## 任务表

| 计划 key | 任务 id | 标题 | 覆盖条款 | 落点（编号+文件） | 阶段 | 端侧 | 依赖 | 工作量 | 验收标准 |
|---|---|---|---|---|---|---|---|---|---|
| t1 | （落库后回填） | 编写需求类模板（6 类型） | FR-1 | templates/{brainstorming,design,implementing}/requirement.*.md | doc | doc | — | M | 6 份模板共用区逐字一致；自检脚本通过 |
| t2 | （落库后回填） | 编写设计类模板（8 份） | FR-1 | templates/design/*.md | doc | doc | — | M | 每份带 front-matter requirement_refs + 全节 serves 标注 |
| t3 | （落库后回填） | 编写拆分/实施/验收/归档模板 | FR-1 | templates/{decomposing,implementing,accepting,archived,common}/ | doc | doc | — | S | 目录齐 17 类；README 索引逐条对得上 |
| t4 | （落库后回填） | 实现模板清单生成器 | FR-2 | I-1 + scripts/inline-templates.mjs、src/domain/prompt/generated/templates.ts | implement | backend | t1, t2, t3 | M | pnpm build 后 dist grep 命中模板字符串（TC-5 过） |
| t5 | （落库后回填） | 实现进节点自动落骨架 | FR-3 | I-3 + S-1 + src/application/internal/template-landing.ts | implement | backend | t4 | M | TC-1/TC-2/TC-4 全过（含逐字节幂等断言） |
| t6 | （落库后回填） | 把模板路径注入节点输入包 | FR-4 | S-3 + src/domain/prompt/（阶段提示词片段） | implement | backend | t4 | S | TC-6 过：输入包含文件指针 + 必填节清单 |
| t7 | （落库后回填） | 把章节校验前移到提交口（SubmitArtifact） | FR-5 | I-2 + S-2 + src/application/SubmitArtifact.ts | implement | backend | t4 | S | TC-3 过（括号注合法变体不误拦） |
| t8 | （落库后回填） | 实现模板防漂移门禁 | FR-6 | scripts/check-templates.mjs | implement | backend | t4 | S | TC-7 过：源改未重跑 → exit 1 |

（起草记录：模板撰写原是 1 张 L 卡「写 17 类模板」——按"L 不许直接落卡"拆成 t1/t2/t3。）

## 覆盖对照

| 需求条款 | 接口（interfaces） | 页面/模块（frontend/backend） | 测试用例（test-cases） | 接收任务 | 完整性 |
|---|---|---|---|---|---|
| FR-1 系统自带一套文档模板 | —（纯内容文件，无接口） | —（纯内容，落 templates/ 目录，无代码模块） | —（漂移由 TC-7 兜底，内容由模板评审把关） | t1, t2, t3（3） | ✅ |
| FR-2 模板清单自动生成 | I-1（1） | —（构建期脚本，无运行时服务模块；落点见 backend 目录与包结构） | TC-5（1） | t4（1） | ✅ |
| FR-3 进节点自动落骨架 | I-3（1） | S-1（1） | TC-1, TC-2, TC-4（3） | t5（1） | ✅ |
| FR-4 提示词里给模板路径 | —（提示词注入，无新接口） | S-3（1） | TC-6（1） | t6（1） | ✅ |
| FR-5 提交即校验章节 | I-2（1） | S-2（1） | TC-3（1） | t7（1） | ✅ |
| FR-6 模板防漂移门禁 | —（CI 脚本，无接口） | —（CI 脚本） | TC-7（1） | t8（1） | ✅ |
| **合计** | 3 接口 | 3 模块 | 7 用例 | 8 任务 | 6/6 条款有主 |

（本需求 sides=backend，无 P-x/C-x；frontend.example.md 是假想变体，不进本对照。
反向检查已做：I-1~I-3 / S-1~S-3 / TC-1~TC-7 全部有主，无超范围设计。）

（起草记录：第一稿 FR-4 / FR-6 的用例格为 0——按覆盖完整性规则回退 design，
补了 TC-6 / TC-7 两份用例后才回本节点更新对照、提请批准。）
