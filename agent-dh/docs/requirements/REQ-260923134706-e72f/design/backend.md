---
requirement_refs: [FR-2, FR-6]
sides: [backend]
---

# 后端设计（REQ-260923134706-e72f）

## 服务与接口实现 <!-- serves: FR-6 -->

| 编号 | 类型 | 名称 | 职责说明 | 输入 | 输出 | 调用方 | 依赖 | serves |
|---|---|---|---|---|---|---|---|---|
| BE-1 | 路由 | isolation router | 把隔离留痕只读暴露给看板 | window?, k? | IsolationLogResponse | client node-panel | IsolationTraceFile.readAll | FR-6 |
| BE-2 | 改动 | routes.ts 注册 | 挂载 GET isolation-log | - | - | host | - | FR-6 |
| BE-3 | 改动 | index.ts 接线 | isolationTrace 以只读端口传入路由 deps | - | - | host | 既有实例 | FR-6 |
| BE-4 | 改动 | stages.ts progress | requirement 对象补 promptDifficulty | - | 增量字段 | client | RequirementRecord | FR-2 |

## 数据流 <!-- serves: FR-6 -->

```
IsolateNodeContext（既有，节点结算时写留痕）
   → IsolationTraceFile → state/node-isolation-log.json（ring buffer 200 条）
   → isolation router（readAll → window 过滤 → 取最近 k 条 → JSON）
   → client fetchIsolationLog → node-panel 取该 stage 最新一条渲染
```

## 关键逻辑 <!-- serves: FR-6 -->

- BE-1 照抄 `http/routers/injection.ts`：k 校验（1..200 整数否则 400）、端口缺省 → `available:false` + 空清单、
  window 过滤、只读（不写不删）。
- 读口：`IsolationTraceFile.readAll()`（缺文件 → []；损坏 → 抛错——路由层 catch 后降级 available=false，看板不红）。
- BE-4 一行透传：`promptDifficulty: target.promptDifficulty ?? null`（老记录无字段 → null，client 省略该行）。

## 错误处理 <!-- serves: FR-6 -->

| 场景 | 状态码/行为 | 重试 |
|---|---|---|
| k 非法 | 400 PARAM 类（badInput，与 injection-log 同文案口径） | 调用方修正 |
| 留痕文件不存在 | 200 + available=true + entries=[] | - |
| 留痕文件损坏 | 200 + available=false + entries=[]（日志告警） | 修复文件后自愈 |
| 留痕端口未装配 | 200 + available=false + entries=[] | - |

## 数据库设计 <!-- serves: FR-6 -->

**不改表、不改 schema、无迁移**。留痕数据源是既有 JSON ring buffer 文件（state/ 下），本需求只读。

## 性能考量 <!-- serves: FR-6 -->

ring buffer 上限 200 条，readAll 全量读也在百 KB 内；k≤200 硬上限防一把拉全量；面板打开才请求，15s 轮询不重复拉留痕（仅 overview 走既有刷新）。

## 安全设计 <!-- serves: FR-6 -->

只读端点，无写入面；window 参数仅用于过滤，不拼路径不拼 SQL；留痕内容为本插件自产数据，无用户输入透传。
