# CLAUDE.md 更新总结

## 更新日期
2026-06-25

## 更新内容

本次更新为 PI Investment 项目的各个 CLAUDE.md 文件添加了系统核心理念和架构说明。

## 核心理念

### 1. 三层架构
```
Human User (观察者 + 偶尔干预)
    ↓ 配置          ↑ 监控
agent-ts (智能员工) ← web-frontend (监控面板)
    ↓ API调用       ↑ 数据查询
quantsys-v2 (后端服务系统)
```

### 2. Agent 自主性
- **不是被动响应**：Agent 通过定时任务自主工作
- **主动监控**：监控市场并响应机会
- **自主决策**：基于数据分析做出投资决策
- **持续学习**：从结果中学习并改进

### 3. 核心目标：盈利
- **唯一目标**：账户持续盈利
- **竞争环境**：零和博弈，战胜对手（散户、游资、机构、其他AI）
- **智能体现**：在复杂金融博弈中持续盈利

### 4. 股票池的博弈价值
股票池不是"选好股票"，而是**战场选择**：
- 识别最容易赚钱的战场
- 避开对手强的战场
- 在对手犯错时出击
- 战局不利时快速撤退

## 更新的文件

### 1. `/CLAUDE.md` (根目录 - 新建)
**内容**：
- 整体系统概述
- 三层架构说明
- 系统哲学（智能 = 博弈中的盈利能力）
- 股票池博弈理论优化方向
- 开发指导原则

**关键章节**：
- System Intelligence Design
- Game Theory in Stock Pools
- Stock Pool Game Theory Optimization

### 2. `/agent-ts/CLAUDE.md` (更新)
**新增内容**：
- Agent 自主性和定时任务系统
- 游戏理论在股票池中的应用
- Agent 决策框架（决策上下文，不仅仅是数据）
- 审计追踪系统（用于学习）
- 主动约定更新（强调自主性和博弈思维）

**关键章节**：
- Agent Autonomy & Scheduled Tasks
- Game Theory in Stock Pools
- Agent Decision Framework

### 3. `/quantsys-v2/CLAUDE.md` (更新)
**新增内容**：
- 后端服务在三层架构中的角色
- 设计哲学：智能基础设施（不仅是数据API）
- 数据审计追踪系统
- 博弈理论智能系统（路线图）
- 后端服务开发原则

**关键章节**：
- Design Philosophy: Intelligence Infrastructure
- Data Audit Trail System
- Game Theory Intelligence System (Roadmap)
- Backend Service Principles for Agent Support
- Stock Pool Optimization Roadmap

### 4. `/web-frontend/CLAUDE.md` (新建)
**内容**：
- 前端在三层架构中的角色
- 核心使命：透明性和监督
- 关键功能（Agent 活动仪表板、股票池监控、信号历史等）
- 设计原则（以 Agent 为中心，而非以用户为中心）
- WebSocket 集成指南

**关键章节**：
- Core Mission: Transparency & Oversight
- Design Principles
- Key API Endpoints
- WebSocket Integration

## 核心设计原则总结

### Agent (agent-ts)
1. **自主运行**：基于定时任务和事件触发
2. **博弈思维**：识别对手行为，利用对手错误
3. **决策上下文**：不仅要数据，还要分析和建议
4. **学习追踪**：记录决策和结果用于改进

### Backend (quantsys-v2)
1. **返回洞察**：不仅返回数字，还返回分析
2. **提供决策上下文**：what + why + action + risk
3. **支持博弈智能**：追踪对手行为，识别机会
4. **启用 Agent 学习**：记录操作上下文和结果
5. **主动检测异常**：推送预警，不等 Agent 询问

### Frontend (web-frontend)
1. **以 Agent 为中心**：观察 Agent 的工作，而非用户操作
2. **显示推理**：不仅显示结果，还显示"为什么"
3. **可视化博弈动态**：谁在赢，谁在输，机会在哪
4. **突出异常**：需要人类注意的情况
5. **支持学习可视化**：Agent 如何随时间改进

## 博弈情报系统路线图 (quantsys-v2)

### P0 - 必需的竞争智能 API
1. **对手行为追踪** - `GET /api/market/opponent-behavior`
2. **池子战场评估** - `GET /api/pools/battlefield-assessment`
3. **实时博弈预警** - `WebSocket /ws/game-alerts`
4. **带博弈上下文的风险评估** - `GET /api/pools/{id}/risk-assessment`
5. **操纵检测** - `GET /api/market/manipulation-detect`

### P1 - 增强决策支持
- 池子健康度时间序列
- 归因分析
- 操纵检测

### P2 - 学习系统
- 决策结果追踪
- 知识库积累
- 策略自动优化

## 使用场景示例

### 场景1：每日自动股票池维护
```
⏰ 02:00 AM - 定时任务触发
  ↓
Agent 自主启动：
  1. 调用 pool_manage (列出所有动态池)
  2. 遍历每个池子：
     - 调用 pool_manage (刷新)
     - 检测变化：+3只新增，-2只移除
     - 记录原因："600519 ROE下降至12%，低于15%阈值"
  3. 调用 pool_validate（策略验证）
  4. 写入审计追踪到 quantsys-v2 数据库
  5. 如有重大变化：推送通知（飞书/邮件）
  ↓
用户早上查看 web 仪表板：
  - 看到池子变化和原因
  - 审查 Agent 的决策
  - 仅在需要时干预
```

### 场景2：收割散户恐慌
```
市场情况：大盘暴跌 -4%，散户恐慌性抛售
  ↓
Agent 识别机会：
  1. 调用 /api/market/opponent-behavior
  2. V2 返回：散户恐慌指数 high，机构净流入
  3. Agent 判断："这是捡便宜的机会"
  ↓
创建狙击池：
  - pool_manage (scan_create)
  - 筛选：基本面好 + 超跌放量 + 恐慌性抛售
  - 排除：ST股票、高质押率
  ↓
快速建仓：
  - 选择最超跌的5只股票
  - 总仓位30%（控制风险）
  - 设定止盈：反弹+8%分批卖出
  ↓
等待收割：
  - 散户恐慌抛售 → Agent 低价接盘
  - 恐慌消退 → 散户追涨（接盘）
  - Agent 在+8%卖给追涨散户
  - 结果：3天赚+6%，收割完成✅
```

## 数据库表设计建议

### agent_decisions (Agent 决策日志)
```sql
CREATE TABLE agent_decisions (
  id SERIAL PRIMARY KEY,
  decision_type VARCHAR(50),  -- 'create_pool', 'adjust_filter', 'choose_strategy'
  context JSONB,              -- 决策时的上下文
  parameters JSONB,           -- 决策参数
  reasoning TEXT,             -- Agent 的推理过程
  created_at TIMESTAMP,
  evaluation_status VARCHAR(20), -- 'pending', 'evaluated'
  evaluation_result JSONB,    -- 评估结果
  learned_lesson TEXT,        -- 学到的教训
  confidence_score FLOAT      -- 置信度
);
```

### agent_knowledge (Agent 知识库)
```sql
CREATE TABLE agent_knowledge (
  id SERIAL PRIMARY KEY,
  domain VARCHAR(100),        -- '白酒行业', '医药行业'
  knowledge_type VARCHAR(50), -- 'filter_rule', 'strategy_param'
  content JSONB,              -- 知识内容
  confidence FLOAT,           -- 置信度 0-1
  evidence JSONB,             -- 支撑证据（决策ID列表）
  learned_at TIMESTAMP,
  last_validated TIMESTAMP,
  status VARCHAR(20)          -- 'active', 'deprecated'
);
```

### pool_change_log (池子变更日志)
```sql
CREATE TABLE pool_change_log (
  id SERIAL PRIMARY KEY,
  pool_id INT,
  changed_at TIMESTAMP,
  action VARCHAR(20),         -- 'add', 'remove', 'refresh'
  symbol VARCHAR(20),
  reason TEXT,                -- 变更原因
  triggered_by VARCHAR(50),   -- 'agent_auto' | 'user_manual'
  agent_context JSONB         -- Agent 的决策上下文
);
```

## 下一步行动

### 对于开发者
1. 阅读对应项目的 CLAUDE.md 了解核心理念
2. 开发新功能时遵循设计原则
3. API 设计时返回洞察，不仅是数据
4. 实现博弈情报系统（P0 APIs）

### 对于 Agent (DeepSeek)
1. 理解自己是自主运行的智能员工
2. 使用博弈思维分析市场
3. 记录决策上下文用于学习
4. 主动监控市场机会和风险

### 对于未来 Claude Code
1. 参考 CLAUDE.md 理解系统架构
2. 遵循设计原则开发新功能
3. 优先实现博弈情报系统
4. 增强数据审计追踪能力

## 文件清单

- ✅ `/CLAUDE.md` (新建)
- ✅ `/agent-ts/CLAUDE.md` (更新)
- ✅ `/quantsys-v2/CLAUDE.md` (更新)
- ✅ `/web-frontend/CLAUDE.md` (新建)

## 总结

本次更新将我们讨论的核心理念系统化地写入了各个项目的 CLAUDE.md 文件：

1. **明确了系统定位**：三层自主智能投资系统
2. **阐述了核心目标**：通过博弈智能实现持续盈利
3. **定义了设计原则**：返回洞察、提供上下文、支持学习
4. **规划了发展路线**：博弈情报系统、学习系统、高级智能

这些文档将指导未来的开发工作，确保系统朝着"智能自主盈利"的目标演进。
