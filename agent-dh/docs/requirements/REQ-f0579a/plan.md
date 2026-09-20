# REQ-f0579a 拆分计划：dsh-pmboard 审计整改

## 目标

审计发现的 17 个失败测试清零，且每处修复对症根因（不是为绿而绿）。

## 做法

按根因分 5 个任务，全部改动落在 dsh-pmboard 包内；每个任务跑定向测试验证，
最后全量 vitest + typecheck + 构建核验收尾。

## 任务表

| key | 任务 | 验收 |
|-----|------|------|
| t1 | 修 verdicts.ts 覆盖留痕：删 52-89 早退分支，覆盖走统一路径（留痕三处） | verify-override/acceptance-archive/e2e-accept-override 共 5 例转绿 |
| t2 | 恢复看板视图：done 归验收泳道 + 归档条 + 产物标签（种类名·文件名） | client-view/board-info-fixes 相关 3 例转绿；af8a2ac0 真名诉求不破 |
| t3 | 精确化操作条断言：验收态禁止推进类 move-req、允许立项取消 | board-info-fixes 2 例转绿；b2b37d9b 新用例不破 |
| t4 | 门禁债：RESPONSE_SOURCES 补登 2 工具、状态词汇下沉 domain、timeoutMs 用 LIMITS、pagination 拼接改模板串 | output-contract/layer-boundary/tools-dispatch/message-hygiene 共 5 例转绿 |
| t5 | 尺寸与杂项：index.ts 拆到 ≤400、base.ts 拆到 ≤400、删 .backup、markdown 链接协议白名单 | size-budget 转绿；全量 vitest + typecheck + build + verify-client-build 全绿 |

## 依赖

t1..t4 相互独立；t5 最后做（尺寸拆分可能受前序改动影响，且它承担全量终验）。
