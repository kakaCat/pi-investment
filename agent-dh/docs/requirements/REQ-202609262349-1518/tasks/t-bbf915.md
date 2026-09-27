# t-bbf915 RTM 快速读取接口

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
RTM 快速读取接口

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
读取 RTM 文件成功（node -e "const {readRTM}=require('./dist/domain/rtm/reader.js');console.log(readRTM('REQ-test','design')?.metadata?.stage)" 输出 design） && 性能 <10ms（time node -e "for(let i=0;i<100;i++)readRTM(...)" 的 real 时间 <1.0s） && 文件不存在时返回 null（readRTM('REQ-nonexistent','design') 输出 null）

## 实施方案（implementation）
创建 src/domain/rtm/reader.ts 实现 readRTM 函数（读取 docs/requirements/{id}/rtm-{stage}.yml → js-yaml 解析 → 返回 RTMFile 对象或 null），支持所有节点，性能目标 <10ms

## 上游产出摘要（dependsSummary）
- 扩展台账数据模型

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T01:36:06.750Z，窗口 session-9f2c6c84-0d41-41b8-b4ce-2d1c7e50bf32）

RTM 读取接口在位：file-io.ts 的 readRTM(filePath) / readRTMStrict / readRTMWithFallback，文件缺失或解析失败返回 null 不抛错（FR-9 降级）。⚠️ 与计划签名 readRTM(requirementId, stage) 不同（收文件路径），功能等价；且锚点 dist/domain/rtm/reader.js 不存在。

### 完成项

- readRTM 在位（file-io.ts）
- file-io.test.ts 8 测试通过

### 改动文件

- `packages/tools/reqboard/src/rtm/file-io.ts`

### 下一步

状态推进需在看板操作或由具备 reqboard_task_move 的通道完成；本卡验收标准锚点已失效，建议先修订验收标准。

---
