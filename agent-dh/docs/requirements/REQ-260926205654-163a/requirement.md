# 需求文档：修复 PM 插件需求编号格式为 REQ-年月日小时分钟-编号

**需求ID**: REQ-260926205654-163a  
**类型**: feature  
**状态**: design  
**创建时间**: 2026-09-26

## 1. 一句话目标

修复 PM 插件（dsh-pmboard）的需求编号生成逻辑，使其生成符合规范的格式：**REQ-年月日小时分钟-编号**（YYYYMMDDHHmm，14位时间戳，4位年份，不含秒）。

## 2. 边界

### 做什么
- 修改 `packages/web/dsh-pmboard/src/shared/protocol.ts` 中的 `formatTimestamp` 函数
- 将年份从2位改为4位（yy -> YYYY）
- 移除秒字段（ss）的生成和拼接
- 更新函数注释说明格式为 YYYYMMDDHHmm

### 不做什么
- 不修改随机编号部分的生成逻辑（保持4位hex）
- 不修改任务ID（`newTaskId`）和执行ID（`newExecutionId`）的生成逻辑
- 不修改已存在的需求编号（向后兼容，旧编号保持不变）
- 不添加编号格式的历史迁移逻辑
- 不修改编号解析或验证逻辑

## 3. 产品定义

### 背景
PM 插件当前生成的需求编号格式为 `REQ-YYMMDDHHmmss-xxxx`（2位年份+含秒），不符合项目规范。用户期望的格式为 `REQ-YYYYMMDDHHmm-xxxx`（4位年份+不含秒）。

### 价值
- **规范统一**：需求编号符合项目命名规范
- **可读性提升**：4位年份更清晰，无Y2100风险
- **精度适中**：分钟级精度足够，加上4位随机hex无碰撞风险

### 影响范围
- **新需求**：修改后创建的所有需求使用新格式
- **旧需求**：保持向后兼容，旧编号继续有效
- **系统功能**：不影响需求管理的其他功能

## 4. 用户与角色

### 主要用户
- **Agent（AI Agent）**：通过 `reqboard_capture` 工具创建需求时，自动生成符合规范的编号
- **人工用户**：通过看板手动创建需求时，生成符合规范的编号

### 次要用户
- **开发者**：查看需求编号时，能从4位年份快速识别需求创建年份

### 角色无关性
此修改对所有角色透明，不需要用户行为改变。

## 5. 功能点

### FR-1：生成4位年份时间戳
**描述**：`formatTimestamp` 函数生成 YYYYMMDDHHmm 格式的时间戳（14位，4位年份，不含秒）

**输入**：Date 对象（可选，默认当前时间）

**输出**：14位字符串，格式为 YYYYMMDDHHmm
- YYYY：4位年份（如 2026）
- MM：2位月份（01-12）
- DD：2位日期（01-31）
- HH：2位小时（00-23）
- mm：2位分钟（00-59）

**示例**：
- 输入：2026-09-26 20:57:00
- 输出：`202609262057`

### FR-2：新需求编号使用新格式
**描述**：`newRequirementId` 函数生成的编号使用新的时间戳格式

**输出格式**：`REQ-{14位时间戳}-{4位hex}`
- 前缀：`REQ-`
- 时间戳：14位（YYYYMMDDHHmm）
- 分隔符：`-`
- 随机编号：4位小写hex（0000-ffff）

**示例**：
- `REQ-202609262057-a1b2`
- `REQ-202609262058-f3e4`

### FR-3：向后兼容旧编号
**描述**：系统继续支持旧格式的需求编号（2位年份）

**旧格式示例**：
- `REQ-260926205736-28e4`（2位年+秒）

**兼容性保证**：
- 旧编号可以正常访问
- 旧编号可以正常推进状态
- 新旧编号可以混用

## 6. 可证伪判定标准

**验收命令**：创建新需求时，生成的编号格式为 `REQ-YYYYMMDDHHmm-xxxx`（14位时间戳 + 4位随机hex）。

**验证步骤**：
1. 重启 DSH 服务应用代码变更
2. 通过 `reqboard_capture` 工具创建新需求
3. 检查生成的 requirement_id 格式
4. 时间戳部分应为14位（YYYYMMDDHHmm），年份为4位，不含秒字段
5. 随机编号部分保持4位hex不变

**期望结果**：
- ✅ 格式匹配：`REQ-\d{14}-[0-9a-f]{4}`
- ✅ 年份为4位：前4位为2026等
- ✅ 不含秒：同一分钟创建多个需求，时间戳部分相同
- ✅ 旧需求可访问：2位年份的旧编号仍可正常使用

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t1 |
| FR-2 | 🔴 **未被接收** | — |
| FR-3 | 🔴 **未被接收** | — |

> 🔴 **未被接收（2 条）**：FR-2、FR-3

<!-- reqboard:marks:end -->

## 7. 问题分析

### 7.1 当前状态
- **文件位置**：`packages/web/dsh-pmboard/src/shared/protocol.ts`
- **问题函数**：`formatTimestamp()` (第1137-1145行)
- **当前实现**：生成 `YYMMDDHHmmss` 格式（14位，2位年+含秒）
- **当前输出示例**：`REQ-260926205736-28e4`

### 7.2 期望状态
- **期望格式**：`YYYYMMDDHHmm` （14位，4位年+不含秒）
- **期望输出示例**：`REQ-202609262057-a1b2`

### 7.3 差异
- 年份从2位改为4位（增加2位）
- 删除秒字段（减少2位）
- 时间戳总长度保持14位不变

## 8. 技术实现要点

### 8.1 修改点
**文件**：`packages/web/dsh-pmboard/src/shared/protocol.ts`

**修改前**（第1136-1145行）：
```typescript
/** 格式化时间戳为 YYMMDDHHmmss（精确到秒）。 */
function formatTimestamp(date: Date = new Date()): string {
  const yy = date.getFullYear().toString().slice(-2)
  const MM = (date.getMonth() + 1).toString().padStart(2, '0')
  const DD = date.getDate().toString().padStart(2, '0')
  const HH = date.getHours().toString().padStart(2, '0')
  const mm = date.getMinutes().toString().padStart(2, '0')
  const ss = date.getSeconds().toString().padStart(2, '0')
  return \`\${yy}\${MM}\${DD}\${HH}\${mm}\${ss}\`
}
```

**修改后**：
```typescript
/** 格式化时间戳为 YYYYMMDDHHmm（4位年份，精确到分钟）。 */
function formatTimestamp(date: Date = new Date()): string {
  const YYYY = date.getFullYear().toString()
  const MM = (date.getMonth() + 1).toString().padStart(2, '0')
  const DD = date.getDate().toString().padStart(2, '0')
  const HH = date.getHours().toString().padStart(2, '0')
  const mm = date.getMinutes().toString().padStart(2, '0')
  return \`\${YYYY}\${MM}\${DD}\${HH}\${mm}\`
}
```

### 8.2 影响范围
- **直接影响**：`newRequirementId` 函数的输出格式
- **间接影响**：所有新创建的需求编号
- **不影响**：已存在的需求编号（向后兼容）

## 9. 测试验证

### 9.1 单元测试验证
可选：在 `packages/web/dsh-pmboard/src/shared/protocol.test.ts` 中添加测试（如文件不存在，跳过）

### 9.2 手动验证
1. 修改代码后重启 DSH 服务
2. 调用 `reqboard_capture` 创建测试需求
3. 检查返回的 `requirement_id` 格式
4. 确认时间戳部分为14位（YYYYMMDDHHmm），年份为4位

### 9.3 验收标准
- ✅ 新生成的需求编号格式为 `REQ-YYYYMMDDHHmm-xxxx`
- ✅ 时间戳部分长度为14位，年份为4位
- ✅ 随机编号部分长度为4位hex
- ✅ 旧需求编号仍可正常访问和操作

## 10. 轻档理由

### 为什么可以走轻档
1. **改动面小**：只修改1个函数，3行代码变更（年份+秒字段）
2. **无新决策点**：格式规范已明确，无需选型或架构讨论
3. **无依赖变更**：不涉及接口变更、数据模型变更
4. **向后兼容**：旧编号格式不受影响

### 不升级为重档的依据
- 无第二个未定决策
- 不涉及架构变更
- 不涉及新增子系统
- 不涉及数据模型变更

## 11. 风险评估

### 低风险
- 仅影响新创建的需求编号
- 不破坏现有数据
- 可通过代码审查快速验证

### 缓解措施
- 修改前备份原代码
- 在测试环境验证后再部署
- 保持函数签名不变，确保调用方无需修改

## 12. 交付物

- [x] 需求文档：`docs/requirements/REQ-260926205654-163a/requirement.md`（已补充必填节）
- [x] 设计文档：`docs/requirements/REQ-260926205654-163a/design/implementation.md`（已申请豁免）
- [ ] 代码修改：`packages/web/dsh-pmboard/src/shared/protocol.ts`
- [ ] 验证报告：创建测试需求并验证编号格式

## 13. 下一步

按照轻档流程，下一步：**design** — 需求文档已确认，设计文档待确认并推进到拆分阶段。
