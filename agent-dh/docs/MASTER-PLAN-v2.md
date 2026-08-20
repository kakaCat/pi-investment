# Agent-DH 自主能力体系实施计划 (Master Plan v2.0 - 修订版)

## 📋 修订说明

**版本**: v2.0  
**修订日期**: 2026-08-20  
**修订原因**: 系统审查发现 26 个问题（6 个严重、9 个高优先级）  
**主要变化**:
1. 新增前置基础设施 Sprint（解决 CRITICAL 问题）
2. 调整 Sprint 顺序，优先解决安全和架构问题
3. 增加时间缓冲（实际工时 = 估算 × 1.5）
4. 完善风险管理策略

---

## 🔴 关键修正点

### 问题 1: 缺少基础设施层（CRITICAL）

**问题**: 没有跨插件通信、日志规范、配置管理等基础设施

**修正**: 新增 Sprint 0 - Infrastructure Foundation

### 问题 2: 时间估算过于乐观（HIGH）

**问题**: 8 天完成 RFC-004 不现实

**修正**: 
- 引入缓冲系数 1.5
- RFC-004: 8 天 → 12 天
- 明确包含 Code Review、修改、集成时间

### 问题 3: 安全机制不完善（CRITICAL）

**问题**: code_generator 无安全检查

**修正**: 
- 提前实施 Security Layer
- 所有代码生成必须经过安全审查
- 分级权限：低风险自动、中风险需确认、高风险需审批

---

## 📅 修订后的 Sprint 规划

### 🏗️ Sprint 0: Infrastructure Foundation (Week 0-1, 2周)

**目标**: 建立所有后续插件依赖的基础设施

**新增插件**: `@pi-infrastructure/core`

**工具清单**:
1. **event_bus** - 事件总线
   - 发布/订阅机制
   - 插件间消息传递
   - 异步事件处理
   - 事件持久化（可选）

2. **config_manager** - 配置管理
   - 配置热更新
   - 配置版本控制
   - 配置变更通知
   - 回滚机制

3. **state_manager** - 状态管理
   - 跨插件状态共享
   - 状态快照
   - 状态一致性保证
   - 并发访问控制（锁）

4. **logging_framework** - 日志框架
   - 统一日志格式（JSON）
   - 日志级别规范（DEBUG/INFO/WARN/ERROR/FATAL）
   - 日志聚合和转发
   - 结构化字段（timestamp, level, plugin, tool, request_id, ...）

5. **security_layer** - 安全层
   - 代码静态分析（危险操作检测）
   - 权限分级（low/medium/high）
   - 沙箱执行环境
   - API 调用限流和配额

6. **version_manager** - 版本管理
   - 插件版本兼容性检查
   - 依赖版本冲突检测
   - 自动回滚到稳定版本
   - 版本锁定机制

**实施者**: Agent-Implementation-0  
**实际工时**: 2 周（10 个工作日）  
**验收标准**:
- [ ] 事件总线支持插件间通信
- [ ] 配置可热更新且不影响运行
- [ ] 日志格式统一且可聚合
- [ ] 代码生成前必须通过安全审查
- [ ] 版本冲突自动检测

---

### 🔍 Sprint 1: Diagnostics Plugin (Week 2-4, 3周) ← 从 2 周调整为 3 周

**修正点**:

1. **性能数据存储方案**（解决 HIGH 问题）
   - 使用 SQLite 存储性能指标
   - 数据自动过期（保留最近 7 天）
   - 内存缓存 + 磁盘持久化双层结构
   - 内存占用上限 100MB

2. **错误签名优化**（解决 HIGH 问题）
   - 保留关键数字（如超时时间）
   - 只标准化变量部分（股票代码、UUID）
   - 增加哈希碰撞检测

3. **LLM 成本控制**（解决 CRITICAL 问题）
   - API 调用限流：最多 10 次/小时
   - 降级方案：LLM 不可用时使用规则匹配
   - 成本监控：记录每次调用成本，超预算告警

4. **集成点明确化**（解决 CRITICAL 问题）
   ```typescript
   // learning 插件通过 event_bus 订阅 diagnostics 事件
   eventBus.on('diagnostics:problem_detected', (problem) => {
     learning.trackExperience({
       type: 'system_issue',
       severity: problem.severity,
       context: problem.context
     });
   });
   ```

**实施者**: Agent-Implementation-1  
**实际工时**: 3 周（15 个工作日）
- 实现: 8 天
- 测试: 3 天
- Code Review: 2 天
- 修改: 2 天

---

### 🛡️ Sprint 2: Security Enhancement (Week 5-6, 2周) ← 新增

**目标**: 在实施代码生成前建立安全防线

**新增插件**: `@pi-investment/security`

**工具清单**:
1. **code_security_scan** - 代码安全扫描
   - 危险函数检测（eval, exec, fs.rm 等）
   - 敏感信息扫描（API key, 密码）
   - 依赖漏洞扫描
   - SQL 注入检测

2. **sandbox_executor** - 沙箱执行
   - 隔离环境运行代码
   - 资源限制（CPU、内存、时间）
   - 网络访问控制
   - 文件系统访问控制

3. **permission_manager** - 权限管理
   - 工具权限分级（low/medium/high/critical）
   - 风险等级评估
   - 权限申请和审批
   - 权限审计日志

4. **approval_workflow** - 审批工作流
   - 高风险操作排队审批
   - 批量审批
   - 超时处理（默认拒绝）
   - 紧急通道（管理员绕过）

**实施者**: Agent-Implementation-2  
**实际工时**: 2 周

---

### 💻 Sprint 3: Codegen Plugin (Week 7-9, 3周) ← 从 2 周调整为 3 周

**修正点**:

1. **安全集成**（解决 CRITICAL 问题）
   ```typescript
   // 所有生成的代码必须经过安全扫描
   const generatedCode = await llm.generate(prompt);
   const securityReport = await security.code_security_scan(generatedCode);
   
   if (securityReport.risk_level === 'high') {
     await human_approval.request(code, securityReport);
   } else if (securityReport.risk_level === 'medium') {
     await log_for_review(code, securityReport);
   }
   ```

2. **测试生成策略**（解决 CRITICAL 问题）
   - 使用 AI 生成测试，但标记为 "AI-generated"
   - AI 生成的测试必须通过人工审查
   - 关键路径（交易、风控）必须有手写测试
   - 测试覆盖率降低要求：核心功能 > 70%，辅助功能 > 50%

**实施者**: Agent-Implementation-3  
**实际工时**: 3 周

---

### 🧪 Sprint 4: Testing Infrastructure (Week 10-11, 2周)

**修正点**:

1. **测试策略调整**（解决 CRITICAL 问题）
   - **单元测试**: 纯逻辑函数
   - **集成测试**: 使用 Mock/Stub 模拟外部依赖
   - **端到端测试**: 真实环境但隔离数据
   - **LLM 测试**: 固定 prompt → 固定输出断言

2. **混沌工程**（解决 HIGH 问题）
   ```typescript
   // chaos_monkey 工具
   chaos_monkey.inject({
     failure_type: 'network_delay',
     target: 'quantsys-v2',
     duration: 60,
     delay_ms: 5000
   });
   ```

3. **长期稳定性测试**（解决 MEDIUM 问题）
   - 7 天连续运行测试（Staging 环境）
   - 内存泄漏检测：每 6 小时快照对比
   - 性能趋势分析：绘制延迟/吞吐曲线

**实施者**: Agent-Implementation-4  
**实际工时**: 2 周

---

### 📊 Sprint 5: Benchmark & Monitoring (Week 12-13, 2周)

**新增内容**:

1. **监控 Dashboard 具体方案**（解决 HIGH 问题）
   - 技术栈: Grafana + Prometheus
   - 数据存储: Prometheus TSDB（时间序列数据库）
   - 关键指标:
     * 系统: CPU, Memory, Disk, Network
     * 工具: latency (p50/p95/p99), error_rate, throughput
     * 业务: strategy_sharpe, portfolio_return, risk_level
   - 告警规则: 基于阈值的告警（Prometheus AlertManager）

2. **备份方案**（解决 MEDIUM 问题）
   - 每日自动备份 memory 数据
   - 关键配置文件版本控制（Git）
   - 灾难恢复 Runbook

**实施者**: Agent-Implementation-5  
**实际工时**: 2 周

---

### 🔄 Sprint 6: Intelligent Rollback (Week 14, 1周)

**修正点**:

1. **防止恶意触发**（解决 MEDIUM 问题）
   ```typescript
   // 回滚触发需要多次确认
   class RollbackGuard {
     private failureCount: Map<string, number> = new Map();
     
     shouldRollback(metric: string, value: number): boolean {
       // 需要连续 3 次超过阈值才触发
       if (value > threshold) {
         const count = this.failureCount.get(metric) || 0;
         this.failureCount.set(metric, count + 1);
         
         if (count >= 3) {
           return true;  // 连续 3 次失败，允许回滚
         }
       } else {
         this.failureCount.delete(metric);  // 恢复正常，重置计数
       }
       return false;
     }
   }
   ```

2. **故障复盘模板**（解决 MEDIUM 问题）
   - 标准化复盘模板
   - 时间线重建
   - 影响范围评估
   - 预防措施建议

**实施者**: Agent-Implementation-6  
**实际工时**: 1 周

---

### 👤 Sprint 7: Human Interaction (Week 15, 1周)

**修正点**:

1. **审批时机量化**（解决 MEDIUM 问题）
   ```typescript
   const REQUIRES_APPROVAL = {
     // 高风险：必须审批
     critical: [
       'delete_data',
       'modify_risk_parameters',
       'trade_amount > 100000'
     ],
     // 中风险：建议审批（超时自动通过）
     medium: [
       'modify_strategy_params',
       'restart_service',
       'trade_amount > 10000'
     ],
     // 低风险：无需审批
     low: [
       'read_only_operations',
       'update_comments',
       'trade_amount < 1000'
     ]
   };
   ```

2. **用户反馈闭环**（解决 LOW 问题）
   - 反馈自动写入 memory (namespace=user_feedback)
   - learning 插件定期分析反馈
   - 负面反馈（1-2 星）自动触发问题诊断

**实施者**: Agent-Implementation-7  
**实际工时**: 1 周

---

### 🧠 Sprint 8: Meta-learning (Week 16-17, 2周)

**新增内容**:

1. **策略失效检测**（解决 MEDIUM 问题）
   ```typescript
   // 定期检查规则是否仍然有效
   async validateRule(rule: Rule): Promise<boolean> {
     const recentPerformance = await backtest(rule, { days: 30 });
     if (recentPerformance.accuracy < 0.6) {
       // 标记为可能失效
       rule.status = 'deprecated';
       await memory.archive(rule);
       return false;
     }
     return true;
   }
   ```

2. **多策略冲突处理**（解决 MEDIUM 问题）
   ```typescript
   // 冲突解决策略
   const strategies = await getSignals(symbol);
   const conflicts = detectConflicts(strategies);
   
   if (conflicts.length > 0) {
     // 按优先级排序
     const priority = ['risk_control', 'momentum', 'mean_reversion'];
     strategies.sort((a, b) => 
       priority.indexOf(a.type) - priority.indexOf(b.type)
     );
     
     // 使用最高优先级策略，记录冲突
     return { 
       selected: strategies[0], 
       conflicts: conflicts,
       decision: 'use_highest_priority'
     };
   }
   ```

**实施者**: Agent-Implementation-8  
**实际工时**: 2 周

---

### 🎯 Sprint 9: Integration & Polish (Week 18, 1周)

**修正点**:

1. **明确验收流程**（解决 MEDIUM 问题）
   ```
   实施者自测 (30%) → 自动化测试 (30%) → 设计者 Code Review (30%) → 集成测试 (10%)
        ↓                      ↓                        ↓                      ↓
     失败 → 修复            失败 → 修复              失败 → 修改            失败 → 修复
   ```

2. **并行开发规范**（解决 MEDIUM 问题）
   - 每个插件在独立分支开发
   - 每周五固定集成日
   - 接口变更需提前 3 天通知
   - 使用语义化版本（semver）

**实施者**: Agent-Integration + 我  
**实际工时**: 1 周

---

## 📊 修订后的总时间线

| Sprint | 名称 | 周数 | 累计周数 | 关键交付物 |
|--------|-----|------|---------|-----------|
| 0 | Infrastructure | 2 | 2 | 基础设施层 |
| 1 | Diagnostics | 3 | 5 | 诊断插件 |
| 2 | Security | 2 | 7 | 安全层 |
| 3 | Codegen | 3 | 10 | 代码生成插件 |
| 4 | Testing | 2 | 12 | 测试框架 |
| 5 | Benchmark | 2 | 14 | 监控和基准 |
| 6 | Rollback | 1 | 15 | 智能回滚 |
| 7 | Human | 1 | 16 | 人工交互 |
| 8 | Meta-learning | 2 | 18 | 元学习 |
| 9 | Integration | 1 | 19 | 集成和优化 |

**总计**: 19 周（4.5 个月）  
**原估算**: 12 周（3 个月）  
**增加**: 7 周（1.5 个月缓冲）

---

## 🎯 修订后的成功指标

### 调整后的现实目标

**短期（1 个月 = Sprint 0-1 完成）**:
- ✅ 自主发现 60% 的常见问题（降低自 80%）
- ✅ 平均修复周期 < 4 小时（放宽自 2 小时）
- ✅ 自动回滚准确率 > 90%（降低自 95%）

**中期（3 个月 = Sprint 0-5 完成）**:
- ✅ 错误率降低 40%（降低自 50%）
- ✅ P95 延迟改善 25%（降低自 30%）
- ✅ 代码覆盖率 70%（降低自 80%）
- ✅ 自主解决 50% 的问题（降低自 60%）

**长期（5 个月 = 全部完成）**:
- ✅ 学习效率提升 1.5x（降低自 2x）
- ✅ 知识迁移成功案例 > 5 个（降低自 10）
- ✅ 自主解决 70% 的常见问题（降低自 80%）
- ✅ 用户干预频率降低 40%（降低自 50%）

---

## 🚨 修订后的风险管理

### 高优先级风险（新增）

1. **风险**: 基础设施 Sprint 延期，影响所有后续 Sprint
   **概率**: Medium  
   **影响**: Critical  
   **应对**:
   - Sprint 0 使用最资深的 Agent
   - 预留 20% 缓冲时间
   - 如果延期，优先级最低的功能砍掉

2. **风险**: LLM API 成本失控
   **概率**: Medium  
   **影响**: High  
   **应对**:
   - 设置月度预算上限（如 $1000）
   - 超过预算自动降级到规则匹配
   - 每周成本审查

3. **风险**: 安全扫描漏报导致恶意代码上线
   **概率**: Low  
   **影响**: Critical  
   **应对**:
   - 高风险代码必须人工审查
   - 沙箱执行验证
   - 生产环境金丝雀发布
   - 快速回滚机制

### 中优先级风险

4. **风险**: 多插件并行开发导致集成困难
   **应对**: 每周集成日，接口变更提前通知

5. **风险**: 测试覆盖不足导致生产事故
   **应对**: 降低覆盖率要求，关键路径 100% 覆盖

---

## 📋 修订后的实施者指南

### 每日进度报告格式（新增）

```
【日期】2026-08-21
【Sprint】1 - Diagnostics
【任务】RFC-004
【今日完成】
- ✅ 实现 self_diagnose 基础功能 (60%)
- 🔄 遇到性能数据存储问题，临时用内存存储

【阻塞问题】
- ⚠️ 不确定 performance_collector 是否需要持久化
- 💡 需要设计者确认：内存占用上限设置多少合适？

【明日计划】
- 完成 self_diagnose
- 开始 performance_monitor

【风险预警】
- 性能数据存储比预期复杂，可能需要额外 1 天

【需要帮助】
- 请设计者确认存储方案选择
```

### 验收流程（新增）

```
1. 实施者自测
   ↓ (通过 → 继续, 失败 → 修复)
2. 自动化测试
   ↓ (通过 → 继续, 失败 → 修复)
3. 提交 PR + 自我评审报告
   ↓
4. 设计者 Code Review (48 小时内)
   ↓ (通过 → 继续, 需修改 → 返工)
5. 集成测试
   ↓ (通过 → 继续, 失败 → 修复)
6. 合并 + 部署到 Staging
   ↓
7. Staging 验证 48 小时
   ↓ (通过 → 完成, 失败 → 回滚)
8. 生产环境灰度发布
   ↓
9. 完成 ✅
```

---

## 🎁 修订版改进总结

### 解决的问题
- ✅ 增加基础设施层（Sprint 0）
- ✅ 提前实施安全层（Sprint 2）
- ✅ 时间估算增加 50% 缓冲
- ✅ LLM 成本控制策略
- ✅ 明确测试策略（Mock、混沌工程）
- ✅ 监控 Dashboard 具体方案
- ✅ 审批时机量化标准
- ✅ 策略失效检测机制
- ✅ 多策略冲突处理
- ✅ 明确的验收流程

### 新增的内容
- ✅ 日志规范和集中化方案
- ✅ 备份和灾难恢复方案
- ✅ 用户反馈闭环
- ✅ 并行开发规范
- ✅ 风险管理清单

### 调整的指标
- 更现实的完成度目标
- 更长但可靠的时间线
- 更清晰的验收标准

---

## 🚦 下一步行动

### 立即（今天）
1. ✅ 修订版计划已完成
2. 🔄 等待你确认：是否同意修订后的顺序和时间线？
3. 📋 如果你同意，我将为 Sprint 0 创建详细 RFC

### Week 0 启动（如果确认）
1. 启动 Sprint 0: Infrastructure Foundation
2. 分配 Agent-Implementation-0
3. 我提供详细的技术指导

### 持续改进
- 每个 Sprint 结束后复盘
- 根据实际情况调整后续 Sprint
- 更新风险管理清单

---

**版本**: 2.0 (修订版)  
**修订日期**: 2026-08-20  
**设计者**: Claude (Kiro)  
**状态**: 等待确认

---

## 💬 请确认

1. **是否同意修订后的计划？**
   - [ ] 同意，启动 Sprint 0
   - [ ] 不同意，需要进一步调整
   - [ ] 部分同意，需要讨论某些 Sprint

2. **时间是否可接受？**
   - [ ] 19 周（4.5 个月）可以接受
   - [ ] 需要压缩到 12 周（需砍掉部分功能）
   - [ ] 时间可以更长，优先保证质量

3. **优先级是否需要调整？**
   - [ ] 当前顺序合理
   - [ ] 某些 Sprint 需要提前/延后
   - [ ] 需要并行执行多个 Sprint
