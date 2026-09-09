/**
 * FundFlowTool.extractRows 契约测试（2026-09-10 修复专项）
 *
 * 背景：板块资金流全景误报「数据源暂不可用」。后端 /api/market/sector-flow
 * 返回 {success, data:{data_type, data:{records:[...]}}}（三层嵌套），而
 * extractRows 只识别 d.data 数组 / d.records 数组 → 返回 [] → available=false。
 * 修复：增加 d.data.data.records 形态识别。本测试用**真实后端响应形状**锁定契约，
 * 防解析层与线上数据模型再次脱节。
 */

import { describe, it, expect, vi } from 'vitest';
import { FundFlowTool } from '../packages/competition/src/tools/FundFlowTool/FundFlowTool.js';

function makeTool() {
  const mockClient = {} as any;
  const tool = new FundFlowTool(mockClient);
  return { tool, mockClient };
}

// 真实响应形状（2026-09-10 curl /api/market/sector-flow，字段名来自 akshare 中文列）
const realSectorResponse = {
  success: true,
  data: {
    data_type: 'sector_fund_flow',
    data: {
      records: [
        { 序号: 1, 行业: '煤炭开采加工', '行业-涨跌幅': 3.35, 净额: 14.16, 领涨股: '云煤能源' },
        { 序号: 2, 行业: '港口航运', '行业-涨跌幅': 2.88, 净额: 6.17, 领涨股: '南京港' },
        { 序号: 3, 行业: '元件', '行业-涨跌幅': 2.2, 净额: 32.84, 领涨股: '胜业电气' },
      ],
      total: 90,
    },
    source: 'akshare',
    timestamp: '2026-09-10T03:07:53',
  },
};

// 个股资金流形状：data.data 是数组
const realStockFlowResponse = {
  success: true,
  data: {
    symbol: '600519',
    data: [
      { date: '2026-09-09', mainNetInflow: 1234, mainNetInflowRate: 2.5 },
      { date: '2026-09-08', mainNetInflow: -567, mainNetInflowRate: -1.1 },
    ],
  },
};

describe('FundFlowTool.extractRows 契约', () => {
  it('板块资金流：识别 data.data = {records:[...]} 三层嵌套（真实响应形状）', () => {
    const { tool } = makeTool();
    const rows = (tool as any).extractRows(realSectorResponse);
    expect(rows).toHaveLength(3);
    expect(rows[0]['行业']).toBe('煤炭开采加工');
    expect(rows[1]['净额']).toBe(6.17);
    expect(rows[2]['领涨股']).toBe('胜业电气');
  });

  it('个股资金流：data.data 直接是数组', () => {
    const { tool } = makeTool();
    const rows = (tool as any).extractRows(realStockFlowResponse);
    expect(rows).toHaveLength(2);
    expect(rows[0].mainNetInflow).toBe(1234);
  });

  it('data.records 数组形态兼容', () => {
    const { tool } = makeTool();
    const res = { data: { records: [{ a: 1 }, { a: 2 }] } };
    expect((tool as any).extractRows(res)).toHaveLength(2);
  });

  it('res.data 直接是数组形态兼容', () => {
    const { tool } = makeTool();
    const res = { data: [{ a: 1 }] };
    expect((tool as any).extractRows(res)).toHaveLength(1);
  });

  it('空/异常响应返回 []（不抛异常）', () => {
    const { tool } = makeTool();
    expect((tool as any).extractRows({ success: false, error: 'x' })).toHaveLength(0);
    expect((tool as any).extractRows(null)).toHaveLength(0);
    expect((tool as any).extractRows({ data: { data: { noRecords: true } } })).toHaveLength(0);
  });

  it('execute 板块模式：成功响应 → available=true + sector_flow 填充', async () => {
    const { tool, mockClient } = makeTool();
    mockClient.getSectorFlow = vi.fn().mockResolvedValue(realSectorResponse);
    const result = await (tool as any).execute({}, {});
    expect(result.mode).toBe('sector');
    expect(result.available).toBe(true);
    expect(result.sector_flow).toHaveLength(3);
    expect(result.degraded_sources).toBeUndefined();
  });
});
