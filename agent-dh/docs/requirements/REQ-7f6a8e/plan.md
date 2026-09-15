# 实施计划：需求详情页文档记录展示

> REQ-7f6a8e · 目标：需求详情页聚合展示该需求关联的文档（需求/UI/设计/计划/验收/复盘），借鉴 superpowers 文档要求

## 目标

需求详情页新增「📁 文档记录」区块，聚合展示 docLinks（requirement/ui/proposal）+ plan.path + archive.docs，让"这个需求产生了哪些文档、在哪"一眼可见。

## 做法

1. **前端文档区块**：DOC_KIND_META 类型映射 + collectReqDocs 聚合去重 + renderDocSection 渲染，插入需求描述之后。
2. **文档记录填充机制**：解决 docLinks 从未被 agent 填充的问题——定义文档创建规范（借鉴 superpowers），让 agent 建文档时回填 docLinks 或走归档文档清单。

## 任务表

| key | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---|---|---|---|---|---|
| t1 | 需求详情页文档记录区块（前端展示） | implement | frontend | — | 详情页出现「📁 文档记录」，聚合 docLinks+plan.path+archive.docs，7 类文档图标+路径，空时给引导 |
| t2 | 文档创建规范 + docLinks 填充机制 | doc | doc | t1 | 定义需求应产出的文档类型与记录时机；补齐 docLinks 填充路径（工具/协议），让记录不再恒空 |

## 说明

- t1 已在头脑风暴阶段先行实现（前端纯展示，复用已有字段，无后端改动）。
- t2 是"记录机制"层，借鉴 superpowers 的文档理念：文档类型明确 + 需求记录引用路径 + 可追溯。
