/**
 * Evolution Executor Tests
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { Type } from '@sinclair/typebox';
import * as fs from 'fs/promises';
import * as path from 'path';
import {
  executeOptimizationSuggestions,
  rollbackExecution,
  getExecutionHistory,
  type ExecutionResult,
  type ActuatorConfig,
} from './evolution-executor.js';
import type { OptimizationSuggestion } from '../../types/evolution.js';

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
      const suggestions: OptimizationSuggestion[] = [
        {
          id: 'sug_002',
          type: 'add_tool',
          priority: 'medium',
          description: '添加技术指标工具',
          reason: '需要更多技术分析能力',
          expectedImpact: '提升技术分析准确性',
          data: {
            name: 'calculate_rsi',
            description: '计算RSI相对强弱指标',
            reason: '补充技术分析工具',
            expectedImpact: '提升超买超卖判断',
          },
        },
      ];

      const result = await executeOptimizationSuggestions(suggestions, TEST_PI_DIR);

      expect(result.applied).toHaveLength(1);
      expect(result.applied[0].status).toBe('success');
      expect(result.applied[0].type).toBe('add_tool');

      const registryPath = path.join(TEST_EVOLUTION_DIR, 'dynamic-tools.json');
      const registryContent = await fs.readFile(registryPath, 'utf-8');
      const registry = JSON.parse(registryContent);

      expect(registry.tools).toHaveLength(1);
      expect(registry.tools[0].name).toBe('calculate_rsi');
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
      const registryPath = path.join(TEST_EVOLUTION_DIR, 'dynamic-tools.json');
      const originalRegistry = {
        tools: [
          {
            name: 'existing_tool',
            description: '现有工具',
            parameters: Type.Object({}),
          },
        ],
      };

      await fs.writeFile(registryPath, JSON.stringify(originalRegistry), 'utf-8');

      const suggestions: OptimizationSuggestion[] = [
        {
          id: 'sug_008',
          type: 'add_tool',
          priority: 'medium',
          description: '添加工具',
          reason: '测试回滚',
          expectedImpact: '无',
          data: {
            name: 'new_tool',
            description: '新工具',
          },
        },
      ];

      const result = await executeOptimizationSuggestions(suggestions, TEST_PI_DIR);
      const rollbackData = result.applied[0].rollbackData;

      await rollbackExecution('sug_008', rollbackData, TEST_PI_DIR);

      const registryContent = await fs.readFile(registryPath, 'utf-8');
      const registry = JSON.parse(registryContent);

      expect(registry.tools).toHaveLength(1);
      expect(registry.tools[0].name).toBe('existing_tool');
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
      const suggestions: OptimizationSuggestion[] = [
        {
          id: 'sug_011',
          type: 'add_tool',
          priority: 'medium',
          description: '测试日志',
          reason: '测试',
          expectedImpact: '无',
          data: {
            name: 'test_tool',
            description: '测试工具',
          },
        },
      ];

      await executeOptimizationSuggestions(suggestions, TEST_PI_DIR);

      const historyPath = path.join(TEST_EVOLUTION_DIR, 'tool-changes.jsonl');
      const historyContent = await fs.readFile(historyPath, 'utf-8');
      const lines = historyContent.trim().split('\n');

      expect(lines.length).toBeGreaterThan(0);

      const lastLog = JSON.parse(lines[lines.length - 1]);
      expect(lastLog.action).toBe('add');
      expect(lastLog.toolName).toBe('test_tool');
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
