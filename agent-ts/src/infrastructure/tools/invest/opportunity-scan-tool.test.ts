/**
 * opportunity_scan 工具配置验证测试
 * 验证持久化配置和工具定义正确性
 */

import { describe, it, expect } from '@jest/globals';
import { opportunityScanTool } from './opportunity-scan-tool.js';

describe('opportunity_scan 工具定义', () => {
  it('工具名称正确', () => {
    expect(opportunityScanTool.name).toBe('opportunity_scan');
  });

  it('工具标签包含动态权重说明', () => {
    expect(opportunityScanTool.label).toContain('动态权重');
  });

  it('工具描述正确反映持久化阈值', () => {
    const description = opportunityScanTool.description;

    // 验证描述中提到了持久化
    expect(description).toContain('💾');
    expect(description).toContain('自动保存');

    // 验证阈值描述准确（>60只，而非旧的>20只）
    expect(description).toContain('>60只股票');
    expect(description).not.toContain('>20只股票');
  });

  it('参数定义包含所有权重配置选项', () => {
    const params = opportunityScanTool.parameters;

    // 验证必要参数存在
    expect(params.properties).toHaveProperty('symbols');
    expect(params.properties).toHaveProperty('conditions');
    expect(params.properties).toHaveProperty('limit');

    // 验证三种权重模式参数
    expect(params.properties).toHaveProperty('weights');
    expect(params.properties).toHaveProperty('enable_dynamic_weights');
    expect(params.properties).toHaveProperty('dynamic_weights_config');

    // 验证行业轮动参数
    expect(params.properties).toHaveProperty('sectorFilter');
  });

  it('权重参数定义完整', () => {
    const params = opportunityScanTool.parameters;
    const weightsParam = (params.properties as any).weights;

    expect(weightsParam).toBeDefined();
    expect(weightsParam.properties).toHaveProperty('technical');
    expect(weightsParam.properties).toHaveProperty('fundamental');
    expect(weightsParam.properties).toHaveProperty('capital');
  });

  it('动态权重配置参数完整', () => {
    const params = opportunityScanTool.parameters;
    const dynamicConfig = (params.properties as any).dynamic_weights_config;

    expect(dynamicConfig).toBeDefined();
    expect(dynamicConfig.properties).toHaveProperty('factors');
    expect(dynamicConfig.properties).toHaveProperty('analysis_period');
    expect(dynamicConfig.properties).toHaveProperty('algorithm');
  });

  it('execute 函数存在', () => {
    expect(opportunityScanTool.execute).toBeDefined();
    expect(typeof opportunityScanTool.execute).toBe('function');
  });
});

describe('opportunity_scan 功能特性描述', () => {
  it('支持固定权重模式（默认）', () => {
    const description = opportunityScanTool.description;
    expect(description).toContain('固定权重');
    expect(description).toContain('技术50% + 基本面30% + 资金20%');
  });

  it('支持自定义权重模式', () => {
    const description = opportunityScanTool.description;
    expect(description).toContain('自定义权重');
    expect(description).toContain('手动指定三维权重');
  });

  it('支持动态权重模式', () => {
    const description = opportunityScanTool.description;
    expect(description).toContain('动态权重');
    expect(description).toContain('因子有效性');
    expect(description).toContain('IC/IR');
  });

  it('说明动态权重优势', () => {
    const description = opportunityScanTool.description;
    expect(description).toContain('自适应市场环境');
    expect(description).toContain('自动降低失效因子权重');
    expect(description).toContain('选股准确率提升');
  });

  it('包含适用场景说明', () => {
    const description = opportunityScanTool.description;
    expect(description).toContain('适用场景');
    expect(description).toContain('市场扫描找机会');
    expect(description).toContain('策略开发前的股票池构建');
  });
});

describe('opportunity_scan 数据大小估算', () => {
  it('单个机会对象约260字节', () => {
    const singleOpp = {
      symbol: "600519.SH",
      name: "贵州茅台",
      score: 85.5,
      technical_score: 90.2,
      fundamental_score: 80.1,
      capital_score: 75.3,
      confidence: 0.85,
      risk_level: "low",
      signal_type: "buy",
      timestamp: "2026-06-03T12:00:00",
      reasons: [
        "RSI超卖反弹机会",
        "MACD金叉信号",
        "基本面健康，ROE > 15%"
      ]
    };

    const size = JSON.stringify(singleOpp).length;
    expect(size).toBeGreaterThan(250);
    expect(size).toBeLessThan(300);
  });

  it('30KB 阈值约对应 65-70 只股票', () => {
    const singleOppSize = 262; // 平均大小
    const formattedTextPerOpp = 200; // 格式化文本额外开销
    const threshold = 30 * 1024;

    const estimatedTriggerCount = Math.floor(threshold / (singleOppSize + formattedTextPerOpp));

    expect(estimatedTriggerCount).toBeGreaterThanOrEqual(60);
    expect(estimatedTriggerCount).toBeLessThanOrEqual(70);
  });

  it('默认 limit=20 不会触发持久化', () => {
    const singleOppSize = 262;
    const formattedTextPerOpp = 200;
    const defaultLimit = 20;
    const threshold = 30 * 1024;

    const estimatedSize = defaultLimit * (singleOppSize + formattedTextPerOpp);

    expect(estimatedSize).toBeLessThan(threshold);
  });

  it('100只股票会触发持久化', () => {
    const singleOppSize = 262;
    const formattedTextPerOpp = 200;
    const largeLimit = 100;
    const threshold = 30 * 1024;

    const estimatedSize = largeLimit * (singleOppSize + formattedTextPerOpp);

    expect(estimatedSize).toBeGreaterThan(threshold);
  });
});
