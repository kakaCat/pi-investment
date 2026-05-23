# V2量化系统完整设计总结

**项目**: pi-investment 量化交易系统 v2.0  
**日期**: 2026-05-22  
**设计理念**: 领导监督Agent的量化交易平台

---

## 📋 核心理念

### 角色定位

```
🤖 Agent = 量化分析员（员工）
👔 人 = 投资经理（领导）
💼 Web = 项目管理平台
```

### 设计原则

1. **Agent是工具使用者，不是主角**
   - Agent使用量化工具进行分析
   - Web展示的是量化分析结果，而不是"Agent在做什么"

2. **领导和Agent双角色平等**
   - 领导可以自己分析、下单
   - Agent可以自动分析、提交审批
   - 两者使用完全相同的工具

3. **透明可追溯**
   - Agent的每个操作都有日志
   - 每个决策都可以复现验证
   - 所有审批都有记录

4. **清晰的权限边界**
   - Agent可以：分析、生成信号、提交申请
   - Agent不能：直接下单（需要审批）
   - 领导可以：所有操作 + 审批Agent的申请

---

## 📚 文档清单

### 1. [后端API技术规范](./backend-api-spec.md)
- 19个新增API命令
- 6大功能模块
- 完整的接口定义和示例

### 2. [数据库设计文档](./database-design.md)
- 8张核心数据表
- 完整的索引设计
- 数据关系图和字典

### 3. [前端完整设计](./frontend-design.md)
- 6个核心页面
- 完整的交互流程
- 技术栈和实现方案

### 4. [V2原型对比分析](./v2-prototype-gap-analysis.md)
- V2原型 vs QuantDinger对比
- 功能覆盖率分析
- 实现优先级建议

---

## 🎯 系统架构

### 整体架构

```
┌─────────────────────────────────────────────┐
│              Web前端 (Vue 3)                │
│  - 仪表盘                                   │
│  - 市场研究（领导 + Agent）                 │
│  - 持仓管理                                 │
│  - 工作台（任务管理）                       │
│  - Agent监控                                │
└─────────────────┬───────────────────────────┘
                  │ HTTP/WebSocket
┌─────────────────┴───────────────────────────┐
│           后端API (Python Flask)            │
│  ┌─────────────────────────────────────┐   │
│  │ 现有功能（100+命令）                │   │
│  │ - 市场数据                          │   │
│  │ - 技术分析                          │   │
│  │ - 基本面分析                        │   │
│  │ - 风险管理                          │   │
│  │ - ML预测                            │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │ 新增功能（19个命令）                │   │
│  │ - Agent操作日志                     │   │
│  │ - 持仓管理                          │   │
│  │ - 订单管理                          │   │
│  │ - 审批流程                          │   │
│  │ - 决策记录                          │   │
│  │ - 数据快照                          │   │
│  └─────────────────────────────────────┘   │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────┴───────────────────────────┐
│          数据库 (SQLite/PostgreSQL)         │
│  - agent_logs (操作日志)                    │
│  - positions (持仓)                         │
│  - orders (订单)                            │
│  - agent_decisions (决策记录)               │
│  - data_snapshots (数据快照)                │
│  - approval_rules (审批规则)                │
└─────────────────────────────────────────────┘
```

---

## 🔧 后端新增功能

### 模块1：Agent操作日志系统（3个命令）
- `agent.log_action` - 记录Agent操作
- `agent.get_logs` - 查询操作日志
- `agent.get_log_detail` - 获取操作详情

### 模块2：持仓管理系统（3个命令）
- `portfolio.get_positions` - 获取持仓列表
- `portfolio.update_position` - 更新持仓
- `portfolio.get_position_history` - 持仓历史

### 模块3：订单管理系统（5个命令）
- `order.create` - 创建订单
- `order.get_pending` - 获取待审批订单
- `order.approve` - 审批订单
- `order.execute` - 执行订单
- `order.get_history` - 订单历史

### 模块4：Agent决策与绩效（4个命令）
- `agent.record_decision` - 记录决策
- `agent.update_feedback` - 更新反馈
- `agent.get_performance` - 获取绩效
- `agent.compare_decision` - 对比决策

### 模块5：数据快照系统（2个命令）
- `snapshot.save` - 保存快照
- `snapshot.get` - 获取快照

### 模块6：审批流程配置（2个命令）
- `approval.get_rules` - 获取规则
- `approval.update_rules` - 更新规则

**总计：19个新命令**

---

## 💾 数据库设计

### 核心数据表

1. **agent_logs** - Agent操作日志
   - 记录Agent的每个操作
   - 支持按时间、类型、股票查询

2. **positions** - 持仓管理
   - 当前持仓信息
   - 成本、市值、盈亏、止损止盈

3. **position_history** - 持仓历史
   - 持仓变动记录
   - 买入、卖出、调整记录

4. **orders** - 订单管理
   - 订单创建、审批、执行
   - 支持审批流程

5. **agent_decisions** - Agent决策记录
   - 决策内容和推理过程
   - 用户反馈和实际结果

6. **data_snapshots** - 数据快照
   - 历史数据保存
   - 用于复现分析

7. **approval_rules** - 审批规则
   - 可配置的审批条件
   - 支持优先级

8. **accounts** - 账户管理
   - 多账户支持
   - 资金和持仓汇总

---

## 🎨 前端页面设计

### 页面1：仪表盘
- 项目状态总览
- Agent工作摘要
- 待处理事项（审批、提醒）

### 页面2：市场研究
- **两个标签**：
  - 🤖 Agent视图：查看Agent的分析
  - 👔 我的工作台：自己做分析
- 使用相同的分析工具
- 可以对比结果

### 页面3：持仓管理
- 当前持仓列表
- 盈亏统计
- 止损止盈管理
- 建仓原因和历史

### 页面4：工作台
- 统一的任务管理
- 待审批订单
- 我的任务
- Agent任务

### 页面5：Agent监控
- Agent工作日志
- 操作详情
- 绩效评估
- 决策对比

### 页面6：工作详情（弹窗）
- 完整的分析过程
- 每一步的详细数据
- 一键复现功能
- 审批操作

---

## 🔄 核心工作流程

### 流程1：Agent提交买入申请

```
1. Agent分析股票
   ↓ 调用现有API（技术分析、基本面分析等）
   ↓ 记录操作日志 (agent.log_action)
   ↓ 保存数据快照 (snapshot.save)

2. Agent生成决策
   ↓ 记录决策 (agent.record_decision)

3. Agent创建订单
   ↓ 创建订单 (order.create, status='pending')

4. 前端显示待审批通知
   ↓ 获取待审批订单 (order.get_pending)

5. 领导查看分析详情
   ↓ 获取操作详情 (agent.get_log_detail)

6. 领导批准
   ↓ 审批订单 (order.approve)

7. 系统执行订单
   ↓ 执行订单 (order.execute)
   ↓ 更新持仓 (portfolio.update_position)
```

### 流程2：领导复现Agent的分析

```
1. 领导点击"我来复现"
   ↓ 获取Agent的分析参数 (agent.get_log_detail)
   ↓ 获取当时的数据快照 (snapshot.get)

2. 前端使用相同参数调用分析API
   ↓ 调用现有API（与Agent使用的完全相同）

3. 前端对比结果
   ↓ 对比决策 (agent.compare_decision)

4. 领导标记反馈
   ↓ 更新反馈 (agent.update_feedback)
```

### 流程3：领导自己分析股票

```
1. 领导输入股票代码
   ↓ 获取实时行情

2. 领导选择分析模块
   ↓ 调用现有API（技术分析、基本面分析等）

3. 前端计算综合评分

4. 领导生成交易计划
   ↓ 创建订单 (order.create, submitted_by='user')

5. 直接执行（无需审批）
   ↓ 执行订单 (order.execute)
   ↓ 更新持仓 (portfolio.update_position)
```

---

## 📊 实现优先级

### P0（必须，第一阶段）

**后端**:
1. ✅ Agent操作日志 (`agent.log_action`, `agent.get_logs`)
2. ✅ 订单管理 (`order.create`, `order.get_pending`, `order.approve`)
3. ✅ 持仓管理 (`portfolio.get_positions`, `portfolio.update_position`)

**前端**:
1. ✅ 仪表盘（项目状态 + 待审批）
2. ✅ 工作台（任务管理 + 审批）
3. ✅ 持仓管理（查看持仓）

**数据库**:
1. ✅ `agent_logs`
2. ✅ `orders`
3. ✅ `positions`

### P1（重要，第二阶段）

**后端**:
4. ✅ Agent决策记录 (`agent.record_decision`, `agent.get_performance`)
5. ✅ 订单执行 (`order.execute`, `order.get_history`)
6. ✅ 数据快照 (`snapshot.save`, `snapshot.get`)

**前端**:
4. ✅ 市场研究（双模式：Agent视图 + 我的工作台）
5. ✅ Agent监控（工作日志 + 绩效）
6. ✅ 工作详情页（完整分析过程）

**数据库**:
4. ✅ `agent_decisions`
5. ✅ `position_history`
6. ✅ `data_snapshots`

### P2（可选，第三阶段）

**后端**:
7. ✅ 决策对比 (`agent.compare_decision`)
8. ✅ 审批规则配置 (`approval.get_rules`, `approval.update_rules`)

**前端**:
7. ✅ 复现验证功能
8. ✅ 决策对比页面
9. ✅ 审批规则配置

**数据库**:
7. ✅ `approval_rules`
8. ✅ `accounts`

---

## 🚀 技术栈

### 后端
- **Python 3.10+**
- **Flask** (Web框架)
- **SQLAlchemy** (ORM)
- **SQLite** (开发) / **PostgreSQL** (生产)
- **WebSocket** (实时推送)

### 前端
- **Vue 3** + **TypeScript**
- **Vite** (构建工具)
- **Pinia** (状态管理)
- **Element Plus** (UI组件)
- **ECharts** (图表)
- **TradingView Lightweight Charts** (K线图)

### 部署
- **Docker** + **Docker Compose**
- **Nginx** (反向代理)
- **PM2** (进程管理)

---

## 📈 预期效果

### 对领导（人）
- ✅ 可以看到Agent做了什么
- ✅ 可以复现验证Agent的分析
- ✅ 可以审批Agent的决策
- ✅ 可以自己做分析和交易
- ✅ 可以评估Agent的绩效

### 对Agent
- ✅ 有完整的操作日志
- ✅ 决策可以被追溯
- ✅ 可以从人的反馈中学习
- ✅ 绩效可以被量化评估

### 对系统
- ✅ 透明可追溯
- ✅ 权限边界清晰
- ✅ 支持人机协作
- ✅ 数据完整可靠

---

## 📝 下一步行动

### 后端开发
1. 创建数据库表结构
2. 实现19个新增API命令
3. 编写单元测试
4. 集成到现有系统

### 前端开发
1. 搭建Vue 3项目
2. 实现6个核心页面
3. 对接后端API
4. 实现实时数据推送

### 测试验证
1. 单元测试
2. 集成测试
3. 端到端测试
4. 用户验收测试

### 部署上线
1. 开发环境部署
2. 测试环境验证
3. 生产环境部署
4. 监控和优化

---

## 🎯 成功标准

### 功能完整性
- ✅ 所有19个新API正常工作
- ✅ 6个核心页面功能完整
- ✅ 审批流程顺畅
- ✅ 数据准确可靠

### 性能指标
- ✅ 页面加载时间 < 2秒
- ✅ API响应时间 < 500ms
- ✅ 实时数据延迟 < 1秒
- ✅ 支持100+并发用户

### 用户体验
- ✅ 界面清晰易用
- ✅ 操作流程顺畅
- ✅ 错误提示友好
- ✅ 响应及时准确

---

## 📞 联系方式

如有问题或建议，请联系：
- 项目负责人：[待填写]
- 技术支持：[待填写]
- 文档维护：[待填写]

---

**文档版本**: v1.0  
**最后更新**: 2026-05-22  
**状态**: 设计完成，待开发
