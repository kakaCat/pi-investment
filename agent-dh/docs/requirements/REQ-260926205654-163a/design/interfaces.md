---
design_exempt: "函数签名不变，仅内部实现调整"
---

# 接口设计文档

**需求ID**: REQ-260926205654-163a

## 公共接口 «serves: FR-2»

### newRequirementId() «serves: FR-2»

**函数签名**（不变）：
```typescript
export function newRequirementId(rand: () => number = Math.random): string
```

**入参**：
- `rand`（可选）：随机数生成函数，默认 `Math.random`

**返回值**：
- 类型：`string`
- 格式（修改前）：`REQ-YYMMDDHHmmss-xxxx`
- 格式（修改后）：`REQ-YYYYMMDDHHmm-xxxx`

**调用方式**（不变）：
```typescript
const reqId = newRequirementId();
// 修改前输出：REQ-260926205736-28e4
// 修改后输出：REQ-202609262057-a1b2
```

## 私有接口 «serves: FR-1»

### formatTimestamp() «serves: FR-1»

**函数签名**（不变）：
```typescript
function formatTimestamp(date: Date = new Date()): string
```

**返回值格式变更**：
- 修改前：`YYMMDDHHmmss`（14位）
- 修改后：`YYYYMMDDHHmm`（14位）

**可见性**：私有函数，外部不可访问。
