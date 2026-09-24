---
requirement_refs: BUG-1, BUG-2
---

# 架构设计 · REQ-260922182505-0924

## 分层处置原则 `serves: BUG-1`

http 层（路由）与 client 层（面板）整体删除；application 判定层摘除函数与调用点；domain 层删两个只为 triage 服务的判定函数；shared/适配器层的**数据契约冻结不动**（triages 字段留作只读遗留数据通道）。删除顺序：先摘调用方（capture/create/QueryState/前端）→ 再删定义（window/support/Predicates）→ 最后删路由与文件，每步 tsc 可编译。

## 不变式 `serves: BUG-1`

老台账加载行为逐字节不变（v4 fixture 的 migration 测试不动且必须保持绿）；rollup 对存量 resolved 记录的读取语义不变；reqboard_capture/create 的其余前置检查（窗口绑定、FR-5 拒绝粘滞）原样保留。
