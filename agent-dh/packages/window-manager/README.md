# Window Manager Plugin

窗口管理工具插件 - 用于测试和演示多窗口协作功能

## 功能概述

提供 4 个工具来创建、管理和清理测试窗口，用于：
- 演示多窗口协作机制
- 测试 office_roster 等办公室工具
- 快速搭建测试场景
- 验证窗口管理 API

## 安装

插件已集成到 DSH investment profile，无需额外安装。

## 工具列表

### 1. window_create

创建单个测试窗口。

**参数**：
- `name` (string, required): 窗口名称，如 "今天股市分析"
- `role` (string, optional): 窗口角色，可选 investor/researcher/trader/monitor/analyst，默认 investor
- `capabilities` (array, optional): 能力列表，如 ["trading", "analysis"]
- `status` (string, optional): 初始状态，可选 idle/active，默认 idle

**示例**：
```
调用 window_create 工具，参数：
- name: "今天股市分析"
- role: "investor"
- capabilities: ["trading", "analysis"]
- status: "idle"
```

**返回**：
```
✅ 测试窗口已创建

- **窗口ID**: w-test-1735307284123
- **名称**: 今天股市分析
- **角色**: investor
- **状态**: idle

⚠️  这是测试窗口，仅存在于注册表中，无法接收真实消息或执行任务。
```

---

### 2. window_create_batch

批量创建预设场景的测试窗口。

**参数**：
- `scenario` (string, required): 场景类型，可选：
  - `trading` - 交易场景（3个窗口）
  - `research` - 研究场景（3个窗口）
  - `monitoring` - 监控场景（3个窗口）
  - `mixed` - 混合场景（4个窗口）

**预设场景**：

#### trading - 交易场景
- 交易执行窗口 (trader) - 能力: execution, order-management
- 风险控制窗口 (analyst) - 能力: risk-management
- 投资决策窗口 (investor) - 能力: trading, analysis

#### research - 研究场景
- 白酒板块研究 (researcher) - 能力: research, backtesting
- 科技股研究 (researcher) - 能力: research, sector-analysis
- 市场情绪分析 (analyst) - 能力: sentiment-analysis

#### monitoring - 监控场景
- 白酒板块监控 (monitor) - 能力: market-monitoring, alert
- 大盘指数监控 (monitor) - 能力: market-monitoring, alert
- 北向资金监控 (monitor) - 能力: flow-monitoring, alert

#### mixed - 混合场景
- 今天股市分析 (investor) - 能力: trading, analysis
- 贵州茅台研究 (researcher) - 能力: research
- 白酒板块监控 (monitor) - 能力: monitoring, alert
- 订单执行 (trader) - 能力: execution

**示例**：
```
调用 window_create_batch 工具，参数：
- scenario: "mixed"
```

**返回**：
```
✅ 已创建 4 个测试窗口

- **w-test-1735307284123**: 今天股市分析 (investor)
- **w-test-1735307284234**: 贵州茅台研究 (researcher)
- **w-test-1735307284345**: 白酒板块监控 (monitor)
- **w-test-1735307284456**: 订单执行 (trader)
```

---

### 3. window_delete

删除单个测试窗口。

**参数**：
- `window` (string, required): 窗口ID，如 "w-test-1735307284123"

**安全保护**：
- 只能删除测试窗口（通过 window_create 创建的）
- 无法删除真实的 DSH agent 窗口

**示例**：
```
调用 window_delete 工具，参数：
- window: "w-test-1735307284123"
```

**返回**：
```
✅ 窗口已删除
```

---

### 4. window_cleanup

清理所有测试窗口（批量删除）。

**参数**：无

**示例**：
```
调用 window_cleanup 工具
```

**返回**：
```
✅ 已清理 4 个测试窗口

- w-test-1735307284123
- w-test-1735307284234
- w-test-1735307284345
- w-test-1735307284456
```

---

## 典型使用流程

### 1. 创建测试环境

```
调用 window_create_batch 工具，参数：
- scenario: "mixed"
```

### 2. 查看所有窗口

```
调用 office_roster 工具
```

你会看到新创建的测试窗口出现在花名册中。

### 3. 测试窗口通信

虽然测试窗口无法真正响应，但可以验证派单和消息工具的调用逻辑：

```
调用 assign_task 工具，参数：
- window: "w-test-1735307284123"
- task: "测试任务"
```

### 4. 清理测试环境

```
调用 window_cleanup 工具
```

---

## 测试窗口的特性

### ✅ 可以做的

- **在 office_roster 中显示** - 和真实窗口一样出现在花名册中
- **在 window_list 中列出** - 完整的窗口信息
- **完整的元数据** - 名称、角色、能力、状态
- **状态管理** - 可以通过心跳更新状态（虽然没有实际意义）

### ❌ 不能做的

- **无法接收真实消息** - 没有对应的 DSH agent 会话
- **无法执行真实任务** - 无法处理 assign_task 派发的任务
- **无法发送消息** - 没有实际的 inbox/outbox
- **无法调用工具** - 没有工具执行环境

### 💡 用途

1. **演示多窗口协作** - 快速搭建多窗口场景展示协作流程
2. **测试 office_roster** - 验证花名册显示逻辑
3. **验证窗口 API** - 测试 Agent OS Window Registry API
4. **开发调试** - 在开发办公室工具时快速创建测试数据

---

## 与其他工具配合

### office_roster

查看所有窗口（包括测试窗口）：

```
调用 office_roster 工具
```

输出示例：
```
## 办公室花名册（共 5 个窗口，5 个活跃）

### 🟢 w-test-1735307284123
- **名称**: 今天股市分析
- **角色**: investor
- **状态**: idle
- **能力**: trading, analysis

### 🟢 w-dsh-1787823748
- **名称**: PI投资脑
- **角色**: investor
- **状态**: idle
- **能力**: trading, analysis
```

### window_list

列出所有窗口（包括离线的）：

```
调用 window_list 工具
```

### assign_task / window_message

可以尝试向测试窗口派单或发消息，但会失败（因为没有实际的 agent 会话）。这可以用于验证错误处理逻辑。

---

## 技术实现

### 架构

```
window-manager (DSH Plugin)
    ↓
AgentOSClient
    ↓
Agent OS REST API
    ↓
PostgreSQL (Window Registry)
```

### 数据标记

所有测试窗口在 `metadata` 中包含：
```json
{
  "test_window": true,
  "created_by": "window_create_tool",
  "created_at": "2026-08-27T18:00:00Z",
  "scenario": "mixed"  // 仅 batch 创建时有
}
```

通过 `test_window: true` 标记，确保：
- 只有测试窗口能被 `window_delete` 删除
- `window_cleanup` 只清理测试窗口
- 真实 DSH agent 窗口不会被误删

---

## 配置

插件配置在 `~/.dsh/profiles/investment/cordis.patch.yml`：

```yaml
- id: window-manager
  name: '@pi-investment/window-manager'
  config:
    agentOS:
      baseURL: http://localhost:8080
```

---

## 故障排查

### 工具不可用

**症状**: 调用工具时提示"工具不存在"

**原因**: 插件未加载或 DSH 未重启

**解决**:
```bash
# 检查插件是否构建
cd /Users/yunpeng/pi-investment/agent-dh/packages/window-manager
pnpm build

# 重启 DSH
# 在 DSH Web UI 中重新加载页面
```

### 创建窗口失败

**症状**: `window_create` 返回错误

**原因**: Agent OS 未运行

**解决**:
```bash
cd /Users/yunpeng/pi-investment/agent-os
./agent-os.sh status
./agent-os.sh start  # 如果未运行
```

### 无法删除窗口

**症状**: `window_delete` 提示"只能删除测试窗口"

**原因**: 尝试删除真实的 DSH agent 窗口

**解决**: 只能删除通过 `window_create` 创建的测试窗口（`metadata.test_window = true`）

---

## 开发指南

### 添加新场景

编辑 `src/index.ts` 的 `window_create_batch` 工具：

```typescript
const scenarios: Record<string, Array<{name: string, role: string, capabilities: string[]}>> = {
  // ... 现有场景
  
  my_scenario: [
    { name: '自定义窗口1', role: 'custom', capabilities: ['cap1', 'cap2'] },
    { name: '自定义窗口2', role: 'custom', capabilities: ['cap3'] },
  ],
};
```

### 扩展工具

可以在 `registerTools()` 中添加新工具，参考现有工具的实现模式。

---

## 相关文档

- [RFC 010: Window-OS Lifecycle Management](../../docs/rfcs/rfc-010-window-os-lifecycle-management.md)
- [Agent OS Window Registry API](../../agent-os/README.md)
- [Office Tools 使用指南](../lifecycle/README.md#office-tools)

---

## 版本历史

### v0.1.0 (2026-08-27)

- ✅ 初始版本
- ✅ 实现 4 个核心工具
- ✅ 支持 4 种预设场景
- ✅ 集成到 DSH investment profile
