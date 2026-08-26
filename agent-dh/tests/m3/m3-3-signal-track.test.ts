/**
 * M3-3 信号质量追踪单元测试（RFC 010，2026-08-26）
 *
 * 测试 signal_track 工具的 schema 和注册逻辑。
 * 集成测试（依赖 quantsys-v2 后端）留到手动验证。
 */

import { describe, it, expect, beforeAll } from 'vitest';
import IntelligencePlugin from '../../packages/intelligence/src/index.js';

describe('M3-3 信号质量追踪', () => {
  let signalTrackTool: any;

  beforeAll(async () => {
    // 创建 stub 上下文（参考 plugin-schema.smoke.test.ts）
    const ctx = {
      tools: {
        register: (tool: any) => {
          if (tool.name === 'signal_track') {
            signalTrackTool = tool;
          }
          return () => true;
        },
        list: () => [],
      },
      on: () => () => true,
      reflect: { provide: () => {} },
      logger: { info() {}, warn() {}, error() {}, debug() {} },
    } as any;

    // 实例化插件（会注册 signal_track 工具）
    new IntelligencePlugin(ctx, {
      quantsysV2: { baseURL: 'http://localhost:5001' },
    });

    // 等待插件初始化
    await new Promise(resolve => setTimeout(resolve, 50));
  });

  it('signal_track 工具已注册', () => {
    expect(signalTrackTool).toBeDefined();
    expect(signalTrackTool.name).toBe('signal_track');
  });

  it('schema 完整：parameters 有 action/symbol/price/source/grade', () => {
    // 先确认工具已注册
    expect(signalTrackTool, 'signal_track 工具未注册').toBeDefined();
    
    // dsh-tools rc7 的 defineTool：parameters 是 JSON Schema object，字段在 properties 下
    const params = signalTrackTool.parameters?.properties || {};
    const required = signalTrackTool.parameters?.required || [];
    
    expect(params.action).toBeDefined();
    expect(params.action.enum).toEqual(['record', 'update', 'report']);
    expect(required).toContain('action');
    
    expect(params.symbol).toBeDefined();
    expect(params.price).toBeDefined();
    expect(params.source).toBeDefined();
    expect(params.grade).toBeDefined();
    expect(params.grade.enum).toEqual(['A', 'B', 'C']);
    expect(params.reason).toBeDefined();
  });

  it('output schema 合法（有 additionalProperties）', () => {
    const outputSchema = signalTrackTool.output?.schema || {};
    expect(outputSchema.type).toBe('object');
    expect(outputSchema.additionalProperties).toBe(true);
    expect(outputSchema.properties?.action).toBeDefined();
    expect(outputSchema.properties?.result).toBeDefined();
    expect(outputSchema.properties?.details).toBeDefined();
    expect(outputSchema.properties?.details.additionalProperties).toBe(true);
  });

  it('timeoutMs 设置为 30000（回填 K 线可能较慢）', () => {
    expect(signalTrackTool.timeoutMs).toBe(30000);
  });

  it('description 包含关键词：追踪/record/update/report', () => {
    const desc = signalTrackTool.description;
    expect(desc).toContain('追踪');
    expect(desc).toContain('record');
    expect(desc).toContain('update');
    expect(desc).toContain('report');
  });
});
