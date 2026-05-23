# 任务分配清单

**项目**: pi-investment v2.0  
**日期**: 2026-05-22

---

## Agent 1: 后端开发

**负责人**: [待分配]  
**预计工期**: 3周

### 必读文档
- ✅ `docs/backend-api-spec.md`
- ✅ `docs/database-design.md`
- ✅ `docs/v2-complete-design-summary.md`

### 任务描述
实现19个新的后端API命令，支持Agent操作日志、持仓管理、订单管理等功能。

### 实现优先级
- **P0（第1周）**: agent日志(3) + order管理(3) + portfolio管理(2) + signal管理(2) ⭐ 新增
- **P1（第2周）**: agent决策(2) + order执行(2) + snapshot(2) + signal统计(2) ⭐ 新增
- **P2（第3周）**: 对比(1) + 审批规则(2) + 测试优化

### 技术栈
- Python 3.10+, Flask, SQLAlchemy, SQLite/PostgreSQL

### 代码位置
- `/Users/mac/Documents/ai/pi-investment/quant/quantsys/cli/`

### 交付物
- [ ] 19个API命令实现
- [ ] 单元测试（覆盖率>80%）
- [ ] API文档更新
- [ ] 集成到现有系统

---

## Agent 2: 前端开发

**负责人**: [待分配]  
**预计工期**: 3周  
**基础**: 现有原型 `quant-web-v2-prototype.html`

### 必读文档
- ✅ `quant-web-v2-prototype.html` - **现有原型（必须先看）**
- ✅ `docs/frontend-task-detail.md` - **详细任务说明（必读）**
- ✅ `docs/frontend-design.md` - 新增功能参考
- ✅ `docs/backend-api-spec.md` - API接口

### 任务描述
**不是从零开发，而是改造现有原型！**

现有原型是一个单页HTML（~1800行），包含17个功能页面。
你的任务是：
1. 保留原型的UI设计（很优秀）
2. 改造为Vue 3项目（组件化）
3. 增加"领导监督Agent"的功能（核心改动）
4. 对接后端API（替换静态数据）

### 核心改造点
1. **增加双角色概念** - 每个分析页面增加"Agent视图"和"我的工作台"两个标签
2. **增加Agent工作日志页面** - 显示Agent做了什么
3. **增加待审批功能** - Agent提交申请，领导审批
4. **增加工作详情弹窗** - 展示完整分析过程

### 实现优先级
- **P0（第1周）**: 项目搭建 + 提取原型 + 改造仪表盘/持仓/订单
- **P1（第2周）**: 改造市场研究（双标签）+ 新增Agent日志页 + 工作详情弹窗
- **P2（第3周）**: 新增绩效评估页 + 复现验证 + WebSocket

### 技术栈
- Vue 3 + TypeScript, Vite, Pinia, Element Plus, ECharts
- Tailwind CSS（保持原型风格）

### 项目位置
- 原型：`/Users/mac/Documents/ai/pi-investment/quant-web-v2-prototype.html`
- 新项目：`/Users/mac/Documents/ai/pi-investment/web-frontend/`

### 交付物
- [ ] 17个原型页面转换为Vue组件
- [ ] 3个新增页面（Agent日志、绩效评估、工作详情）
- [ ] 所有页面对接后端API
- [ ] 组件测试
- [ ] 部署配置

---

## Agent 3: 数据库实施

**负责人**: [待分配]  
**预计工期**: 1周

### 必读文档
- ✅ `docs/database-design.md`
- ✅ `docs/backend-api-spec.md`

### 任务描述
创建数据库表结构和初始化脚本。

### 任务清单
- [ ] 创建8张核心表
- [ ] 创建所有索引
- [ ] 数据库迁移脚本（Alembic）
- [ ] 初始化数据脚本
- [ ] 回滚脚本

### 技术栈
- SQLAlchemy, Alembic, SQLite/PostgreSQL

### 输出位置
- `/Users/mac/Documents/ai/pi-investment/quant/quantsys/db/migrations/`

### 交付物
- [ ] 数据库迁移脚本
- [ ] 初始化脚本
- [ ] 数据库文档

---

## Agent 4: 测试工程师

**负责人**: [待分配]  
**预计工期**: 2周

### 必读文档
- ✅ `docs/backend-api-spec.md`
- ✅ `docs/frontend-design.md`
- ✅ `docs/v2-complete-design-summary.md`

### 任务描述
编写完整的测试用例，确保系统质量。

### 测试范围
- [ ] 后端API单元测试（19个命令）
- [ ] 数据库集成测试（8张表）
- [ ] 前端组件测试（6个页面）
- [ ] 端到端测试（3个核心流程）

### 技术栈
- pytest, Vitest, Vue Test Utils, Playwright

### 输出位置
- `/Users/mac/Documents/ai/pi-investment/tests/`

### 交付物
- [ ] 测试用例文档
- [ ] 自动化测试脚本
- [ ] 测试报告模板
- [ ] CI集成配置

---

## Agent 5: DevOps工程师

**负责人**: [待分配]  
**预计工期**: 1周

### 必读文档
- ✅ `docs/v2-complete-design-summary.md`
- ✅ `docs/backend-api-spec.md`
- ✅ `docs/frontend-design.md`

### 任务描述
搭建开发、测试、生产环境，实现CI/CD。

### 任务清单
- [ ] Docker化（后端 + 前端 + 数据库）
- [ ] docker-compose.yml
- [ ] CI/CD流程（GitHub Actions）
- [ ] 环境配置（开发/测试/生产）
- [ ] 监控和日志（Prometheus + Grafana）

### 技术栈
- Docker, Nginx, GitHub Actions, Prometheus, Grafana

### 输出位置
- `/Users/mac/Documents/ai/pi-investment/docker/`
- `/Users/mac/Documents/ai/pi-investment/.github/workflows/`

### 交付物
- [ ] Dockerfile
- [ ] docker-compose.yml
- [ ] CI/CD配置
- [ ] 部署文档
- [ ] 监控配置

---

## 协作流程

### 依赖关系
```
Agent 3 (数据库) → Agent 1 (后端) → Agent 2 (前端)
                                  ↓
                            Agent 4 (测试)
                                  ↓
                            Agent 5 (DevOps)
```

### 里程碑
- **Week 1**: 数据库完成 + 后端P0完成
- **Week 2**: 后端P1完成 + 前端P0完成
- **Week 3**: 后端P2完成 + 前端P1完成 + 测试开始
- **Week 4**: 前端P2完成 + 测试完成 + DevOps完成
- **Week 5**: 集成测试 + 部署上线

### 沟通机制
- 每日站会：同步进度和问题
- 每周评审：检查交付物
- 文档更新：及时更新设计文档

---

## 文档位置

所有设计文档位于：
- `/Users/mac/Documents/ai/pi-investment/docs/`

包含：
1. `backend-api-spec.md` - 后端API规范
2. `database-design.md` - 数据库设计
3. `frontend-design.md` - 前端设计
4. `v2-complete-design-summary.md` - 完整设计总结
5. `v2-prototype-gap-analysis.md` - V2原型对比

---

## 联系方式

- 项目负责人：[待填写]
- 技术负责人：[待填写]
- 紧急联系：[待填写]
