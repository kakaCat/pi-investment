# t-cf2b22 实现 StageOverview 的 RTM 读取接口

> 需求：REQ-260926140539-457b RTM YAML 追溯基础设施 - Dive 模式自动化的数据底座

## 在做什么
实现 StageOverview 的 RTM 读取接口

## 解决什么问题
创建 src/stage-overview/rtm-reader.ts，实现 readStageRTM(reqId, stage) 与 readLifecycleRTM(reqId)，文件不存在返回 null。

## 得到什么结果
运行单元测试 `pnpm test rtm-reader.test.ts` 通过；readStageRTM 返回含 outputs/traceability/coverage 的对象；文件删除后返回 null 且不抛异常

---
## 汇报 1（2026-09-26T10:32:49.530Z，窗口 session-c5ea210f-afc3-4735-a4d1-f9058b378363）

这一步做完，会话节点能直接读 RTM 快照（读不到就返回「没有」，不报错），为追溯展示和 Dive 决策提供入口。

### 完成项

- readStageRTM / readLifecycleRTM / readDesignRTM / readDecomposingRTM / readAcceptingRTM
- 缺失返回 null（降级入口）
- 5 条单测覆盖读取与缺失

### 改动文件

- `packages/tools/reqboard/src/stage-overview/rtm-reader.ts`
- `packages/tools/reqboard/tests/rtm/stage-overview.test.ts`

---
