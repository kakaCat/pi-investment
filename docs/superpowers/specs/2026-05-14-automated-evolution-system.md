# Agent 自动化进化系统 - 设计文档

**日期**：2026-05-14  
**版本**：v2.0 (自动化版本)  
**状态**：待审核

---

## 一、功能概述

### 1.1 核心目标

实现完全自动化的 Agent 进化系统，补偿器自动生成代码实现工具，效应器负责分支管理、验证和提交，支持完整的回退机制。

### 1.2 与 v1.0 的区别

**v1.0（半自动）**：
- 补偿器生成建议 → 保存到 JSON → 人工实现代码

**v2.0（全自动）**：
- 补偿器生成建议 → 效应器自动生成代码 → 沙箱验证 → 提交分支 → 用户审核合并

### 1.3 控制论模型（更新）

```
目标值（期望收益）
    ↓
减法器（Comparator）：计算误差 = 目标 - 实际
    ↓
误差信号（目标差距）
    ↓
补偿器（Compensator）：生成优化建议
    ↓
效应器（Effector）：自动生成代码并验证
    ↓
    ├─ 创建 evolution 分支
    ├─ 生成工具代码
    ├─ 沙箱验证（编译 + 测试 + 集成）
    ├─ 提交到分支
    └─ 生成修改计划报告
    ↓
用户审核
    ├─ 批准 → 合并到 main
    └─ 拒绝 → 删除分支（回退）
    ↓
实际输出（盈利结果）
    ↓
反馈回路 ──────────┘
```

---

## 二、核心架构

### 2.1 组件职责划分

#### 减法器（Comparator）
- **职责**：计算目标与实际的差距，归因分析
- **输入**：目标收益、实际收益、市场收益、历史数据
- **输出**：差距信号、归因结果
- **实现**：`src/services/intelligence/comparator.ts`（已存在）

#### 补偿器（Compensator）
- **职责**：根据差距生成优化建议
- **输入**：差距信号、归因结果、工具统计、弱点分析
- **输出**：优化建议列表（add_tool, remove_tool, update_experience）
- **实现**：`src/services/intelligence/compensator.ts`（已存在）

#### 能力执行器（CapabilityExecutor）
- **职责**：执行能力层面的改动（经验库更新）
- **输入**：优化建议
- **输出**：执行结果
- **实现**：`src/services/intelligence/capability-executor.ts`（重命名自 evolution-executor）

#### 效应器（EvolutionEffector）
- **职责**：自动生成代码、验证、提交 git
- **输入**：优化建议
- **输出**：分支名称、提交列表、修改计划报告
- **实现**：`src/services/intelligence/evolution-effector.ts`（新增）

#### 沙箱验证器（SandboxValidator）
- **职责**：验证生成的代码（编译 + 测试 + 集成）
- **输入**：工具代码、工具名称
- **输出**：验证结果（通过/失败 + 错误信息）
- **实现**：`src/services/intelligence/sandbox-validator.ts`（新增）

### 2.2 数据流图

```
/evolution 命令
    ↓
evolution-service.ts
    ├─ 调用 comparator（减法器）
    ├─ 调用 compensator（补偿器）
    ├─ 调用 capability-executor（能力执行器）
    └─ 调用 evolution-effector（效应器）
        ↓
    evolution-effector.ts
        ├─ 创建 evolution/YYYY-MM-DD-xxx 分支
        ├─ 对每个 add_tool 建议：
        │   ├─ 生成工具代码（我作为 Agent）
        │   ├─ 调用 sandbox-validator 验证
        │   ├─ 验证通过 → git commit
        │   └─ 验证失败 → 记录错误，跳过
        ├─ 对每个 remove_tool 建议：
        │   ├─ 从 index.ts 移除工具
        │   ├─ 移动工具文件到 deprecated/
        │   └─ git commit
        └─ 生成修改计划报告
            ↓
    返回给用户
        ├─ 分支名称
        ├─ 提交列表
        ├─ 验证结果
        └─ 询问是否合并
```

---

## 三、效应器详细设计

### 3.1 EvolutionEffector 接口

```typescript
interface EvolutionEffectorResult {
  branchName: string;
  commits: Array<{
    hash: string;
    message: string;
    files: string[];
  }>;
  validationResults: Array<{
    suggestionId: string;
    toolName: string;
    status: 'success' | 'failed';
    error?: string;
  }>;
  modificationPlan: string; // Markdown 格式的修改计划
  needsReview: boolean;
}

export class EvolutionEffector {
  async executeEvolution(
    suggestions: OptimizationSuggestion[],
    piDir: string
  ): Promise<EvolutionEffectorResult>;
}
```

### 3.2 执行流程

#### Step 1: 创建进化分支

```typescript
async createEvolutionBranch(): Promise<string> {
  const timestamp = new Date().toISOString().split('T')[0];
  const branchName = `evolution/${timestamp}-auto-evolution`;
  
  // 确保在 main 分支
  await exec('git checkout main');
  await exec('git pull');
  
  // 创建新分支
  await exec(`git checkout -b ${branchName}`);
  
  return branchName;
}
```

#### Step 2: 处理 add_tool 建议

```typescript
async handleAddTool(suggestion: OptimizationSuggestion): Promise<void> {
  const toolName = suggestion.data.toolName;
  const toolPath = `src/infrastructure/tools/${toolName}-tool.ts`;
  
  // 1. 生成工具代码（我作为 Agent 直接生成）
  const toolCode = await this.generateToolCode(suggestion);
  
  // 2. 写入文件
  await fs.writeFile(toolPath, toolCode, 'utf-8');
  
  // 3. 沙箱验证
  const validationResult = await this.validator.validate(toolName, toolPath);
  
  if (!validationResult.passed) {
    // 验证失败，删除文件，记录错误
    await fs.unlink(toolPath);
    throw new Error(`Tool validation failed: ${validationResult.error}`);
  }
  
  // 4. 注册工具到 index.ts
  await this.registerToolInIndex(toolName);
  
  // 5. 提交
  await exec(`git add ${toolPath} src/infrastructure/tools/index.ts`);
  await exec(`git commit -m "feat(evolution): add ${toolName} tool"`);
}
```

#### Step 3: 处理 remove_tool 建议

```typescript
async handleRemoveTool(suggestion: OptimizationSuggestion): Promise<void> {
  const toolName = suggestion.data.toolName;
  const toolPath = `src/infrastructure/tools/${toolName}-tool.ts`;
  
  // 1. 从 index.ts 移除
  await this.unregisterToolFromIndex(toolName);
  
  // 2. 移动到 deprecated/（保留代码以便回退）
  const deprecatedPath = `src/infrastructure/tools/deprecated/${toolName}-tool.ts`;
  await fs.mkdir('src/infrastructure/tools/deprecated', { recursive: true });
  await fs.rename(toolPath, deprecatedPath);
  
  // 3. 提交
  await exec(`git add ${toolPath} ${deprecatedPath} src/infrastructure/tools/index.ts`);
  await exec(`git commit -m "refactor(evolution): remove ${toolName} tool"`);
}
```

#### Step 4: 生成修改计划报告

```typescript
async generateModificationPlan(
  suggestions: OptimizationSuggestion[],
  results: ValidationResult[]
): Promise<string> {
  return `
# 进化修改计划

## 执行时间
${new Date().toISOString()}

## 分支信息
- 分支名称: ${this.branchName}
- 基于: main
- 提交数量: ${this.commits.length}

## 修改内容

### ✅ 成功应用 (${results.filter(r => r.status === 'success').length})

${results.filter(r => r.status === 'success').map(r => `
#### ${r.toolName}
- 类型: ${r.type}
- 文件: ${r.files.join(', ')}
- 验证: 通过（编译 + 单元测试 + 集成测试）
`).join('\n')}

### ❌ 失败跳过 (${results.filter(r => r.status === 'failed').length})

${results.filter(r => r.status === 'failed').map(r => `
#### ${r.toolName}
- 类型: ${r.type}
- 错误: ${r.error}
- 建议: 需要人工介入
`).join('\n')}

## Git 提交记录

${this.commits.map(c => `
- ${c.hash.slice(0, 7)} ${c.message}
  文件: ${c.files.join(', ')}
`).join('\n')}

## 下一步操作

### 如果批准此次进化：
\`\`\`bash
git checkout main
git merge ${this.branchName}
git push
\`\`\`

### 如果拒绝此次进化：
\`\`\`bash
git checkout main
git branch -D ${this.branchName}
\`\`\`

## 回退方案

如果合并后发现问题，可以回退到合并前的状态：
\`\`\`bash
git log --oneline -10  # 找到合并前的 commit
git reset --hard <commit-hash>
\`\`\`
`;
}
```

---

## 四、沙箱验证器详细设计

### 4.1 SandboxValidator 接口

```typescript
interface ValidationResult {
  passed: boolean;
  error?: string;
  details: {
    compilation: { passed: boolean; error?: string };
    unitTest: { passed: boolean; error?: string };
    integration: { passed: boolean; error?: string };
  };
}

export class SandboxValidator {
  async validate(toolName: string, toolPath: string): Promise<ValidationResult>;
}
```

### 4.2 验证流程

#### Level 1: 编译验证

```typescript
async validateCompilation(toolPath: string): Promise<{ passed: boolean; error?: string }> {
  try {
    // 运行 TypeScript 编译检查
    const { stdout, stderr } = await exec(`npx tsc --noEmit ${toolPath}`);
    
    if (stderr) {
      return { passed: false, error: stderr };
    }
    
    return { passed: true };
  } catch (e) {
    return { passed: false, error: e.message };
  }
}
```

#### Level 2: 单元测试验证

```typescript
async validateUnitTest(toolName: string, toolPath: string): Promise<{ passed: boolean; error?: string }> {
  // 1. 生成单元测试代码
  const testCode = await this.generateUnitTest(toolName, toolPath);
  const testPath = toolPath.replace('.ts', '.test.ts');
  
  // 2. 写入测试文件
  await fs.writeFile(testPath, testCode, 'utf-8');
  
  try {
    // 3. 运行测试
    const { stdout, stderr } = await exec(`npm test -- ${testPath}`);
    
    // 4. 清理测试文件
    await fs.unlink(testPath);
    
    if (stderr && stderr.includes('FAIL')) {
      return { passed: false, error: stderr };
    }
    
    return { passed: true };
  } catch (e) {
    await fs.unlink(testPath);
    return { passed: false, error: e.message };
  }
}
```

#### Level 3: 集成测试验证

```typescript
async validateIntegration(toolName: string): Promise<{ passed: boolean; error?: string }> {
  try {
    // 1. 动态导入工具
    const toolModule = await import(`../../infrastructure/tools/${toolName}-tool.js`);
    const tool = toolModule[`${toCamelCase(toolName)}Tool`];
    
    // 2. 调用工具（使用 mock 参数）
    const result = await tool.execute('test-call-id', {});
    
    // 3. 验证返回格式
    if (!result.content || !Array.isArray(result.content)) {
      return { passed: false, error: 'Invalid return format' };
    }
    
    return { passed: true };
  } catch (e) {
    return { passed: false, error: e.message };
  }
}
```

---

## 五、代码生成策略

### 5.1 我作为 Agent 的代码生成能力

作为 Agent，我可以：
1. 理解优化建议的意图
2. 参考现有工具的代码模式
3. 生成符合项目规范的代码
4. 处理边界情况和错误处理

### 5.2 代码生成输入

```typescript
interface CodeGenerationInput {
  toolName: string;
  description: string;
  reason: string;
  expectedImpact: string;
  dataSource?: string; // 如 "get_sector_fund_flow"
  parameters?: Record<string, any>;
  referenceTools: string[]; // 参考的现有工具
}
```

### 5.3 生成流程

```typescript
async generateToolCode(suggestion: OptimizationSuggestion): Promise<string> {
  // 1. 读取参考工具代码
  const referenceCode = await this.loadReferenceTools([
    'evolution-tool.ts',
    'invest-tools.ts'
  ]);
  
  // 2. 构造生成提示（我自己理解）
  const prompt = `
根据以下需求生成工具代码：

工具名称: ${suggestion.data.toolName}
描述: ${suggestion.description}
原因: ${suggestion.reason}
预期效果: ${suggestion.expectedImpact}

参考现有工具模式：
${referenceCode}

要求：
1. 使用 ToolDefinition 类型
2. 使用 @sinclair/typebox 定义参数
3. 包含完整的错误处理
4. 返回格式：{ content: [{ type: "text", text: string }], details: any }
5. 遵循项目代码风格
`;

  // 3. 我直接生成代码（作为 Agent 的能力）
  const toolCode = await this.generateCode(prompt);
  
  return toolCode;
}
```

---

*（文档第一部分完成，继续下一部分...）*

## 六、回退机制设计

### 6.1 回退场景

#### 场景 1: 验证失败（自动回退）
- 代码生成后验证失败
- 自动删除生成的文件
- 不创建 commit
- 记录失败原因到报告

#### 场景 2: 用户拒绝合并（手动回退）
- 用户审核后拒绝此次进化
- 删除整个 evolution 分支
- 代码完全回退到进化前状态

#### 场景 3: 合并后发现问题（紧急回退）
- 进化已合并到 main，但运行时发现问题
- 使用 git revert 回退合并提交
- 或使用 git reset 回退到合并前

### 6.2 回退操作接口

```typescript
export class EvolutionRollback {
  // 场景 1: 验证失败自动回退
  async rollbackFailedValidation(toolPath: string): Promise<void> {
    await fs.unlink(toolPath);
    console.log(`已回退失败的工具: ${toolPath}`);
  }
  
  // 场景 2: 删除进化分支
  async rollbackEvolutionBranch(branchName: string): Promise<void> {
    await exec('git checkout main');
    await exec(`git branch -D ${branchName}`);
    console.log(`已删除进化分支: ${branchName}`);
  }
  
  // 场景 3: 回退已合并的进化
  async rollbackMergedEvolution(mergeCommitHash: string): Promise<void> {
    // 方案 A: 使用 revert（推荐，保留历史）
    await exec(`git revert -m 1 ${mergeCommitHash}`);
    
    // 方案 B: 使用 reset（危险，重写历史）
    // await exec(`git reset --hard ${mergeCommitHash}^`);
    
    console.log(`已回退合并提交: ${mergeCommitHash}`);
  }
}
```

### 6.3 回退安全检查

```typescript
async safeRollback(branchName: string): Promise<void> {
  // 1. 检查是否有未提交的更改
  const { stdout: status } = await exec('git status --porcelain');
  if (status.trim()) {
    throw new Error('有未提交的更改，请先提交或暂存');
  }
  
  // 2. 检查分支是否存在
  const { stdout: branches } = await exec('git branch --list');
  if (!branches.includes(branchName)) {
    throw new Error(`分支不存在: ${branchName}`);
  }
  
  // 3. 确认当前不在要删除的分支上
  const { stdout: currentBranch } = await exec('git branch --show-current');
  if (currentBranch.trim() === branchName) {
    await exec('git checkout main');
  }
  
  // 4. 执行删除
  await exec(`git branch -D ${branchName}`);
}
```

---

## 七、风险控制

### 7.1 代码生成风险

**风险**：生成的代码可能包含安全漏洞或错误逻辑

**控制措施**：
1. 三级沙箱验证（编译 + 单元测试 + 集成测试）
2. 静态代码分析（检查危险操作）
3. 限制工具权限（不允许文件系统写入、网络请求等）
4. 人工最终审核

```typescript
async checkCodeSafety(code: string): Promise<{ safe: boolean; issues: string[] }> {
  const issues: string[] = [];
  
  // 检查危险操作
  if (code.includes('eval(') || code.includes('Function(')) {
    issues.push('包含 eval 或 Function 调用');
  }
  
  if (code.includes('fs.writeFile') || code.includes('fs.unlink')) {
    issues.push('包含文件系统写入操作');
  }
  
  if (code.includes('exec(') || code.includes('spawn(')) {
    issues.push('包含命令执行操作');
  }
  
  return {
    safe: issues.length === 0,
    issues
  };
}
```

### 7.2 Git 操作风险

**风险**：错误的 git 操作可能导致代码丢失

**控制措施**：
1. 所有进化在独立分支进行
2. 合并前必须人工审核
3. 提供完整的回退方案
4. 定期备份 main 分支

```typescript
async safeGitOperation(operation: () => Promise<void>): Promise<void> {
  // 1. 备份当前状态
  const { stdout: currentBranch } = await exec('git branch --show-current');
  const { stdout: currentCommit } = await exec('git rev-parse HEAD');
  
  try {
    // 2. 执行操作
    await operation();
  } catch (e) {
    // 3. 失败时恢复
    console.error('Git 操作失败，正在恢复...', e);
    await exec(`git checkout ${currentBranch}`);
    await exec(`git reset --hard ${currentCommit}`);
    throw e;
  }
}
```

### 7.3 验证失败风险

**风险**：验证过程可能误判或遗漏问题

**控制措施**：
1. 多级验证（编译 → 单元测试 → 集成测试）
2. 验证失败时保留详细日志
3. 人工审核验证结果
4. 提供手动重新验证机制

```typescript
async validateWithRetry(
  toolName: string,
  toolPath: string,
  maxRetries: number = 2
): Promise<ValidationResult> {
  let lastError: string | undefined;
  
  for (let i = 0; i < maxRetries; i++) {
    const result = await this.validator.validate(toolName, toolPath);
    
    if (result.passed) {
      return result;
    }
    
    lastError = result.error;
    console.log(`验证失败 (${i + 1}/${maxRetries}): ${result.error}`);
    
    // 等待后重试
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  
  return {
    passed: false,
    error: `验证失败 ${maxRetries} 次: ${lastError}`,
    details: {
      compilation: { passed: false },
      unitTest: { passed: false },
      integration: { passed: false }
    }
  };
}
```

### 7.4 过度进化风险

**风险**：频繁自动进化可能导致系统不稳定

**控制措施**：
1. 限制进化频率（每周最多 1 次）
2. 限制单次进化的改动数量（最多 3-5 个工具）
3. 观察期机制（新工具运行 1 周后才能再次进化）
4. 进化效果评估（下次进化前评估上次效果）

```typescript
async checkEvolutionThrottle(): Promise<{ allowed: boolean; reason?: string }> {
  // 1. 检查上次进化时间
  const lastEvolution = await this.getLastEvolutionDate();
  const daysSinceLastEvolution = (Date.now() - lastEvolution.getTime()) / (1000 * 60 * 60 * 24);
  
  if (daysSinceLastEvolution < 7) {
    return {
      allowed: false,
      reason: `距离上次进化仅 ${daysSinceLastEvolution.toFixed(1)} 天，需等待 7 天`
    };
  }
  
  // 2. 检查待审核的进化分支
  const { stdout: branches } = await exec('git branch --list evolution/*');
  if (branches.trim()) {
    return {
      allowed: false,
      reason: '存在未审核的进化分支，请先处理'
    };
  }
  
  return { allowed: true };
}
```

---

## 八、用户交互流程

### 8.1 进化触发

```bash
# 用户执行
npm run dev

# 在 Agent 会话中
/evolution
```

### 8.2 进化执行（自动）

```
🔄 开始自动进化分析...

📊 减法器计算
  目标收益: 10%
  实际收益: 8%
  差距: 2%
  归因: 能力需要优化

💡 补偿器生成建议
  ✅ 新增工具: analyze_sector_rotation
  ✅ 新增工具: check_stop_loss_trigger
  ✅ 移除工具: get_stock_news

🛠️ 效应器执行
  ├─ 创建分支: evolution/2026-05-14-auto-evolution
  ├─ 生成 analyze_sector_rotation 工具代码...
  │   ├─ ✅ 编译验证通过
  │   ├─ ✅ 单元测试通过
  │   ├─ ✅ 集成测试通过
  │   └─ ✅ 已提交: feat(evolution): add analyze_sector_rotation tool
  ├─ 生成 check_stop_loss_trigger 工具代码...
  │   ├─ ✅ 编译验证通过
  │   ├─ ✅ 单元测试通过
  │   ├─ ✅ 集成测试通过
  │   └─ ✅ 已提交: feat(evolution): add check_stop_loss_trigger tool
  └─ 移除 get_stock_news 工具...
      └─ ✅ 已提交: refactor(evolution): remove get_stock_news tool

📝 修改计划已生成: .pi-invest/evolution/modification-plan-2026-05-14.md

✅ 进化完成！请审核修改计划。
```

### 8.3 用户审核

```markdown
# 修改计划报告

## 执行时间
2026-05-14T10:30:00Z

## 分支信息
- 分支名称: evolution/2026-05-14-auto-evolution
- 基于: main
- 提交数量: 3

## 修改内容

### ✅ 成功应用 (3)

#### analyze_sector_rotation
- 类型: add_tool
- 文件: src/infrastructure/tools/analyze-sector-rotation-tool.ts
- 验证: 通过（编译 + 单元测试 + 集成测试）

#### check_stop_loss_trigger
- 类型: add_tool
- 文件: src/infrastructure/tools/check-stop-loss-trigger-tool.ts
- 验证: 通过（编译 + 单元测试 + 集成测试）

#### get_stock_news
- 类型: remove_tool
- 文件: 已移至 deprecated/

## 下一步操作

### 批准此次进化：
```bash
git checkout main
git merge evolution/2026-05-14-auto-evolution
git push
```

### 拒绝此次进化：
```bash
git checkout main
git branch -D evolution/2026-05-14-auto-evolution
```
```

### 8.4 用户决策

**选项 A: 批准**
```bash
git checkout main
git merge evolution/2026-05-14-auto-evolution
git push
```

**选项 B: 拒绝**
```bash
git checkout main
git branch -D evolution/2026-05-14-auto-evolution
```

**选项 C: 部分批准（手动）**
```bash
# 查看具体提交
git log evolution/2026-05-14-auto-evolution

# 只合并部分提交
git cherry-pick <commit-hash>
```

---

## 九、实施计划

### 9.1 开发顺序

1. **Phase 1: 基础设施**
   - 重命名 evolution-executor → capability-executor
   - 创建 EvolutionEffector 骨架
   - 创建 SandboxValidator 骨架

2. **Phase 2: 沙箱验证**
   - 实现编译验证
   - 实现单元测试生成和验证
   - 实现集成测试验证

3. **Phase 3: 代码生成**
   - 实现工具代码生成逻辑
   - 实现工具注册/注销逻辑
   - 实现代码安全检查

4. **Phase 4: Git 操作**
   - 实现分支创建和管理
   - 实现自动提交
   - 实现回退机制

5. **Phase 5: 集成测试**
   - 端到端测试完整流程
   - 测试各种失败场景
   - 测试回退机制

### 9.2 文件清单

**新增文件**：
- `src/services/intelligence/evolution-effector.ts`
- `src/services/intelligence/sandbox-validator.ts`
- `src/services/intelligence/evolution-rollback.ts`

**修改文件**：
- `src/services/intelligence/evolution-executor.ts` → `capability-executor.ts`
- `src/services/intelligence/evolution-service.ts`（集成 effector）

**测试文件**：
- `src/services/intelligence/evolution-effector.test.ts`
- `src/services/intelligence/sandbox-validator.test.ts`

---

## 十、成功指标

### 10.1 自动化指标
- 代码生成成功率 >80%
- 沙箱验证通过率 >90%
- 自动提交成功率 100%

### 10.2 质量指标
- 生成的工具代码无编译错误
- 生成的工具通过集成测试
- 无安全漏洞

### 10.3 效率指标
- 从 /evolution 到生成报告 <5 分钟
- 验证时间 <2 分钟/工具
- 用户审核时间 <10 分钟

---

**文档结束**

---

## 附录 A：补偿器增强 - 进化效果评估

### A.1 问题描述

当前补偿器只根据当前差距生成建议，但缺少对**上次进化效果**的评估。这导致：
- 不知道上次新增的工具是否有效
- 可能重复生成相同的无效建议
- 无法形成"建议 → 应用 → 评估 → 改进"的完整闭环

### A.2 解决方案：进化历史追踪

#### 数据结构

```typescript
interface EvolutionHistory {
  evolutionId: string;
  date: string;
  branchName: string;
  suggestions: OptimizationSuggestion[];
  applied: string[]; // 已应用的建议 ID
  
  // 应用前的基线
  baseline: {
    return: number;
    winRate: number;
    maxDrawdown: number;
    toolStats: ToolEfficiency[];
  };
  
  // 应用后的效果（下次进化时填充）
  outcome?: {
    return: number;
    winRate: number;
    maxDrawdown: number;
    toolStats: ToolEfficiency[];
    improvement: {
      returnDelta: number;
      winRateDelta: number;
      maxDrawdownDelta: number;
    };
  };
  
  // 效果评估
  evaluation?: {
    effective: boolean;
    effectiveTools: string[]; // 有效的工具
    ineffectiveTools: string[]; // 无效的工具
    reasons: string[];
  };
}
```

#### 存储位置

```
.pi-invest/evolution/
├── history/
│   ├── 2026-05-07.json  # 上次进化记录
│   ├── 2026-05-14.json  # 本次进化记录
│   └── 2026-05-21.json  # 下次进化记录
├── evolution-2026-05-07.md
├── evolution-2026-05-14.md
└── modification-plan-2026-05-14.md
```

### A.3 补偿器增强逻辑

#### Step 1: 加载上次进化历史

```typescript
async function loadLastEvolution(): Promise<EvolutionHistory | null> {
  const historyDir = path.join(piDir, 'evolution/history');
  const files = await fs.readdir(historyDir);
  
  if (files.length === 0) return null;
  
  // 获取最近的历史文件
  const lastFile = files.sort().reverse()[0];
  const content = await fs.readFile(path.join(historyDir, lastFile), 'utf-8');
  
  return JSON.parse(content);
}
```

#### Step 2: 评估上次进化效果

```typescript
async function evaluateLastEvolution(
  lastEvolution: EvolutionHistory,
  currentMetrics: PerformanceMetrics
): Promise<EvolutionEvaluation> {
  
  // 1. 计算指标变化
  const improvement = {
    returnDelta: currentMetrics.return - lastEvolution.baseline.return,
    winRateDelta: currentMetrics.winRate - lastEvolution.baseline.winRate,
    maxDrawdownDelta: currentMetrics.maxDrawdown - lastEvolution.baseline.maxDrawdown,
  };
  
  // 2. 判断整体效果
  const effective = 
    improvement.returnDelta > 0 || 
    improvement.winRateDelta > 0.02 || 
    improvement.maxDrawdownDelta > 0;
  
  // 3. 评估每个工具的效果
  const effectiveTools: string[] = [];
  const ineffectiveTools: string[] = [];
  
  for (const suggestionId of lastEvolution.applied) {
    const suggestion = lastEvolution.suggestions.find(s => s.id === suggestionId);
    if (!suggestion || suggestion.type !== 'add_tool') continue;
    
    const toolName = suggestion.data.toolName;
    
    // 查找工具的使用统计
    const toolStat = currentMetrics.toolStats.find(t => t.tool_name === toolName);
    
    if (!toolStat) {
      ineffectiveTools.push(toolName);
      continue;
    }
    
    // 判断工具是否有效
    if (toolStat.win_rate > 0.6 && toolStat.avg_return > 0) {
      effectiveTools.push(toolName);
    } else {
      ineffectiveTools.push(toolName);
    }
  }
  
  // 4. 生成评估原因
  const reasons: string[] = [];
  
  if (improvement.returnDelta > 0) {
    reasons.push(`收益率提升 ${improvement.returnDelta.toFixed(2)}%`);
  } else if (improvement.returnDelta < 0) {
    reasons.push(`收益率下降 ${Math.abs(improvement.returnDelta).toFixed(2)}%`);
  }
  
  if (improvement.winRateDelta > 0.02) {
    reasons.push(`胜率提升 ${(improvement.winRateDelta * 100).toFixed(1)}%`);
  } else if (improvement.winRateDelta < -0.02) {
    reasons.push(`胜率下降 ${Math.abs(improvement.winRateDelta * 100).toFixed(1)}%`);
  }
  
  if (effectiveTools.length > 0) {
    reasons.push(`有效工具: ${effectiveTools.join(', ')}`);
  }
  
  if (ineffectiveTools.length > 0) {
    reasons.push(`无效工具: ${ineffectiveTools.join(', ')}`);
  }
  
  return {
    effective,
    effectiveTools,
    ineffectiveTools,
    reasons,
    improvement,
  };
}
```

#### Step 3: 基于评估结果调整建议

```typescript
function generateOptimizationSuggestionsV2(
  gap: PerformanceGap,
  attribution: AttributionResult,
  toolStats: ToolEfficiency[],
  weaknesses: string[],
  lastEvolutionEval?: EvolutionEvaluation
): OptimizationSuggestion[] {
  
  const suggestions: OptimizationSuggestion[] = [];
  
  // 1. 如果上次进化有无效工具，优先移除
  if (lastEvolutionEval?.ineffectiveTools.length > 0) {
    for (const toolName of lastEvolutionEval.ineffectiveTools) {
      suggestions.push({
        id: `opt_remove_${toolName}`,
        type: 'remove_tool',
        description: `移除无效工具: ${toolName}`,
        reason: `上次进化新增的工具 ${toolName} 效果不佳（胜率低或负收益）`,
        expectedImpact: '减少噪音，提升决策质量',
        priority: 'high',
        data: { toolName }
      });
    }
  }
  
  // 2. 如果上次进化整体无效，降低本次进化的激进程度
  const aggressiveness = lastEvolutionEval?.effective === false ? 'conservative' : 'normal';
  
  // 3. 避免重复建议
  const previousSuggestions = lastEvolutionEval?.appliedSuggestions || [];
  
  // 4. 根据差距生成新建议（排除已尝试过的）
  if (Math.abs(gap.gap) >= 2) {
    // 生成新建议，但排除上次已尝试且无效的
    const newSuggestions = generateNewSuggestions(
      gap,
      weaknesses,
      toolStats,
      aggressiveness
    );
    
    // 过滤掉重复的建议
    const filtered = newSuggestions.filter(s => {
      return !previousSuggestions.some(prev => 
        prev.type === s.type && 
        prev.data?.toolName === s.data?.toolName
      );
    });
    
    suggestions.push(...filtered);
  }
  
  return suggestions;
}
```

### A.4 进化历史保存

```typescript
async function saveEvolutionHistory(
  evolutionId: string,
  suggestions: OptimizationSuggestion[],
  applied: string[],
  baseline: PerformanceMetrics
): Promise<void> {
  
  const history: EvolutionHistory = {
    evolutionId,
    date: new Date().toISOString(),
    branchName: `evolution/${evolutionId}`,
    suggestions,
    applied,
    baseline: {
      return: baseline.return,
      winRate: baseline.winRate,
      maxDrawdown: baseline.maxDrawdown,
      toolStats: baseline.toolStats,
    },
    // outcome 和 evaluation 在下次进化时填充
  };
  
  const historyDir = path.join(piDir, 'evolution/history');
  await fs.mkdir(historyDir, { recursive: true });
  
  const historyPath = path.join(historyDir, `${evolutionId}.json`);
  await fs.writeFile(historyPath, JSON.stringify(history, null, 2), 'utf-8');
}
```

### A.5 更新上次进化的结果

```typescript
async function updateLastEvolutionOutcome(
  lastEvolution: EvolutionHistory,
  currentMetrics: PerformanceMetrics,
  evaluation: EvolutionEvaluation
): Promise<void> {
  
  lastEvolution.outcome = {
    return: currentMetrics.return,
    winRate: currentMetrics.winRate,
    maxDrawdown: currentMetrics.maxDrawdown,
    toolStats: currentMetrics.toolStats,
    improvement: evaluation.improvement,
  };
  
  lastEvolution.evaluation = {
    effective: evaluation.effective,
    effectiveTools: evaluation.effectiveTools,
    ineffectiveTools: evaluation.ineffectiveTools,
    reasons: evaluation.reasons,
  };
  
  const historyPath = path.join(
    piDir,
    'evolution/history',
    `${lastEvolution.evolutionId}.json`
  );
  
  await fs.writeFile(
    historyPath,
    JSON.stringify(lastEvolution, null, 2),
    'utf-8'
  );
}
```

### A.6 完整流程（更新）

```
/evolution 触发
    ↓
1. 加载上次进化历史
    ↓
2. 评估上次进化效果
    ├─ 计算指标变化
    ├─ 评估每个工具的效果
    └─ 更新上次进化的 outcome 和 evaluation
    ↓
3. 减法器计算当前差距
    ↓
4. 补偿器生成建议（基于评估结果）
    ├─ 优先移除无效工具
    ├─ 避免重复建议
    └─ 根据上次效果调整激进程度
    ↓
5. 效应器执行
    ├─ 创建分支
    ├─ 生成代码
    ├─ 验证
    └─ 提交
    ↓
6. 保存本次进化历史（baseline）
    ↓
7. 生成报告（包含上次进化评估）
```

### A.7 报告增强

进化报告中新增"上次进化效果评估"部分：

```markdown
# 进化报告 2026-05-14

## 📊 上次进化效果评估 (2026-05-07)

### 整体效果
✅ **有效** - 收益率提升 1.2%，胜率提升 3%

### 工具效果评估

#### ✅ 有效工具
- **analyze_sector_rotation**: 调用 15 次，胜率 73%，平均收益 +4.2%
- **check_stop_loss_trigger**: 调用 8 次，成功避免 3 次亏损扩大

#### ❌ 无效工具
- **predict_market_trend**: 调用 12 次，胜率 42%，平均收益 -1.5%
  - **建议**: 本次进化将移除此工具

### 改进建议
- 保留有效工具，继续观察
- 移除无效工具，避免噪音
- 本次进化采用正常激进度

---

## 📊 本次表现
...
```

---

**补充完成**

---

## 附录 B：完全自动化流程（无需用户审核）

### B.1 设计变更

**原设计**：
```
效应器执行 → 生成报告 → 用户审核 → 手动合并/拒绝
```

**新设计**：
```
效应器执行 → 验证通过 → 自动合并到 main → 记录完整日志
```

### B.2 自动合并流程

```typescript
async function autoMergeEvolution(
  branchName: string,
  validationResults: ValidationResult[]
): Promise<AutoMergeResult> {
  
  // 1. 检查是否所有验证都通过
  const allPassed = validationResults.every(r => r.passed);
  
  if (!allPassed) {
    // 有验证失败，不合并，删除分支
    await exec('git checkout main');
    await exec(`git branch -D ${branchName}`);
    
    return {
      merged: false,
      reason: '部分验证失败，已回退',
      failedValidations: validationResults.filter(r => !r.passed)
    };
  }
  
  // 2. 切换到 main 分支
  await exec('git checkout main');
  await exec('git pull');
  
  // 3. 合并进化分支
  const mergeMessage = `chore(evolution): auto-merge ${branchName}`;
  await exec(`git merge ${branchName} -m "${mergeMessage}"`);
  
  // 4. 推送到远程
  await exec('git push');
  
  // 5. 删除进化分支（已合并）
  await exec(`git branch -d ${branchName}`);
  
  // 6. 记录合并信息
  const { stdout: mergeCommit } = await exec('git rev-parse HEAD');
  
  return {
    merged: true,
    mergeCommit: mergeCommit.trim(),
    branchName,
    timestamp: new Date().toISOString()
  };
}
```

### B.3 执行记录保存

#### 记录结构

```typescript
interface EvolutionExecutionLog {
  executionId: string;
  timestamp: string;
  
  // 输入
  trigger: 'manual' | 'scheduled';
  gap: PerformanceGap;
  suggestions: OptimizationSuggestion[];
  
  // 执行过程
  branchName: string;
  commits: Array<{
    hash: string;
    message: string;
    files: string[];
    timestamp: string;
  }>;
  
  // 验证结果
  validations: Array<{
    toolName: string;
    passed: boolean;
    compilation: { passed: boolean; duration: number; error?: string };
    unitTest: { passed: boolean; duration: number; error?: string };
    integration: { passed: boolean; duration: number; error?: string };
  }>;
  
  // 合并结果
  merge: {
    merged: boolean;
    mergeCommit?: string;
    reason?: string;
    timestamp?: string;
  };
  
  // 统计
  stats: {
    totalSuggestions: number;
    appliedSuggestions: number;
    failedSuggestions: number;
    totalDuration: number; // 毫秒
  };
}
```

#### 存储位置

```
.pi-invest/evolution/
├── history/
│   ├── 2026-05-07.json          # 进化历史（效果评估）
│   └── 2026-05-14.json
├── execution-logs/
│   ├── 2026-05-07T10:30:00.json # 执行日志（详细过程）
│   └── 2026-05-14T10:30:00.json
├── evolution-2026-05-07.md      # 进化报告（Markdown）
└── evolution-2026-05-14.md
```

#### 保存逻辑

```typescript
async function saveExecutionLog(log: EvolutionExecutionLog): Promise<string> {
  const logDir = path.join(piDir, 'evolution/execution-logs');
  await fs.mkdir(logDir, { recursive: true });
  
  const logPath = path.join(logDir, `${log.executionId}.json`);
  await fs.writeFile(logPath, JSON.stringify(log, null, 2), 'utf-8');
  
  return logPath;
}
```

### B.4 完整自动化流程

```
/evolution 触发
    ↓
1. 加载上次进化历史
    ↓
2. 评估上次进化效果
    ↓
3. 减法器计算差距
    ↓
4. 补偿器生成建议
    ↓
5. 创建执行日志（开始记录）
    ↓
6. 效应器执行
    ├─ 创建 evolution/YYYY-MM-DD 分支
    ├─ 对每个建议：
    │   ├─ 生成代码
    │   ├─ 沙箱验证（记录详细结果）
    │   ├─ 验证通过 → commit（记录 commit hash）
    │   └─ 验证失败 → 跳过（记录失败原因）
    └─ 记录所有 commits
    ↓
7. 检查验证结果
    ├─ 全部通过 → 自动合并到 main
    │   ├─ git merge
    │   ├─ git push
    │   └─ 删除进化分支
    └─ 有失败 → 删除分支，不合并
    ↓
8. 更新执行日志（合并结果）
    ↓
9. 保存本次进化历史（baseline）
    ↓
10. 生成进化报告（Markdown）
    ↓
11. 输出执行摘要
```

### B.5 执行摘要输出

```
🔄 自动进化执行完成

📊 执行摘要
  执行ID: 2026-05-14T10:30:00
  触发方式: 手动 (/evolution)
  执行时长: 3分42秒

💡 建议处理
  总建议数: 3
  成功应用: 2
  验证失败: 1

✅ 成功应用
  1. analyze_sector_rotation
     - 编译: ✅ (1.2s)
     - 单元测试: ✅ (2.5s)
     - 集成测试: ✅ (3.8s)
     - 提交: a1b2c3d
  
  2. check_stop_loss_trigger
     - 编译: ✅ (1.1s)
     - 单元测试: ✅ (2.3s)
     - 集成测试: ✅ (4.1s)
     - 提交: d4e5f6g

❌ 验证失败
  1. predict_market_trend
     - 编译: ✅
     - 单元测试: ❌ (TypeError: Cannot read property 'data')
     - 已回退，未提交

🔀 合并结果
  ✅ 已自动合并到 main
  合并提交: h7i8j9k
  已推送到远程: origin/main

📝 记录保存
  执行日志: .pi-invest/evolution/execution-logs/2026-05-14T10:30:00.json
  进化历史: .pi-invest/evolution/history/2026-05-14.json
  进化报告: .pi-invest/evolution/evolution-2026-05-14.md

🔍 查看详情
  git log --oneline -5
  cat .pi-invest/evolution/execution-logs/2026-05-14T10:30:00.json
```

### B.6 失败场景处理

#### 场景 1: 所有验证都失败

```
❌ 自动进化失败

所有建议验证失败，未进行任何修改。

失败原因:
  1. analyze_sector_rotation: 编译错误
  2. check_stop_loss_trigger: 集成测试失败
  3. predict_market_trend: 单元测试失败

已删除进化分支: evolution/2026-05-14-auto-evolution
未对 main 分支进行任何修改。

📝 执行日志已保存，可用于调试。
```

#### 场景 2: 部分验证失败

```
⚠️ 自动进化部分成功

成功应用: 2/3
验证失败: 1/3

✅ 已合并到 main:
  - analyze_sector_rotation
  - check_stop_loss_trigger

❌ 验证失败（未应用）:
  - predict_market_trend

合并提交: h7i8j9k
```

### B.7 回退机制（自动化版本）

由于已自动合并到 main，回退需要使用 git revert：

```typescript
async function autoRevertEvolution(mergeCommit: string): Promise<void> {
  // 1. 确认在 main 分支
  await exec('git checkout main');
  await exec('git pull');
  
  // 2. Revert 合并提交
  await exec(`git revert -m 1 ${mergeCommit}`);
  
  // 3. 推送
  await exec('git push');
  
  // 4. 记录回退
  const revertLog = {
    revertedCommit: mergeCommit,
    revertCommit: await exec('git rev-parse HEAD'),
    timestamp: new Date().toISOString(),
    reason: '自动回退：进化效果不佳'
  };
  
  await saveRevertLog(revertLog);
}
```

### B.8 监控和告警

虽然是自动化，但需要监控关键指标：

```typescript
interface EvolutionMonitoring {
  // 成功率监控
  successRate: number; // 最近 10 次进化的成功率
  
  // 验证失败率
  validationFailureRate: number;
  
  // 合并失败次数
  mergeFailures: number;
  
  // 告警阈值
  alerts: {
    successRateBelowThreshold: boolean; // < 70%
    tooManyValidationFailures: boolean; // > 50%
    consecutiveMergeFailures: boolean;  // 连续 3 次
  };
}

async function checkEvolutionHealth(): Promise<EvolutionMonitoring> {
  const recentLogs = await loadRecentExecutionLogs(10);
  
  const successCount = recentLogs.filter(log => log.merge.merged).length;
  const successRate = successCount / recentLogs.length;
  
  const validationFailures = recentLogs.reduce(
    (sum, log) => sum + log.stats.failedSuggestions,
    0
  );
  const totalSuggestions = recentLogs.reduce(
    (sum, log) => sum + log.stats.totalSuggestions,
    0
  );
  const validationFailureRate = validationFailures / totalSuggestions;
  
  return {
    successRate,
    validationFailureRate,
    mergeFailures: recentLogs.length - successCount,
    alerts: {
      successRateBelowThreshold: successRate < 0.7,
      tooManyValidationFailures: validationFailureRate > 0.5,
      consecutiveMergeFailures: checkConsecutiveFailures(recentLogs, 3)
    }
  };
}
```

---

**完全自动化设计完成**
