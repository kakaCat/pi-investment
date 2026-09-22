---
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5
---

# 架构设计 · REQ-260922012924-2e29

## 总体结构 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

五处改动分属 dsh-pmboard 四层、互不耦合：测试层（tests/capture-tool.test.ts）→ application 纯函数（node-input-package.ts 的 requirementDocPath）→ 配置层（config/cordis.yml）→ 接口层（stages.handleState + 客户端 open-doc/显示）。台账 schema 零改动：路径一律存相对，根仅存在于运行时解析层——"存储相对、显示绝对"。

## 依赖方向与落点 `serves: FR-2, FR-4, FR-5`

FR-2 只动 application/internal 纯函数（domain 无感）；FR-4 服务端在 http/routers/stages.ts 的 handleState 增字段（deps.cwd ?? process.cwd() 现有注入口），客户端在 board-mount/conversation-progress 拼绝对路径；FR-5 在 application/use-cases/CaptureRequirement.ts 增留痕写 + 前置检查，留痕文件 state/capture-rejections.json 走与 IsolationTraceFile 同款 ring buffer 原子写适配器模式。无跨包改动、无新依赖。

## 不变式 `serves: FR-3, FR-5`

压缩算法 isolateNodeContext 一行不动（三条纪律仍在用例内部执行）；四问题目/选项/注入文案不动；拒绝留痕写失败必须降级不阻断"未立项"返回（留痕是增强不是门槛）。
