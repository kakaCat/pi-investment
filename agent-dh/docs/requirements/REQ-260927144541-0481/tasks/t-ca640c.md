# t-ca640c 一眼看清父子：新增「父卡→子卡」结构查询·测试

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

## 在做什么
一眼看清父子：新增「父卡→子卡」结构查询·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

## 汇报 1（2026-09-27T10:33:44.143Z，窗口 session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）

测试：本卡验收命令全绿——task-tree 6/6、tools-schema 40/40、output-contract 26/26，合计 72 passed / exit 0（2026-09-27 18:33 本机实跑）。新增工具已纳入全工具 schema 构造，返回体键与声明逐一对齐。

### 完成项

- vitest run tests/task-tree.test.ts → 6 passed（TC-5 父卡+4子卡按链序 / TC-6 无子卡 []+note / TC-7 跨窗口拒绝 / 未绑定与不存在错误码）
- vitest run tests/tools-schema.test.ts → 40 passed（defineTaskTreeTool 已纳入全工具 schema 构造）
- vitest run tests/output-contract.test.ts → 26 passed（声明键 ⊇ 实际 return 键）
- 合计 Test Files 3 passed (3) / Tests 72 passed (72)，exit 0
- 线上实调佐证：reqboard_task_tree 多次成功返回本需求 8 条父卡链结构

### 下一步

父卡 t-acd60f 汇总收尾

---
