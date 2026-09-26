import {
  DesignCoverage,
  ImplementationCoverage,
  TestingCoverage,
} from '../types/rtm';

/**
 * 门禁检查结果
 */
export interface GateCheckResult {
  /** 是否通过 */
  passed: boolean;
  /** 检查消息 */
  message: string;
  /** 覆盖率（百分比） */
  coverageRate: number;
  /** 未覆盖项列表 */
  uncovered?: string[];
  /** 详细信息 */
  details?: {
    total: number;
    covered: number;
    rate: number;
  };
}

/**
 * 门禁类型
 */
export type GateType = 'design' | 'implementation' | 'testing';

/**
 * 门禁配置
 */
export interface GateConfig {
  /** 最低覆盖率要求（百分比） */
  minimumCoverage: number;
  /** 门禁名称 */
  name: string;
  /** 描述 */
  description: string;
}

/**
 * 默认门禁配置
 */
export const DEFAULT_GATE_CONFIGS: Record<GateType, GateConfig> = {
  design: {
    minimumCoverage: 100,
    name: '设计覆盖度门禁',
    description: '所有 FR 都必须有对应的设计章节',
  },
  implementation: {
    minimumCoverage: 100,
    name: '实施覆盖度门禁',
    description: '所有设计章节都必须有对应的实施任务',
  },
  testing: {
    minimumCoverage: 80,
    name: '测试覆盖度门禁',
    description: '至少 80% 的任务必须有对应的测试用例',
  },
};

/**
 * 设计覆盖度门禁检查
 */
export function checkDesignGate(
  coverage: DesignCoverage,
  config: GateConfig = DEFAULT_GATE_CONFIGS.design
): GateCheckResult {
  const passed = coverage.rate >= config.minimumCoverage;

  if (passed) {
    return {
      passed: true,
      message: `✅ ${config.name}通过：覆盖度 ${coverage.rate}% (${coverage.covered_frs}/${coverage.total_frs})`,
      coverageRate: coverage.rate,
      details: {
        total: coverage.total_frs,
        covered: coverage.covered_frs,
        rate: coverage.rate,
      },
    };
  } else {
    const missing = coverage.uncovered.length;
    return {
      passed: false,
      message: `❌ ${config.name}未通过：覆盖度 ${coverage.rate}% (${coverage.covered_frs}/${coverage.total_frs})，需要 ≥${config.minimumCoverage}%。缺少 ${missing} 个 FR 的设计。`,
      coverageRate: coverage.rate,
      uncovered: coverage.uncovered,
      details: {
        total: coverage.total_frs,
        covered: coverage.covered_frs,
        rate: coverage.rate,
      },
    };
  }
}

/**
 * 实施覆盖度门禁检查
 */
export function checkImplementationGate(
  coverage: ImplementationCoverage,
  config: GateConfig = DEFAULT_GATE_CONFIGS.implementation
): GateCheckResult {
  const passed = coverage.rate >= config.minimumCoverage;

  if (passed) {
    return {
      passed: true,
      message: `✅ ${config.name}通过：覆盖度 ${coverage.rate}% (${coverage.covered_designs}/${coverage.total_designs})`,
      coverageRate: coverage.rate,
      details: {
        total: coverage.total_designs,
        covered: coverage.covered_designs,
        rate: coverage.rate,
      },
    };
  } else {
    const missing = coverage.uncovered.length;
    return {
      passed: false,
      message: `❌ ${config.name}未通过：覆盖度 ${coverage.rate}% (${coverage.covered_designs}/${coverage.total_designs})，需要 ≥${config.minimumCoverage}%。以下 ${missing} 个设计章节缺少任务：\n${coverage.uncovered.map(item => `  - ${item}`).join('\n')}`,
      coverageRate: coverage.rate,
      uncovered: coverage.uncovered,
      details: {
        total: coverage.total_designs,
        covered: coverage.covered_designs,
        rate: coverage.rate,
      },
    };
  }
}

/**
 * 测试覆盖度门禁检查
 */
export function checkTestingGate(
  coverage: TestingCoverage,
  config: GateConfig = DEFAULT_GATE_CONFIGS.testing
): GateCheckResult {
  const passed = coverage.rate >= config.minimumCoverage;

  if (passed) {
    return {
      passed: true,
      message: `✅ ${config.name}通过：覆盖度 ${coverage.rate}% (${coverage.tested_tasks}/${coverage.total_tasks})`,
      coverageRate: coverage.rate,
      details: {
        total: coverage.total_tasks,
        covered: coverage.tested_tasks,
        rate: coverage.rate,
      },
    };
  } else {
    const missing = coverage.untested.length;
    return {
      passed: false,
      message: `❌ ${config.name}未通过：覆盖度 ${coverage.rate}% (${coverage.tested_tasks}/${coverage.total_tasks})，需要 ≥${config.minimumCoverage}%。以下 ${missing} 个任务缺少测试用例：\n${coverage.untested.map(item => `  - ${item}`).join('\n')}`,
      coverageRate: coverage.rate,
      uncovered: coverage.untested,
      details: {
        total: coverage.total_tasks,
        covered: coverage.tested_tasks,
        rate: coverage.rate,
      },
    };
  }
}

/**
 * 统一门禁检查接口
 */
export function checkGate(
  type: GateType,
  coverage: DesignCoverage | ImplementationCoverage | TestingCoverage,
  config?: GateConfig
): GateCheckResult {
  switch (type) {
    case 'design':
      return checkDesignGate(coverage as DesignCoverage, config);
    case 'implementation':
      return checkImplementationGate(coverage as ImplementationCoverage, config);
    case 'testing':
      return checkTestingGate(coverage as TestingCoverage, config);
    default:
      throw new Error(`Unknown gate type: ${type}`);
  }
}

/**
 * 批量门禁检查
 */
export interface BatchGateCheckResult {
  /** 所有门禁是否都通过 */
  allPassed: boolean;
  /** 各门禁检查结果 */
  results: {
    design?: GateCheckResult;
    implementation?: GateCheckResult;
    testing?: GateCheckResult;
  };
  /** 未通过的门禁列表 */
  failedGates: GateType[];
  /** 汇总消息 */
  summary: string;
}

/**
 * 批量检查多个门禁
 */
export function checkMultipleGates(checks: {
  design?: DesignCoverage;
  implementation?: ImplementationCoverage;
  testing?: TestingCoverage;
}): BatchGateCheckResult {
  const results: BatchGateCheckResult['results'] = {};
  const failedGates: GateType[] = [];

  if (checks.design) {
    results.design = checkDesignGate(checks.design);
    if (!results.design.passed) {
      failedGates.push('design');
    }
  }

  if (checks.implementation) {
    results.implementation = checkImplementationGate(checks.implementation);
    if (!results.implementation.passed) {
      failedGates.push('implementation');
    }
  }

  if (checks.testing) {
    results.testing = checkTestingGate(checks.testing);
    if (!results.testing.passed) {
      failedGates.push('testing');
    }
  }

  const allPassed = failedGates.length === 0;
  const totalChecks = Object.keys(checks).length;
  const passedChecks = totalChecks - failedGates.length;

  const summary = allPassed
    ? `✅ 所有 ${totalChecks} 个门禁都已通过`
    : `❌ ${totalChecks} 个门禁中有 ${failedGates.length} 个未通过：${failedGates.join(', ')}`;

  return {
    allPassed,
    results,
    failedGates,
    summary,
  };
}
