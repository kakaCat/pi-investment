---
design_exempt: "单函数修改，无架构变更"
---

# 架构设计文档

**需求ID**: REQ-260926205654-163a

## 架构变更 «serves: FR-1, FR-2»

**无架构变更**。本需求仅修改一个内部工具函数 `formatTimestamp`，不涉及：
- 模块结构调整
- 组件间通信变更
- 依赖关系改变
- 新增或删除模块

## 受影响的模块 «serves: FR-1»

**单一模块**：`packages/web/dsh-pmboard/src/shared/protocol.ts`

**函数调用链**：
```
newRequirementId()  [exported function]
  └─> formatTimestamp()  [private function, 此处修改]
```

**隔离性**：`formatTimestamp` 是私有函数，仅被 `newRequirementId` 调用，改动完全隔离。

## 兼容性 «serves: FR-3»

- **向后兼容**：旧编号格式继续有效
- **接口不变**：`newRequirementId` 签名和调用方式不变
- **数据兼容**：编号作为字符串存储，格式变化不影响存储和查询
