# 架构说明（REQ-260924002956-f37c）

## 改动范围

本次为缺陷修复，改动面 = dsh-pmboard 包内 3 个源文件 + 3 个测试文件，不新增能力、不动协议。

## 链路定位

```
用户消息 → hook 登记 pending → 注入立项提示 → reqboard_capture
  → 【弹框题目组装】capture-mapping.ts（拆两段）
  → 【用例编排】CaptureRequirement.ts（拒绝短路 + G0 挪段）
  → 【闸门后置链 H4】h4-resume.ts（无 from 不编现状）
  → 下游：创建/推进/留痕（不变）
```

## 关键决策

| 决策 | 理由 |
|------|------|
| 在调用方（pmboard）实现短路，不改 DSH 框架 | `dsh-user-questions` 的 `intent` 只支持 `plan-review`，没有"选项即终止"语义；改宿主影响所有弹框，超出本单 |
| 第一段 ask 不带 `gate: 'G0'` | 拒绝不是一次闸门作答；若声明 G0，链会把它当"未通过"向窗口回发告警（BUG-2） |
| G0 登记挪到第二段 | 只有肯定分支才是一次完整的闸门作答（四问全部回收 → 创建 → 推进） |
| H4 无 `from` 时不编"节点仍在 {to}" | G0 在 GateCatalog 中没有 `from`，回落到 `to='brainstorming'` 会印出从未存在的节点状态 |
