/**
 * Evolution Executor Tests
 */

import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { Type } from '@sinclair/typebox';
import * as fs from 'fs/promises';
import * as path from 'path';
import type { OptimizationSuggestion } from '../../types/evolution.js';
import type { ExecutionResult, ActuatorConfig } from './evolution-executor.js';

// add_tool 新架构（Codex 代码生成 + git 分支流）依赖外部 CLI 与 git 操作，
// 单元测试 mock 三个边界模块使其可hermetic运行
const mockGenerateToolCode = jest.fn<(...args: any[]) => Promise<any>>();
const mockWriteGeneratedCode = jest.fn<(...args: any[]) => Promise<any>>();

jest.unstable_mockModule('./code-generator.js', () => ({
  generateToolCode: mockGenerateToolCode,
  writeGeneratedCode: mockWriteGeneratedCode,
}));

jest.unstable_mockModule('./sandbox-validator.js', () => ({
  validateInSandbox: jest.fn(async () => []),
  allValidationsPassed: jest.fn(() => true),
  formatValidationResults: jest.fn(() => ''),
}));

jest.unstable_mockModule('./evolution-branch-manager.js', () => ({
  getCurrentBranch: jest.fn(async () => 'main'),
  createEvolutionBranch: jest.fn(async () => 'evolution/test-branch'),
  commitChanges: jest.fn(async () => 'abc1234'),
  mergeToBranch: jest.fn(async () => undefined),
  rollbackToBranch: jest.fn(async () => undefined),
}));

const {
  executeOptimizationSuggestions,
  rollbackExecution,
  getExecutionHistory,
} = await import('./evolution-executor.js');

/** add_tool 全 mock 成功的建议项（name/toolFileName 精确命中 index.ts 已有 import，
 *  registerToolToIndex 早退不写真实文件） */
function makeAddToolSuggestion(id: string, description = '测试工具'): OptimizationSuggestion {
  return {
    id,
    type: 'add_tool',
    priority: 'medium',
    description: '添加工具',
    reason: '测试',
    expectedImpact: '无',
    data: {
      name: 'modelSwitch',
      description,
      reason: '测试',
      expectedImpact: '无',
    },
  };
}

const TEST_PI_DIR = path.join(process.cwd(), '.pi-invest-test');
const TEST_EVOLUTION_DIR = path.join(TEST_PI_DIR, 'evolution');

describe('Evolution Executor', () => {
  beforeEach(async () => {
    await fs.mkdir(TEST_EVOLUTION_DIR, { recursive: true });
  });

  afterEach(async () => {
    await fs.rm(TEST_PI_DIR, { recursive: true, force: true });
  });

  describe('executeOptimizationSuggestions', () => {
    it('should execute experience update suggestion', async () => {
      const suggestions: OptimizationSuggestion[] = [
        {
          id: 'sug_001',
          type: 'update_experience',
          priority: 'high',
          description: '添加新经验模式',
          reason: '发现高胜率模式',
          expectedImpact: '提升决策准确率',
          data: {
            pattern: {
              pattern: '突破MA20后回踩',
              conditions: ['价格突破MA20', '回踩确认支撑'],
              action: 'buy',
              count: 10,
              winRate: 0.7,
              avgReturn: 0.05,
            },
          },
        },
      ];

      const result = await executeOptimizationSuggestions(suggestions, TEST_PI_DIR);

      expect(result.applied).toHaveLength(1);
      expect(result.applied[0].status).toBe('success');
      expect(result.applied[0].type).toBe('update_experience');
    });

    it('should execute tool addition suggestion', async () => {
      mockGenerateToolCode.mockResolvedValue({
        toolFileName: 'agent/model-switch-tool.ts',
        toolCode: '// tool',
        testFileName: 'agent/model-switch-tool.test.ts',
        testCode: '// test',
      });
      mockWriteGeneratedCode.mockResolvedValue({
        toolPath: '/tmp/model-switch-tool.ts',
        testPath: '/tmp/model-switch-tool.test.ts',
      });

      const result = await executeOptimizationSuggestions(
        [makeAddToolSuggestion('sug_002', '计算RSI相对强弱指标')],
        TEST_PI_DIR
      );

      expect(result.applied).toHaveLength(1);
      expect(result.applied[0].status).toBe('success');
      expect(result.applied[0].type).toBe('add_tool');
      // 新架构 rollbackData：git 分支信息（非旧 registry 契约）
      expect(result.applied[0].rollbackData.branchName).toBe('evolution/test-branch');
      expect(result.applied[0].rollbackData.commitHash).toBe('abc1234');
    });

    it('should execute tool removal suggestion', async () => {
      const registryPath = path.join(TEST_EVOLUTION_DIR, 'dynamic-tools.json');
      await fs.writeFile(
        registryPath,
        JSON.stringify({
          tools: [
            {
              name: 'obsolete_tool',
              description: '过时的工具',
              parameters: Type.Object({}),
            },
          ],
        }),
        'utf-8'
      );

      const suggestions: OptimizationSuggestion[] = [
        {
          id: 'sug_003',
          type: 'remove_tool',
          priority: 'low',
          description: '移除低效工具',
          reason: '使用率低且效果差',
          expectedImpact: '减少token消耗',
          data: {
            name: 'obsolete_tool',
            reason: '胜率低于40%',
            evidence: {
              callCount: 5,
              winRate: 0.2,
              avgReturn: -0.03,
            },
          },
        },
      ];

      const result = await executeOptimizationSuggestions(suggestions, TEST_PI_DIR);

      expect(result.applied).toHaveLength(1);
      expect(result.applied[0].status).toBe('success');
      expect(result.applied[0].type).toBe('remove_tool');

      const registryContent = await fs.readFile(registryPath, 'utf-8');
      const registry = JSON.parse(registryContent);

      expect(registry.tools).toHaveLength(0);
    });

    it('should execute parameter adjustment suggestion', async () => {
      const suggestions: OptimizationSuggestion[] = [
        {
          id: 'sug_004',
          type: 'adjust_parameter',
          priority: 'high',
          description: '调整止损阈值',
          reason: '当前止损过于激进',
          expectedImpact: '减少误触止损',
          data: {
            paramName: 'stop_loss_threshold',
            newValue: 0.08,
          },
        },
      ];

      const result = await executeOptimizationSuggestions(suggestions, TEST_PI_DIR);

      expect(result.applied).toHaveLength(1);
      expect(result.applied[0].status).toBe('success');
      expect(result.applied[0].type).toBe('adjust_parameter');

      const configPath = path.join(TEST_EVOLUTION_DIR, 'runtime-config.json');
      const configContent = await fs.readFile(configPath, 'utf-8');
      const config = JSON.parse(configContent);

      expect(config.stop_loss_threshold).toBe(0.08);
    });

    it('should reject parameter adjustment outside valid range', async () => {
      const suggestions: OptimizationSuggestion[] = [
        {
          id: 'sug_005',
          type: 'adjust_parameter',
          priority: 'high',
          description: '调整止损阈值',
          reason: '测试范围验证',
          expectedImpact: '无',
          data: {
            paramName: 'stop_loss_threshold',
            newValue: 0.5,
          },
        },
      ];

      const result = await executeOptimizationSuggestions(suggestions, TEST_PI_DIR);

      expect(result.applied).toHaveLength(1);
      expect(result.applied[0].status).toBe('error');
      expect(result.applied[0].message).toContain('超出允许范围');
    });

    it('should generate manual tasks when autoExecute is false', async () => {
      const suggestions: OptimizationSuggestion[] = [
        {
          id: 'sug_006',
          type: 'add_tool',
          priority: 'high',
          description: '添加新工具',
          reason: '需要人工审核',
          expectedImpact: '提升能力',
          data: {
            name: 'new_tool',
            description: '新工具',
          },
        },
      ];

      const config: Partial<ActuatorConfig> = {
        autoExecute: false,
      };

      const result = await executeOptimizationSuggestions(suggestions, TEST_PI_DIR, config);

      expect(result.applied).toHaveLength(1);
      expect(result.applied[0].status).toBe('skipped');
      expect(result.manualTasks).toHaveLength(1);
      expect(result.manualTasks[0].type).toBe('add_tool');
    });

    it('should generate manual tasks for types requiring approval', async () => {
      const suggestions: OptimizationSuggestion[] = [
        {
          id: 'sug_007',
          type: 'remove_tool',
          priority: 'high',
          description: '移除工具',
          reason: '需要审核',
          expectedImpact: '减少复杂度',
          data: {
            name: 'some_tool',
          },
        },
      ];

      const config: Partial<ActuatorConfig> = {
        requireApproval: ['remove_tool'],
      };

      const result = await executeOptimizationSuggestions(suggestions, TEST_PI_DIR, config);

      expect(result.applied).toHaveLength(1);
      expect(result.applied[0].status).toBe('skipped');
      expect(result.manualTasks).toHaveLength(1);
    });
  });

  describe('rollbackExecution', () => {
    it('should rollback tool addition', async () => {
      mockGenerateToolCode.mockResolvedValue({
        toolFileName: 'agent/model-switch-tool.ts',
        toolCode: '// tool',
        testFileName: 'agent/model-switch-tool.test.ts',
        testCode: '// test',
      });
      mockWriteGeneratedCode.mockResolvedValue({
        toolPath: '/tmp/model-switch-tool.ts',
        testPath: '/tmp/model-switch-tool.test.ts',
      });

      const result = await executeOptimizationSuggestions(
        [makeAddToolSuggestion('sug_008')],
        TEST_PI_DIR
      );
      const rollbackData = result.applied[0].rollbackData;

      // 新架构：rollback 写入 execution-log（add_tool 的回滚动作是删分支/提交，由人工或流程处理）
      await rollbackExecution('sug_008', rollbackData, TEST_PI_DIR);

      const history = await getExecutionHistory(TEST_PI_DIR, 10);
      const rollbackEntry = history.find((h: any) => h.type === 'rollback' && h.suggestionId === 'sug_008');
      expect(rollbackEntry).toBeDefined();
      expect(rollbackEntry!.status).toBe('success');
    });

    it('should rollback parameter adjustment', async () => {
      const configPath = path.join(TEST_EVOLUTION_DIR, 'runtime-config.json');
      await fs.writeFile(
        configPath,
        JSON.stringify({ stop_loss_threshold: 0.05 }),
        'utf-8'
      );

      const suggestions: OptimizationSuggestion[] = [
        {
          id: 'sug_009',
          type: 'adjust_parameter',
          priority: 'high',
          description: '调整参数',
          reason: '测试回滚',
          expectedImpact: '无',
          data: {
            paramName: 'stop_loss_threshold',
            newValue: 0.1,
          },
        },
      ];

      const result = await executeOptimizationSuggestions(suggestions, TEST_PI_DIR);
      const rollbackData = result.applied[0].rollbackData;

      await rollbackExecution('sug_009', rollbackData, TEST_PI_DIR);

      const configContent = await fs.readFile(configPath, 'utf-8');
      const config = JSON.parse(configContent);

      expect(config.stop_loss_threshold).toBe(0.05);
    });
  });

  describe('getExecutionHistory', () => {
    it('should return execution history', async () => {
      const suggestions: OptimizationSuggestion[] = [
        {
          id: 'sug_010',
          type: 'update_experience',
          priority: 'high',
          description: '测试历史记录',
          reason: '测试',
          expectedImpact: '无',
          data: {
            pattern: {
              pattern: '测试模式',
              conditions: [],
              action: 'hold',
              count: 1,
              winRate: 0.5,
              avgReturn: 0,
            },
          },
        },
      ];

      await executeOptimizationSuggestions(suggestions, TEST_PI_DIR);

      const history = await getExecutionHistory(TEST_PI_DIR, 10);

      expect(history.length).toBeGreaterThan(0);
      expect(history[0].suggestionId).toBe('sug_010');
      expect(history[0].type).toBe('update_experience');
    });

    it('should return empty array when no history exists', async () => {
      const history = await getExecutionHistory(TEST_PI_DIR, 10);
      expect(history).toEqual([]);
    });
  });

  describe('execution logging', () => {
    it('should log tool changes to history file', async () => {
      mockGenerateToolCode.mockResolvedValue({
        toolFileName: 'agent/model-switch-tool.ts',
        toolCode: '// tool',
        testFileName: 'agent/model-switch-tool.test.ts',
        testCode: '// test',
      });
      mockWriteGeneratedCode.mockResolvedValue({
        toolPath: '/tmp/model-switch-tool.ts',
        testPath: '/tmp/model-switch-tool.test.ts',
      });

      await executeOptimizationSuggestions([makeAddToolSuggestion('sug_011')], TEST_PI_DIR);

      // 新架构：工具变更记录在 execution-log.json（tool-changes.jsonl 仅参数调整使用）
      const history = await getExecutionHistory(TEST_PI_DIR, 10);
      const addEntry = history.find((h: any) => h.type === 'add_tool' && h.suggestionId === 'sug_011');
      expect(addEntry).toBeDefined();
      expect(addEntry!.status).toBe('success');
    });

    it('should log parameter changes to history file', async () => {
      const suggestions: OptimizationSuggestion[] = [
        {
          id: 'sug_012',
          type: 'adjust_parameter',
          priority: 'high',
          description: '测试参数日志',
          reason: '测试',
          expectedImpact: '无',
          data: {
            paramName: 'risk_preference',
            newValue: 0.6,
          },
        },
      ];

      await executeOptimizationSuggestions(suggestions, TEST_PI_DIR);

      const historyPath = path.join(TEST_EVOLUTION_DIR, 'parameter-changes.jsonl');
      const historyContent = await fs.readFile(historyPath, 'utf-8');
      const lines = historyContent.trim().split('\n');

      expect(lines.length).toBeGreaterThan(0);

      const lastLog = JSON.parse(lines[lines.length - 1]);
      expect(lastLog.paramName).toBe('risk_preference');
      expect(lastLog.newValue).toBe(0.6);
    });
  });
});
