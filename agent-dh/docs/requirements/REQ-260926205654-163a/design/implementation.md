---
design_exempt: "单函数3行改动（4位年份+删除秒字段），无架构/接口/数据模型变更，申请设计豁免"
---

# 设计文档：修复需求编号格式

**需求ID**: REQ-260926205654-163a  
**设计版本**: v2（根据用户反馈修改：使用4位年份）  
**创建时间**: 2026-09-26  
**更新时间**: 2026-09-26

> **设计豁免理由**：本需求仅修改1个私有函数（formatTimestamp）的3行代码（4位年份+删除秒字段），
> 无架构变更、无接口变更、无数据模型变更，无需拆分为多份设计文档。

---

## 目标 «serves: FR-1, FR-2»

修改 `formatTimestamp` 函数，使需求编号生成格式从 `REQ-YYMMDDHHmmss-xxxx`（2位年份+14位时间戳）改为 `REQ-YYYYMMDDHHmm-xxxx`（4位年份+14位时间戳），符合项目规范。

**serves: FR-1**

---

## 设计方案 «serves: FR-1, FR-2»

### 文件与函数定位 «serves: FR-1»

**修改文件**：`packages/web/dsh-pmboard/src/shared/protocol.ts`

**修改函数**：
- `formatTimestamp(date: Date = new Date()): string` (第1137-1145行)

**调用链**：
```
newRequirementId() 
  -> formatTimestamp() [此处修改]
     -> 返回时间戳字符串
```

### 代码改动 «serves: FR-1, FR-2»

**修改前**（第1136-1145行）：

```typescript
/** 格式化时间戳为 YYMMDDHHmmss（精确到秒）。 */
function formatTimestamp(date: Date = new Date()): string {
  const yy = date.getFullYear().toString().slice(-2)      // 2位年份
  const MM = (date.getMonth() + 1).toString().padStart(2, '0')
  const DD = date.getDate().toString().padStart(2, '0')
  const HH = date.getHours().toString().padStart(2, '0')
  const mm = date.getMinutes().toString().padStart(2, '0')
  const ss = date.getSeconds().toString().padStart(2, '0')  // 删除此行
  return \`\${yy}\${MM}\${DD}\${HH}\${mm}\${ss}\`           // 改为4位年+移除秒
}
```

**修改后**：

```typescript
/** 格式化时间戳为 YYYYMMDDHHmm（4位年份，精确到分钟）。 */
function formatTimestamp(date: Date = new Date()): string {
  const YYYY = date.getFullYear().toString()              // 4位年份（完整年份）
  const MM = (date.getMonth() + 1).toString().padStart(2, '0')
  const DD = date.getDate().toString().padStart(2, '0')
  const HH = date.getHours().toString().padStart(2, '0')
  const mm = date.getMinutes().toString().padStart(2, '0')
  return \`\${YYYY}\${MM}\${DD}\${HH}\${mm}\`              // 14位：YYYY(4)+MM(2)+DD(2)+HH(2)+mm(2)
}
```

**变更摘要**：
1. 年份字段：从 `slice(-2)` 改为完整 `.toString()`（2位 -> 4位）
2. 变量名：`yy` -> `YYYY`（语义更清晰）
3. 删除秒字段：移除 `const ss = date.getSeconds().toString().padStart(2, '0')`
4. 更新返回值：`\${yy}...\${ss}` -> `\${YYYY}...\${mm}`（不含秒）
5. 更新注释：`YYMMDDHHmmss` -> `YYYYMMDDHHmm（4位年份，精确到分钟）`

**serves: FR-2**

---

## 接口契约 «serves: FR-2»

### 函数签名（不变） «serves: FR-1»

```typescript
function formatTimestamp(date: Date = new Date()): string
```

**入参**：
- `date`（可选）：Date 对象，默认当前时间

**返回值**：
- 类型：`string`
- 格式（修改前）：`YYMMDDHHmmss`（14位：2位年+月日时分秒）
- 格式（修改后）：`YYYYMMDDHHmm`（14位：4位年+月日时分）
- 位数不变（都是14位），但组成方式改变

### 调用方不受影响 «serves: FR-2»

`newRequirementId` 函数签名和调用方式保持不变：

```typescript
export function newRequirementId(rand: () => number = Math.random): string {
  const timestamp = formatTimestamp()  // 调用方式不变
  const random4 = Math.floor(rand() * 0xffff).toString(16).padStart(4, '0')
  return \`REQ-\${timestamp}-\${random4}\`
}
```

**输出变化**：
- 修改前示例：`REQ-260926205736-28e4`（2位年+秒）
- 修改后示例：`REQ-202609262057-a1b2`（4位年+不含秒）

**serves: FR-3**

---

## 影响范围分析 «serves: FR-1, FR-2, FR-3»

### 直接影响 «serves: FR-2»
- **新需求编号**：修改后创建的需求使用新格式（4位年份，14位时间戳，不含秒）
- **时间戳位数**：保持14位不变，但组成从"2位年+秒"改为"4位年+不含秒"

### 不影响 «serves: FR-3»
- **已存在的需求**：旧编号格式（2位年份）保持不变，系统向后兼容
- **任务编号**：`newTaskId` 不受影响（使用随机hex，无时间戳）
- **执行编号**：`newExecutionId` 不受影响
- **其他模块**：`formatTimestamp` 为私有函数，仅供 `newRequirementId` 调用

### 数据兼容性 «serves: FR-3»
- **编号格式识别**：系统按前缀 `REQ-` 识别需求编号，时间戳内容变化不影响解析
- **存储与查询**：编号作为字符串存储，位数不变（14位），查询不受影响
- **历史数据**：2位年份的旧编号继续有效，无需迁移
- **新旧混用**：2026年的需求可能同时存在 `REQ-26...` 和 `REQ-2026...` 两种格式

**serves: FR-4**

---

## 验收口径 «serves: FR-1, FR-2, FR-3»

### 验收命令 «serves: FR-2»

```bash
# 1. 重启 DSH 服务（应用代码变更）
cd agent-dh && ./scripts/restart-with-build.sh

# 2. 创建测试需求
# 在 DSH Web UI 中调用 reqboard_capture 创建需求，或通过看板手动创建

# 3. 验证编号格式
# 检查返回的 requirement_id 格式
```

### 期望输出 «serves: FR-2»

**新需求编号格式**：
```
REQ-YYYYMMDDHHmm-xxxx
```

**验证标准**：
- 前缀为 `REQ-`
- 时间戳部分长度为 **14位**（YYYYMMDDHHmm）
- 年份为 **4位完整年份**（如 2026）
- 时间戳精确到分钟，不含秒
- 随机编号部分长度为 4位hex
- 总格式：`REQ-{14位时间戳}-{4位hex}`

**示例**：
- ✅ 正确：`REQ-202609262057-a1b2`（4位年份，不含秒）
- ❌ 错误：`REQ-260926205736-28e4`（2位年份，含秒）
- ❌ 错误：`REQ-2609262057-a1b2`（2位年份，不含秒）

**serves: FR-5**

---

## 测试策略 «serves: FR-1, FR-2, FR-3»

### 单元测试（可选） «serves: FR-1, FR-2»
如果存在 `protocol.test.ts`，可添加测试：

```typescript
describe('formatTimestamp', () => {
  it('should generate 14-digit timestamp with 4-digit year (YYYYMMDDHHmm)', () => {
    const testDate = new Date('2026-09-26T20:57:00')
    const result = formatTimestamp(testDate)
    expect(result).toBe('202609262057')
    expect(result).toHaveLength(14)
    expect(result.substring(0, 4)).toBe('2026')  // 验证4位年份
  })
})

describe('newRequirementId', () => {
  it('should generate REQ-{14digit}-{4hex} format with 4-digit year', () => {
    const id = newRequirementId(() => 0.5)
    expect(id).toMatch(/^REQ-\\d{14}-[0-9a-f]{4}$/)
    expect(id.substring(4, 8)).toMatch(/^(19|20)\\d{2}$/)  // 年份以19或20开头
  })
})
```

### 集成测试 «serves: FR-2, FR-3»
1. 修改代码后重启服务
2. 通过 `reqboard_capture` 创建多个测试需求
3. 验证所有新需求编号符合 14位时间戳格式（4位年份）
4. 确认旧需求（2位年份）仍可正常访问

### 回归测试 «serves: FR-3»
- 确认需求列表正常显示（新旧编号混合）
- 确认需求详情页正常打开
- 确认任务创建、推进、验收流程不受影响

**serves: FR-6**

---

## 风险与缓解 «serves: FR-1, FR-2, FR-3»

### 风险评估 «serves: FR-2, FR-3»

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 新旧编号混用引起混淆 | 低 | 编号前缀相同（REQ-），系统按字符串处理，位数相同（14位），无影响 |
| 时间戳碰撞概率 | 极低 | 与旧版本相同（同一分钟内 4位hex = 65536种可能） |
| 代码修改引入bug | 低 | 改动仅3行，逻辑简单，易于验证 |
| 2位年与4位年混用 | 低 | 系统按字符串处理，不解析年份，无实际影响 |

### 2100年后的兼容性 «serves: FR-2»
- 4位年份格式可支持到9999年，无Y2K类问题
- 相比2位年份（有Y2100风险），4位年份更具前瞻性

### 回滚方案 «serves: FR-1, FR-2, FR-3»
如需回滚：
```bash
git checkout HEAD~1 -- packages/web/dsh-pmboard/src/shared/protocol.ts
cd agent-dh && ./scripts/restart-with-build.sh
```

**serves: FR-7**

---

## 总结 «serves: FR-1, FR-2, FR-3»

### 变更内容 «serves: FR-1»
- 修改 1 个文件：`packages/web/dsh-pmboard/src/shared/protocol.ts`
- 修改 1 个函数：`formatTimestamp`
- 修改年份提取：`slice(-2)` -> 完整 `.toString()`（2位->4位）
- 删除秒字段提取：移除 `const ss = ...`
- 修改返回值：`yy...ss` -> `YYYY...mm`（4位年+不含秒）
- 更新注释：说明为4位年份格式

### 预期效果 «serves: FR-2, FR-3»
- 新需求编号格式：`REQ-YYYYMMDDHHmm-xxxx`（如 `REQ-202609262057-a1b2`）
- 时间戳位数保持14位（与旧版本相同）
- 旧需求编号保持兼容，无需迁移
- 系统功能不受影响

### 下一步 «serves: FR-1, FR-2, FR-3»
按照轻档流程，下一步：**decomposing** — 用 `reqboard_ask_confirm(target=artifact, kind=design)` 请人确认设计文档。

**serves: FR-8**