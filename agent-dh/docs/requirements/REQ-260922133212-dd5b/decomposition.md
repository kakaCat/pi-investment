# 拆分计划 · REQ-260922133212-dd5b

目标：归档目录校验兼容新旧两种 REQ id 格式，并用补交 REQ-260922012924-2e29 归档材料做线上闭环实证。
做法：一张实施卡改正则+补单测（就近新建 tests/requirement-dir-pattern.test.ts），一张实证卡部署后补交归档材料并核验台账 archive 字段；bug 类无设计文档集要求，契约已在 design/design.md 定死。

## 任务表

| key | title | phase | side | depends_on | requirement_refs |
|-----|-------|-------|------|-----------|------------------|
| t1 | [BUG-1] 归档目录校验兼容新旧两种需求 id 格式 | implement | backend | — | BUG-1 |
| t2 | [BUG-2] 部署并补交 REQ-260922012924-2e29 归档材料闭环验证 | test | backend | t1 | BUG-2 |
