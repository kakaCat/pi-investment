---
design_exempt: "极简单修改，测试用例已包含在 implementation.md"
---

# 测试用例设计文档

**需求ID**: REQ-260926205654-163a

## 单元测试用例 «serves: FR-1, FR-2»

### TC-1: formatTimestamp 生成正确格式 «serves: FR-1»

**测试目标**：验证 `formatTimestamp` 生成14位时间戳，4位年份，不含秒

**测试代码**：
```typescript
it('should generate 14-digit timestamp with 4-digit year (YYYYMMDDHHmm)', () => {
  const testDate = new Date('2026-09-26T20:57:00')
  const result = formatTimestamp(testDate)
  expect(result).toBe('202609262057')
  expect(result).toHaveLength(14)
  expect(result.substring(0, 4)).toBe('2026')
})
```

### TC-2: newRequirementId 生成正确格式 «serves: FR-2»

**测试目标**：验证需求编号格式为 `REQ-{14digit}-{4hex}`

**测试代码**：
```typescript
it('should generate REQ-{14digit}-{4hex} format', () => {
  const id = newRequirementId(() => 0.5)
  expect(id).toMatch(/^REQ-\\d{14}-[0-9a-f]{4}$/)
  expect(id.substring(4, 8)).toMatch(/^(19|20)\\d{2}$/)
})
```

## 集成测试用例 «serves: FR-2, FR-3»

### TC-3: 创建需求生成新格式编号 «serves: FR-2»

**测试步骤**：
1. 调用 `reqboard_capture` 创建新需求
2. 检查返回的 `requirement_id`

**期望结果**：
- 格式匹配：`REQ-\d{14}-[0-9a-f]{4}`
- 年份为4位：前4位为 `2026`

### TC-4: 旧编号向后兼容 «serves: FR-3»

**测试步骤**：
1. 访问已存在的旧格式需求（如 `REQ-260926205736-28e4`）
2. 验证需求可正常访问和操作

**期望结果**：
- 需求详情正常显示
- 状态可正常推进
- 任务可正常创建

## 验收测试 «serves: FR-1, FR-2, FR-3»

详见 implementation.md 中的验收口径。
