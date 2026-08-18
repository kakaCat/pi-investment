import { describe, it, expect } from 'vitest';
import { createQuoteTool, createKlineTool, createFinancialTool, createPoolListTool, createStrategyListTool } from '../src/index.js';
import { AgentDHClient } from '@pi-investment/agent-dh-client';

describe('Investment Tools Registration Smoke Test', () => {
  it('should create all 5 investment tools without errors', () => {
    // Create mock client
    const mockClient = new AgentDHClient({
      agentOS: { baseURL: 'http://localhost:8080' },
      quantsysV2: { baseURL: 'http://localhost:5001' },
    });

    // Create all tools
    const quoteTool = createQuoteTool(mockClient);
    const klineTool = createKlineTool(mockClient);
    const financialTool = createFinancialTool(mockClient);
    const poolListTool = createPoolListTool(mockClient);
    const strategyListTool = createStrategyListTool(mockClient);

    // Verify all tools have correct names and required properties
    expect(quoteTool.name).toBe('data_fetch_quote');
    expect(quoteTool.description).toBeTruthy();
    expect(quoteTool.execute).toBeInstanceOf(Function);
    expect(quoteTool.output).toBeTruthy();
    expect(quoteTool.output.schema).toBeTruthy();
    expect(quoteTool.output.render).toBeInstanceOf(Function);

    expect(klineTool.name).toBe('data_fetch_kline');
    expect(klineTool.description).toBeTruthy();
    expect(klineTool.execute).toBeInstanceOf(Function);

    expect(financialTool.name).toBe('data_fetch_financial');
    expect(financialTool.description).toBeTruthy();
    expect(financialTool.execute).toBeInstanceOf(Function);

    expect(poolListTool.name).toBe('pool_list');
    expect(poolListTool.description).toBeTruthy();
    expect(poolListTool.execute).toBeInstanceOf(Function);

    expect(strategyListTool.name).toBe('strategy_list');
    expect(strategyListTool.description).toBeTruthy();
    expect(strategyListTool.execute).toBeInstanceOf(Function);
  });
});
