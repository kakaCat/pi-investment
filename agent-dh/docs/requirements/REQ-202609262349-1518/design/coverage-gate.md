# 覆盖度统计与门禁


实现覆盖度计算器和门禁检查器，计算设计/实施/测试三种覆盖度，在 reqboard_submit 时执行门禁检查（设计 100%、实施 100%、测试 ≥80%），不足时拒绝提交并返回缺口清单，验收标准：故意提交覆盖度不足的文档时被门禁拦截，补充后通过。


## CoverageCalculator 实现（serves: FR-6）

```typescript
// packages/web/dsh-pmboard/src/rtm/CoverageCalculator.ts

export interface Coverage {
  design?: {
    total_frs: number
    covered_frs: number
    uncovered: string[]       // 缺少设计的 FR
    rate: number              // 0.0 ~ 1.0
  }
  implementation?: {
    total_designs: number
    covered_designs: number
    uncovered: string[]       // 缺少任务的设计章节
    rate: number
  }
  testing?: {
    total_tasks: number
    tested_tasks: number
    untested: string[]        // 缺少测试的任务
    rate: number
  }
}

export class CoverageCalculator {
  calculate(traceability: TraceabilityMap, stage: Stage, frs?: string[], designs?: string[], tasks?: string[]): Coverage {
    switch (stage) {
      case 'design':
        return { design: this.calcDesignCoverage(traceability.fr_to_design!, frs!) };
      case 'decomposing':
        return { implementation: this.calcImplementationCoverage(traceability.design_to_tasks!, designs!) };
      case 'accepting':
        return { testing: this.calcTestingCoverage(traceability.task_to_tests!, tasks!) };
      default:
        return {};
    }
  }

  private calcDesignCoverage(fr_to_design: Record<string, string[]>, allFRs: string[]) {
    const covered = allFRs.filter(fr => fr_to_design[fr] && fr_to_design[fr].length > 0);
    const uncovered = allFRs.filter(fr => !fr_to_design[fr] || fr_to_design[fr].length === 0);
    
    return {
      total_frs: allFRs.length,
      covered_frs: covered.length,
      uncovered,
      rate: allFRs.length > 0 ? covered.length / allFRs.length : 0
    };
  }

  private calcImplementationCoverage(design_to_tasks: Record<string, string[]>, allDesigns: string[]) {
    const covered = allDesigns.filter(d => design_to_tasks[d] && design_to_tasks[d].length > 0);
    const uncovered = allDesigns.filter(d => !design_to_tasks[d] || design_to_tasks[d].length === 0);
    
    return {
      total_designs: allDesigns.length,
      covered_designs: covered.length,
      uncovered,
      rate: allDesigns.length > 0 ? covered.length / allDesigns.length : 0
    };
  }

  private calcTestingCoverage(task_to_tests: Record<string, string[]>, allTasks: string[]) {
    const tested = allTasks.filter(t => task_to_tests[t] && task_to_tests[t].length > 0);
    const untested = allTasks.filter(t => !task_to_tests[t] || task_to_tests[t].length === 0);
    
    return {
      total_tasks: allTasks.length,
      tested_tasks: tested.length,
      untested,
      rate: allTasks.length > 0 ? tested.length / allTasks.length : 0
    };
  }
}
```

## CoverageGate 实现（serves: FR-7）

```typescript
// packages/web/dsh-pmboard/src/rtm/CoverageGate.ts

export class CoverageGate {
  check(kind: 'design' | 'plan' | 'verification', coverage: Coverage): void {
    if (kind === 'design') {
      if (!coverage.design || coverage.design.rate < 1.0) {
        throw new CoverageInsufficientError('design', coverage.design!);
      }
    }
    
    if (kind === 'plan') {
      if (!coverage.implementation || coverage.implementation.rate < 1.0) {
        throw new CoverageInsufficientError('implementation', coverage.implementation!);
      }
    }
    
    if (kind === 'verification') {
      if (!coverage.testing || coverage.testing.rate < 0.8) {
        throw new CoverageInsufficientError('testing', coverage.testing!);
      }
    }
  }
}

class CoverageInsufficientError extends Error {
  constructor(public kind: string, public coverage: any) {
    super(`Coverage insufficient: ${kind}`);
    this.name = 'COVERAGE_INSUFFICIENT';
  }
}
```


```bash
# 测试：设计覆盖度门禁（故意缺少 FR-3 的设计）
node -e "
// 提交设计文档（FR-3 无设计章节）
try {
  reqboard_submit({ kind: 'design', path: '...' });
  assert(false, '应该被门禁拦截');
} catch (err) {
  assert(err.name === 'COVERAGE_INSUFFICIENT');
  assert(err.kind === 'design');
  assert(err.coverage.uncovered.includes('FR-3'));
  console.log('✅ 设计覆盖度门禁正常工作');
}
"

# 补充设计后通过
node -e "
// 补充 FR-3 的设计章节
// 重新提交
reqboard_submit({ kind: 'design' });
console.log('✅ 设计覆盖度 100%，门禁通过');
"
```