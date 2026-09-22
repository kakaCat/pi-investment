---
requirement_refs: [FR-2, FR-3, FR-4, FR-5]
---

# 后端设计（REQ-example）

## 目录与包结构 <!-- serves: FR-3 -->

```
packages/web/dsh-pmboard/
├── scripts/
│   └── inline-templates.mjs            （新增：构建期生成器）
├── src/
│   ├── application/internal/
│   │   └── template-landing.ts         （新增：落盘钩子）
│   ├── application/SubmitArtifact.ts   （改动：校验前移）
│   └── domain/prompt/generated/
│       └── templates.ts                （生成物，不入库手写）
└── templates/                          （新增：模板源文件包）
```

| 路径 | 内容 | 新增/改动 | 分层归属与理由 |
|---|---|---|---|
| scripts/inline-templates.mjs | 构建期生成器 | 新增 | 构建工具归 scripts/，照抄 inline-prompt-fragments 同款 |
| src/application/internal/template-landing.ts | 落盘钩子 | 新增 | 应用层内部实现，不进 domain |
| src/domain/prompt/generated/templates.ts | 模板常量 | 生成 | 生成物归 generated/，与 fragments.ts 并列 |

## 服务与接口实现 <!-- serves: FR-3 -->

| 编号 | 服务/模块 | 职责 | 关键逻辑 | 改动文件 | serves |
|---|---|---|---|---|---|
| S-1 | TemplateLanding | 节点转移后置落盘 | 选模板→幂等写→登记产物 | src/application/internal/template-landing.ts（新增） | FR-3 |
| S-2 | SubmitArtifact | 提交产物 | kind=requirement 时先跑必填节校验 | src/application/SubmitArtifact.ts（改） | FR-5 |
| S-3 | 阶段提示词组装 | 节点输入包注入 | 追加模板文件指针 + 必填节清单 | src/domain/prompt/（阶段片段，改） | FR-4 |

## 处理时序 <!-- serves: FR-3 -->

```
转移成功      落盘钩子        模板常量        需求目录
 │ 事件        │               │              │
 │ ──────────► │ getTemplate   │              │
 │             │ ────────────► │              │
 │             │ ◄──────────── │ null→告警跳过 │
 │             │ 幂等检查/写入  │ ──────────►  │
 │             │ 写失败→catch  │              │
 │             │ →comments留痕 │              │
```

## 数据访问 <!-- serves: FR-3 -->

写：需求目录文件（fs，相对 profileDir 解析）；artifacts 登记走既有仓储。
并发：同一需求并发转移不存在（转移有乐观锁）；幂等约束兜底重复登记。

（任务与调度节已删——本需求无定时/异步任务，check-templates 属 CI 不属于运行时调度。）
