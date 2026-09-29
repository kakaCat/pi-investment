# t-fc43f2 超时归位：投递/查询类工具不再挂交互式长超时·复核

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

## 在做什么
超时归位：投递/查询类工具不再挂交互式长超时·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-09-27T10:44:12.824Z，窗口 c811ef10-a880-432a-bff4-f15585116c0f）

FR-6 复核结论：无偏离（逐条依据见下）。设计 architecture.md「上述工具 timeoutMs 归位到 timeoutWriteMs/timeoutReadMs」与实现逐项一致；TC-12 静态判定独立复跑 0 命中；仅登记一条已知取舍（同步兼容路径）供人工知悉，非缺陷。

### 完成项

- 【无偏离】FR-6 逐条核对（依据：design/architecture.md 第 28 行 + test-cases.md TC-12 + requirement.md 第 124-127/157-159 行）：task_run→timeoutWriteMs（AdvanceTool.ts:72）、task_execute（别名，无独立值，经同一 factory 继承，TC-12a 深比较相等）、run_status→timeoutReadMs（RunStatusTool.ts:67）、task_status→timeoutReadMs（TaskStatusTool.ts:77）——四工具与设计一一对应，无遗漏、无错配
- 【无偏离·旁证】同族旁证工具取值同源一致：task_tree→timeoutReadMs（TaskTreeTool.ts:83）、task_move→timeoutWriteMs（TaskMoveTool.ts:68）、task_report→timeoutReadMs（TaskReportTool.ts:52），均为「查询读档 / 写入写档」口径
- 【无偏离·范围】全 src/tools 复核仍取 timeoutInteractiveMs 的仅 AskConfirmTool.ts:72 与 CaptureTool.ts:68（AcceptSheetTool 用 timeoutSheetMs），均为需人作答的弹框类——正是 requirement.md 明示「不在本需求范围，允许保留」的那类
- 【无偏离·独立复跑】TC-12 判定命令重跑：grep -rc timeoutInteractiveMs 于 AdvanceTool/TaskExecuteTool/RunStatusTool/TaskStatusTool 四个目录 → 全部 0 命中（grep 退出码 1）；联调用例 timeout-routing-integration(4) + 契约门禁 tools-schema(40) + output-contract(26) → 3 文件 70 tests 全绿，exit 0（复核者独立执行，非引用上游输出）
- 【无偏离·契约面】timeoutMs 属工具壳内部配置，不进 parameters/output.schema：I-1/I-2/I-4 的报文形状未受影响（output-contract/tools-schema 全绿即证据）
- 【无偏离·注释一致性】AdvanceTool 原「30s 写档会掐断，恢复交互档」注释已被 dev 改写为 FR-6 归位依据（注明交互档只服务弹框类、JobsPort 已修复），不存在注释与代码互相矛盾的残留
- 【登记·非缺陷】同步兼容路径（deps.jobs 未装配的内存测试/嵌入调用，AdvanceChain.ts:412）仍可能跑过 30s 被写档掐断。判定：非对设计的偏离——FR-6 明示要求非交互档，且线上走投递式路径（联调样例 6 实测认领+投递后立即返回 dispatched，耗时毫秒级 << 30s），该路径不构成线上路径；作为已知取舍登记，不再改动，是否加档位说明留人工裁决
- 【判据可信度】以上均为只读复核：grep + 独立跑测试 + 读源码行号；本卡未改任何文件，不制造 filesChanged 充数（结论族凭证形态）

---
