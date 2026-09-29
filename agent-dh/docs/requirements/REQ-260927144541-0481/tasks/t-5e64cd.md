# t-5e64cd 门禁固化：声明与行为不一致由测试拦住

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
门禁固化：声明与行为不一致由测试拦住

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
vitest run tests/output-contract.test.ts tests/tools-schema.test.ts 全绿；故障注入（临时给某工具加未声明返回键）在该测试内被验证为变红。

## 实施方案（implementation）
tools-schema.test.ts 构造全部已注册工具；output-contract.test.ts 补 TaskTreeTool 响应源映射与全工具扫描；新增参数 DSL 形状检测与故障注入用例。

## 上游产出摘要（dependsSummary）
- 链只留一个入口：起链工具收口，别名不再各跑一套
- 一眼看清父子：新增「父卡→子卡」结构查询
- 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落
- 推错状态要说清：报错带上角色与合法边，验收标准能当场改
- 超时归位：投递/查询类工具不再挂交互式长超时

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
