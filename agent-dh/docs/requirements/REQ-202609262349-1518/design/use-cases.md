# 使用场景


描述 RTM YAML 追溯基础设施的典型使用场景，使开发者和用户理解如何使用，验收标准：每个场景都有完整的操作步骤和预期结果。


## 场景1：Dive 模式快速读取节点状态（serves: FR-8）

**用户**：Dive 模式（AI Agent）

**操作步骤**：
```typescript
// Dive 每次决策循环
const reader = new RTMReader();
const lifecycleRTM = await reader.read(requirementId, 'lifecycle');
const currentStage = lifecycleRTM.lifecycle.current_stage;

if (currentStage === 'design') {
  const designRTM = await reader.read(requirementId, 'design');
  const coverage = designRTM.coverage.design.rate;
  
  if (coverage === 1.0 && designRTM.confirmed) {
    console.log('设计覆盖度 100%，可以推进到 decomposing');
  } else {
    console.log(`设计覆盖度 ${coverage * 100}%，需要补充设计`);
  }
}
```

**预期结果**：读取耗时 ~2ms，快速判断下一步动作

## 场景2：用户查看完整追溯链（serves: FR-5）

**用户**：前端用户（人类）

**操作步骤**：
1. 打开 StageOverview
2. 点击"追溯 Tab"
3. 后端读取 rtm-design.yml / rtm-decomposing.yml / rtm-accepting.yml
4. 展示完整追溯链：FR-1 → design/arch#1.1 → t-354ea0 → TC-1

**预期结果**：追溯链清晰展示，可点击跳转到对应文档

## 场景3：提交设计时覆盖度门禁检查（serves: FR-7）

**用户**：需求执行窗口（AI Agent）

**操作步骤**：
```typescript
// 提交设计文档
try {
  await reqboard_submit({ kind: 'design', path: '...' });
} catch (err) {
  if (err.name === 'COVERAGE_INSUFFICIENT') {
    console.log('设计覆盖度不足:', err.coverage.uncovered);
    // 补充缺失的 FR 设计
  }
}
```

**预期结果**：覆盖度不足时被拦截，返回缺口清单

## 场景4：数据迁移（serves: FR-9）

**用户**：运维人员

**操作步骤**：
```bash
# 备份现有台账
cp .dsh-data/dsh-reqboard.json .dsh-data/dsh-reqboard.json.bak-manual

# 运行迁移脚本
node scripts/migrate-reqboard-schema-v9.ts

# 重启服务
./scripts/restart-with-build.sh
```

**预期结果**：台账升级到 v9，所有数据完整，服务正常运行


```bash
# 场景1 验证
node -e "
const start = Date.now();
const rtm = await reader.read('REQ-xxx', 'design');
const elapsed = Date.now() - start;
assert(elapsed < 10, '读取时间应 < 10ms');
"

# 场景2 验证（手动）
# 打开 http://127.0.0.1:13080/dashboard#pmboard?req=REQ-xxx
# 点击追溯 Tab，验证显示完整追溯链

# 场景3 验证
node -e "
// 故意缺少 FR-3 的设计
try {
  reqboard_submit({ kind: 'design' });
  assert(false, '应该被门禁拦截');
} catch (err) {
  assert(err.name === 'COVERAGE_INSUFFICIENT');
}
"

# 场景4 验证
node scripts/migrate-reqboard-schema-v9.ts
jq '.schemaVersion' .dsh-data/dsh-reqboard.json
# 预期输出：9
```