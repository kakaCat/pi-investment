# Agent并行工作启动指令

**项目**: pi-investment v2.0 - 领导监督Agent的量化交易系统  
**日期**: 2026-05-22

---

## 🎯 项目背景

我们正在开发一个"领导监督Agent"的量化交易系统：
- **Agent = 员工**（量化分析员）
- **人 = 领导**（投资经理）
- **Web = 项目管理平台**

领导可以：
1. 看到Agent做了什么（工作日志）
2. 自己做分析和交易（双角色）
3. 复现验证Agent的分析（数据快照）
4. 审批Agent的决策（审批流程）
5. 评估Agent的绩效（绩效统计）

---

## 👥 Agent分工

### Agent 1: 后端开发（Python）
**任务**: 实现19个新的后端API命令

### Agent 2: 前端原型设计（HTML）
**任务**: 继续完善HTML原型，增加5个新页面/功能

### Agent 3: 数据库实施（SQL）
**任务**: 创建8张核心表和迁移脚本

### Agent 4: 测试工程师
**任务**: 编写完整的测试用例

### Agent 5: DevOps工程师
**任务**: Docker化和CI/CD配置

---

## 📋 启动指令

### Agent 1: 后端开发

**一句话任务**：
```
实现19个新的后端API命令，支持Agent操作日志、持仓管理、订单管理、决策记录、数据快照、审批流程。
```

**必读文档**：
1. `docs/backend-api-spec.md` - 包含所有API的详细定义（必读）
2. `docs/database-design.md` - 数据库表结构（必读）
3. `docs/task-assignment.md` - 查看"Agent 1"部分

**工作位置**：
- `/Users/mac/Documents/ai/pi-investment/quant/quantsys/cli/`

**实现优先级**：
- **P0（第1周）**: 8个命令
  - agent.log_action (记录Agent操作)
  - agent.get_logs (获取操作日志)
  - agent.get_log_detail (获取日志详情)
  - order.create (创建订单)
  - order.get_pending (获取待审批订单)
  - order.approve (审批订单)
  - portfolio.get_positions (获取持仓)
  - portfolio.update_position (更新持仓)

- **P1（第2周）**: 6个命令
  - agent.record_decision (记录决策)
  - agent.get_performance (获取绩效)
  - order.execute (执行订单)
  - order.get_history (获取历史订单)
  - snapshot.save (保存数据快照)
  - snapshot.get (获取快照)

- **P2（第3周）**: 5个命令
  - agent.compare_decision (对比决策)
  - approval.get_rules (获取审批规则)
  - approval.update_rules (更新审批规则)
  - portfolio.get_position_history (获取持仓历史)
  - account.get_info (获取账户信息)

**技术栈**：
- Python 3.10+
- Flask
- SQLAlchemy
- SQLite (开发) / PostgreSQL (生产)

**开始命令**：
```bash
cd /Users/mac/Documents/ai/pi-investment
# 先阅读 docs/backend-api-spec.md
# 然后从P0的第一个命令开始实现
```

---

### Agent 2: 前端原型设计

**一句话任务**：
```
继续完善HTML原型（quant-web-v2-prototype.html），增加5个新页面/功能，保持相同的技术栈和风格。
```

**必读文档**：
1. `quant-web-v2-prototype.html` - 现有原型（必须先看）
2. `docs/frontend-prototype-task.md` - 详细任务说明（必读）
3. `docs/frontend-design.md` - 设计参考

**工作位置**：
- 基础文件：`/Users/mac/Documents/ai/pi-investment/quant-web-v2-prototype.html`
- 新文件：`/Users/mac/Documents/ai/pi-investment/quant-web-v2-prototype-new.html`

**需要新增**：
1. **Agent工作日志页面** - 显示Agent今天做了什么
2. **工作详情弹窗** - 展示完整的分析过程（7步）
3. **Agent绩效评估页面** - 准确率、收益贡献、常见错误
4. **仪表盘增加"待审批"区域** - 显示待处理事项
5. **股票详情增加"双标签"** - Agent视图 + 我的工作台

**技术栈**：
- HTML + Tailwind CSS + 原生JavaScript（与现有原型相同）

**设计要求**：
- 保持现有原型的颜色方案和布局结构
- 🤖 Agent相关内容用蓝色背景
- ⚠️ 待审批用红色/黄色边框
- ✅ 已完成用绿色标识

**开始命令**：
```bash
cd /Users/mac/Documents/ai/pi-investment
# 1. 在浏览器中打开现有原型，熟悉结构
open quant-web-v2-prototype.html

# 2. 复制为新文件
cp quant-web-v2-prototype.html quant-web-v2-prototype-new.html

# 3. 阅读 docs/frontend-prototype-task.md
# 4. 开始增加新页面
```

---

### Agent 3: 数据库实施

**一句话任务**：
```
创建8张核心表和数据库迁移脚本，支持Agent日志、持仓、订单、决策、快照等数据存储。
```

**必读文档**：
1. `docs/database-design.md` - 数据库设计（必读）
2. `docs/backend-api-spec.md` - API接口（参考）

**工作位置**：
- `/Users/mac/Documents/ai/pi-investment/quant/quantsys/db/migrations/`

**需要创建的表**：
1. `agent_logs` - Agent操作日志
2. `positions` - 当前持仓
3. `position_history` - 持仓历史
4. `orders` - 订单记录
5. `agent_decisions` - Agent决策记录
6. `data_snapshots` - 数据快照
7. `approval_rules` - 审批规则
8. `accounts` - 账户信息

**技术栈**：
- SQLAlchemy ORM
- Alembic (数据库迁移)
- SQLite (开发) / PostgreSQL (生产)

**交付物**：
- [ ] 数据库迁移脚本（支持SQLite和PostgreSQL）
- [ ] 初始化数据脚本（默认账户、默认审批规则）
- [ ] 回滚脚本
- [ ] 数据库文档

**开始命令**：
```bash
cd /Users/mac/Documents/ai/pi-investment/quant/quantsys
# 1. 创建db目录
mkdir -p db/migrations

# 2. 初始化Alembic
alembic init db/migrations

# 3. 阅读 docs/database-design.md
# 4. 创建第一个迁移脚本
```

---

### Agent 4: 测试工程师

**一句话任务**：
```
编写完整的测试用例，覆盖后端API、数据库、前端页面、端到端流程。
```

**必读文档**：
1. `docs/backend-api-spec.md` - 后端API（必读）
2. `docs/frontend-design.md` - 前端设计（必读）
3. `docs/v2-complete-design-summary.md` - 整体架构（必读）

**工作位置**：
- `/Users/mac/Documents/ai/pi-investment/tests/`

**测试范围**：
1. **后端API单元测试** - 19个命令
2. **数据库集成测试** - 8张表
3. **前端组件测试** - 6个核心页面
4. **端到端测试** - 3个核心流程

**核心流程测试**：
- 流程1：Agent提交买入申请 → 领导审批 → 执行订单
- 流程2：领导复现Agent的分析 → 对比结果 → 标记反馈
- 流程3：领导自己分析股票 → 生成订单 → 直接执行

**技术栈**：
- pytest (后端单元测试)
- Vitest + Vue Test Utils (前端测试，后期)
- Playwright (E2E测试)

**交付物**：
- [ ] 测试用例文档
- [ ] 自动化测试脚本
- [ ] 测试报告模板
- [ ] CI集成配置

**开始命令**：
```bash
cd /Users/mac/Documents/ai/pi-investment
# 1. 创建tests目录
mkdir -p tests/{backend,frontend,e2e}

# 2. 安装测试依赖
pip install pytest pytest-cov

# 3. 阅读 docs/backend-api-spec.md
# 4. 编写第一个测试用例
```

---

### Agent 5: DevOps工程师

**一句话任务**：
```
Docker化整个项目，配置CI/CD流程，搭建监控和日志系统。
```

**必读文档**：
1. `docs/v2-complete-design-summary.md` - 整体架构（必读）
2. `docs/backend-api-spec.md` - 后端技术栈（参考）
3. `docs/frontend-design.md` - 前端技术栈（参考）

**工作位置**：
- `/Users/mac/Documents/ai/pi-investment/docker/`
- `/Users/mac/Documents/ai/pi-investment/.github/workflows/`

**任务清单**：
1. **Docker化**
   - 后端Dockerfile
   - 前端Dockerfile（后期）
   - docker-compose.yml（后端 + 数据库 + Nginx）

2. **CI/CD流程**
   - GitHub Actions配置
   - 自动化测试
   - 自动化部署

3. **环境配置**
   - 开发环境（本地）
   - 测试环境（Docker）
   - 生产环境（云服务器）

4. **监控和日志**
   - 应用监控（Prometheus + Grafana）
   - 日志收集（ELK）
   - 告警配置

**技术栈**：
- Docker + Docker Compose
- Nginx
- GitHub Actions
- Prometheus + Grafana

**交付物**：
- [ ] Dockerfile（后端）
- [ ] docker-compose.yml
- [ ] CI/CD配置
- [ ] 部署文档
- [ ] 监控配置

**开始命令**：
```bash
cd /Users/mac/Documents/ai/pi-investment
# 1. 创建docker目录
mkdir -p docker

# 2. 创建后端Dockerfile
touch docker/Dockerfile.backend

# 3. 阅读 docs/v2-complete-design-summary.md
# 4. 编写第一个Dockerfile
```

---

## 📊 依赖关系

```
Agent 3 (数据库) → Agent 1 (后端) → Agent 2 (前端原型)
                                  ↓
                            Agent 4 (测试)
                                  ↓
                            Agent 5 (DevOps)
```

**说明**：
- Agent 3 先完成数据库表结构（1周）
- Agent 1 基于数据库实现API（3周）
- Agent 2 可以独立画原型（1-2周）
- Agent 4 可以先写测试用例文档（2周）
- Agent 5 可以先搭建Docker环境（1周）

**并行工作**：
- Agent 2、3、4、5 可以立即开始
- Agent 1 等Agent 3完成后开始

---

## 🎯 里程碑

### Week 1
- ✅ Agent 3: 数据库表结构完成
- ✅ Agent 2: 前端原型新增页面完成
- ✅ Agent 5: Docker环境搭建完成
- ✅ Agent 4: 测试用例文档完成
- 🔄 Agent 1: 开始实现P0 API

### Week 2
- ✅ Agent 1: P0 API完成（8个命令）
- 🔄 Agent 1: 开始实现P1 API
- ✅ Agent 4: 后端单元测试完成

### Week 3
- ✅ Agent 1: P1 API完成（6个命令）
- 🔄 Agent 1: 开始实现P2 API
- ✅ Agent 4: E2E测试完成

### Week 4
- ✅ Agent 1: P2 API完成（5个命令）
- ✅ Agent 4: 所有测试完成
- ✅ Agent 5: CI/CD完成
- 🎉 集成测试和部署

---

## 📞 沟通机制

### 每日站会
- 时间：每天早上10:00
- 内容：同步进度、问题、阻塞

### 每周评审
- 时间：每周五下午
- 内容：检查交付物、调整计划

### 文档更新
- 及时更新设计文档
- 记录重要决策和变更

---

## 🚀 立即开始

每个Agent现在可以：
1. 阅读对应的文档
2. 执行开始命令
3. 开始独立工作

**祝各位工作顺利！** 🎉
