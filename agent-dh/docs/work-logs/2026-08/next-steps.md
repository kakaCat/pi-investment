# 下一步任务清单

**更新时间**: 2026-08-26 01:15  
**当前状态**: 方案一审计修复完成（5/5），已测试并部署

---

## 立即待办（0-2天）

### 1. 监控首次调用（高优先级）
- [ ] 下次 validation_gate 裁决时，检查日志确认零样本门槛生效
- [ ] 下次 experience_distill 调用时，监控 LLM 蒸馏是否成功（或正确回退）
- [ ] 熔断解除后首笔真实交易，端到端验证完整链路

**验证命令**：
```bash
# 检查 validation_gate 裁决记录
curl "http://localhost:8080/api/v1/memory/search?q=verdict&limit=5"

# 检查 experience_distill 生成的建议
grep "subagent.*生成蒸馏" ~/.dsh/profiles/investment/logs/*.log

# 检查真实交易打标
curl "http://localhost:8080/api/v1/memory/search?kind=experience&q=portfolio_trade" | jq '.memories[0].payload.genome_context'
```

---

### 2. 补充单元测试（中优先级）
当前测试覆盖度不足（集成60%，数据验证40%），建议补充：

- [ ] **evolver/searchRewards 过滤逻辑**：
  - 测试用例1：混合数据（portfolio_trade + model_predict），验证只统计前者
  - 测试用例2：无 tool 字段的历史数据，验证不被误过滤
  - 测试用例3：空数据，验证返回 {count: 0, avg: 0}

- [ ] **evolver/judgeCandidates 零样本门槛**：
  - 测试用例1：cand.count=0，验证返回 verdict='extended'
  - 测试用例2：cand.count=1 但 minSamples=3，验证 !force 时 extended
  - 测试用例3：cand.count=5，验证正常比较流程

- [ ] **learning/experience_distill LLM 蒸馏**：
  - 测试用例1：mock subagent 成功返回，验证解析 JSON
  - 测试用例2：mock subagent 失败，验证 fallback 到模板
  - 测试用例3：无高低奖励模式，验证兜底建议

**实现路径**：
```bash
# 创建测试文件
mkdir -p packages/evolver/tests packages/learning/tests
touch packages/evolver/tests/searchRewards.test.ts
touch packages/evolver/tests/judgeCandidates.test.ts
touch packages/learning/tests/experienceDistill.test.ts

# 运行测试
npx vitest run packages/evolver packages/learning
```

---

## 短期待办（3-7天）

### 3. 基建线协同（#5 技术层兜底）
在 quantsys-v2 后端增加打标钩子（与基建线协调）：

- [ ] 在 v2 的 `/api/trade/execute` 增加可选参数：
  - `genome_version`（string, optional）
  - `reason`（string, optional, 含 R-XXX 规则 ID）
  
- [ ] 执行成功后自动调用 Agent OS `/api/v1/memory`：
  ```python
  # 伪代码
  if genome_version or reason:
      memory_client.write({
          'kind': 'experience',
          'content': json.dumps({
              'action': {'tool': 'portfolio_trade', 'args': {...}},
              'outcome': {'success': True, 'result': order_result},
              'reward': calculate_reward(order),  # 需真实 PnL
              'genome_context': {
                  'genome_version': genome_version,
                  'rules_used': extract_rules(reason)
              }
          }),
          'namespace': 'experience'
      })
  ```

- [ ] 测试：基建线直接调 v2 API 下单（带 genome_version/reason），验证 OS memory 有记录

**协调渠道**：公告板发帖 / 飞书通知基建线窗口

---

### 4. Phase 4 元学习（RFC 005 未覆盖部分）
当前完成度 85%（功能）/ 80%（验证），Phase 4 元学习 0%：

- [ ] **P4-1 策略级蒸馏**：从多条规则归纳出高层原则
  - 输入：rule_scoreboard（规则表现统计）
  - 输出：principles 段的新增/修改建议
  - 实现：类似 experience_distill，但输入是规则而非经验

- [ ] **P4-2 跨代比较**：分析 g6/g7/g8... 各代的优劣
  - 输入：各代的胜率/收益/回撤
  - 输出：哪代基因组表现最好、为什么
  - 实现：新增 genome_compare 工具

- [ ] **P4-3 长期记忆压缩**：定期归档老经验，保留精华
  - 触发：经验库 >1000 条
  - 策略：低 importance + 老旧（>90天）→ 归档到冷存储
  - 保留：高 importance / 近期 / 典型案例

**优先级**：中（元学习是锦上添花，不影响当前运作）

---

## 中期待办（1-2周）

### 5. 数据充实与质量提升
- [ ] 等待熔断解除，积累 2-4 周真实交易数据
- [ ] 观察修复后的验证门裁决质量（是否还有零样本转正）
- [ ] 观察 LLM 蒸馏建议质量（是否比模板化更可操作）
- [ ] 统计规则级归因（哪条规则在赚钱/亏钱）

### 6. 文档完善
- [ ] 更新 RFC 005 状态（Phase 1-3 完成度 → 88%）
- [ ] 补充《验证门使用指南》（min_samples 如何设置、裁决标准）
- [ ] 补充《经验蒸馏最佳实践》（何时调用、如何应用建议）

---

## 长期待办（>2周）

### 7. 外部依赖模块（M7/M8）
RFC 005 中标注为"外部依赖"的模块：

- [ ] **M7 信息采集器**（web_search / 新闻爬虫）
  - 目标：从新闻/公告中提取驱动因子
  - 依赖：外部 API / 爬虫服务

- [ ] **M8 社区反馈**（用户评价 → 奖励信号）
  - 目标：用户满意度作为 reward 维度
  - 依赖：UI 界面 + 反馈收集机制

---

## 风险与阻塞项

### 当前无阻塞
所有审计发现已修复，技术债已偿还，可以正常运作。

### 潜在风险
1. **LLM 蒸馏成本**：每次 experience_distill 调 subagent（LLM token 消耗）
   - 缓解：只在有高/低奖励模式时才调 LLM，数据不足时跳过
   - 监控：首次调用后评估成本

2. **基线数据断档**（v2→OS 迁移）
   - 当前已缓解：迁移了 7 条 agent-ts 经验
   - 长期方案：继续积累真实交易经验

---

## 成功标准（2周后复查）

- [ ] 验证门至少完成 1 次零样本延期裁决（#1 生效）
- [ ] experience_distill 至少成功调用 1 次 LLM 生成建议（#3 生效）
- [ ] 真实交易至少 3 笔且全部正确打标（#2/#4/#5 端到端验证）
- [ ] 单元测试覆盖度达到 70%（当前 0%）
- [ ] 无回归 bug 报告

---

**优先级排序**：
1. 🔴 P0：监控首次调用（0-2天）
2. 🟠 P1：补充单元测试（3-7天）
3. 🟡 P2：基建线协同（3-7天）
4. 🟢 P3：元学习/文档/外部依赖（1-2周+）
