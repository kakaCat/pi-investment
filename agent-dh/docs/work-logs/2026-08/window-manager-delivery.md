# Window Manager Plugin 交付文档

## 交付时间
2026-08-27 19:00

## 需求来源
用户提出："你做一个可以操作窗口的工具"

---

## 📦 交付内容

### 1. 新插件：@pi-investment/window-manager

**位置**: `/Users/yunpeng/pi-investment/agent-dh/packages/window-manager/`

**文件**:
- `package.json` - 插件配置
- `src/index.ts` - 插件源码（342行）
- `dist/` - 构建产物
- `README.md` - 使用文档

**构建状态**: ✅ 已构建成功

---

## 🎯 功能清单

### 实现的 4 个工具

| 工具 | 功能 | 状态 |
|------|------|------|
| **window_create** | 创建单个测试窗口 | ✅ 已实现 |
| **window_create_batch** | 批量创建场景（4种预设） | ✅ 已实现 |
| **window_delete** | 删除单个测试窗口 | ✅ 已实现 |
| **window_cleanup** | 清理所有测试窗口 | ✅ 已实现 |

---

## 📋 预设场景

### 1. trading - 交易场景（3个窗口）
- 交易执行窗口 (trader)
- 风险控制窗口 (analyst)
- 投资决策窗口 (investor)

### 2. research - 研究场景（3个窗口）
- 白酒板块研究 (researcher)
- 科技股研究 (researcher)
- 市场情绪分析 (analyst)

### 3. monitoring - 监控场景（3个窗口）
- 白酒板块监控 (monitor)
- 大盘指数监控 (monitor)
- 北向资金监控 (monitor)

### 4. mixed - 混合场景（4个窗口）
- 今天股市分析 (investor)
- 贵州茅台研究 (researcher)
- 白酒板块监控 (monitor)
- 订单执行 (trader)

---

## 🔧 配置集成

### 已添加到 DSH 配置

**文件**: `~/.dsh/profiles/investment/cordis.patch.yml`

**配置**:
```yaml
- id: window-manager
  name: '@pi-investment/window-manager'
  config:
    agentOS:
      baseURL: http://localhost:8080
```

**位置**: 第 146-150 行（notification 插件之后）

---

## ✅ 测试验证

### 构建测试
```bash
cd packages/window-manager
pnpm install  # ✅ 依赖安装成功
pnpm build    # ✅ 构建成功
```

### 功能测试（待在 DSH 中验证）

需要重启 DSH 后在 http://localhost:13080 验证：

1. **创建单个窗口**:
   ```
   调用 window_create 工具，参数：
   - name: "测试窗口"
   - role: "investor"
   ```

2. **批量创建场景**:
   ```
   调用 window_create_batch 工具，参数：
   - scenario: "mixed"
   ```

3. **查看花名册**:
   ```
   调用 office_roster 工具
   ```
   应该能看到新创建的测试窗口

4. **清理窗口**:
   ```
   调用 window_cleanup 工具
   ```

---

## 🎨 设计特性

### 安全保护
- ✅ 测试窗口标记 `test_window: true`
- ✅ 只能删除测试窗口，不能删除真实窗口
- ✅ `window_delete` 验证 metadata 防止误删

### 用户友好
- ✅ 清晰的错误提示
- ✅ Markdown 格式化输出
- ✅ 预设场景快速创建
- ✅ 一键清理所有测试窗口

### 技术实现
- ✅ 基于 Agent OS REST API
- ✅ 使用 AgentOSClient
- ✅ 符合 DSH 插件规范
- ✅ TypeScript 类型安全

---

## 📊 与现有功能集成

### 配合使用的工具

| 工具 | 来源 | 用途 |
|------|------|------|
| office_roster | lifecycle | 查看所有窗口（含测试窗口） |
| window_list | lifecycle | 列出所有窗口 |
| window_update | lifecycle | 更新窗口状态 |
| assign_task | lifecycle | 派发任务（测试窗口会失败） |
| window_message | lifecycle | 窗口通信（测试窗口会失败） |

---

## ⚠️ 测试窗口限制

### ✅ 可以做的
- 在 office_roster 中显示
- 在 window_list 中列出
- 有完整的元数据
- 可以更新状态（通过 API）

### ❌ 不能做的
- 无法接收真实消息
- 无法执行真实任务
- 无法调用工具
- 没有对应的 DSH agent 会话

### 💡 用途
- 演示多窗口协作
- 测试 office_roster
- 验证窗口 API
- 快速搭建测试场景

---

## 📚 文档

### 已创建文档

1. **README.md** - 完整使用文档
   - 工具列表和参数
   - 使用示例
   - 预设场景说明
   - 故障排查
   - 开发指南

2. **使用指南脚本** - `/tmp/window-manager-guide.sh`
   - 快速参考
   - 典型流程
   - 注意事项

3. **本交付文档** - 交付清单和验收指南

---

## 🚀 下一步

### 用户验收

1. **重启 DSH**（让插件生效）
2. **打开** http://localhost:13080
3. **测试工具**:
   ```
   调用 window_create_batch 工具，参数：
   - scenario: "mixed"
   
   调用 office_roster 工具
   
   调用 window_cleanup 工具
   ```

### 可选扩展

如果需要，可以添加：
- 更多预设场景
- 窗口状态批量更新
- 窗口筛选和搜索
- 窗口模板自定义

---

## 🎉 总结

### 交付物

- ✅ 1 个新插件（window-manager）
- ✅ 4 个管理工具
- ✅ 4 种预设场景
- ✅ 完整文档
- ✅ 集成到 DSH 配置

### 代码规模

- **源码**: 342 行 TypeScript
- **文档**: 400+ 行 Markdown
- **测试脚本**: 2 个

### 生产就绪度

- **构建**: ✅ 成功
- **集成**: ✅ 已配置
- **文档**: ✅ 完整
- **测试**: ⏳ 待在 DSH 中验证

---

**交付人**: Claude Code Agent (ccvibe-4-8)

**交付日期**: 2026-08-27

**状态**: ✅ 开发完成，待用户验收
