import { describe, it, expect } from 'vitest';
import { createAccountInfoTool, createPositionListTool } from '../src/index.js';
import { AgentDHClient } from '@pi-investment/agent-dh-client';

describe('Trading Tools Registration Smoke Test', () => {
  it('should create all 2 trading tools without errors', () => {
    // Create mock client
    const mockClient = new AgentDHClient({
      agentOS: { baseURL: 'http://localhost:8080' },
      quantsysV2: { baseURL: 'http://localhost:5001' },
    });

    // Create all tools
    const accountTool = createAccountInfoTool(mockClient);
    const positionTool = createPositionListTool(mockClient);

    // Verify all tools have correct names and required properties
    expect(accountTool.name).toBe('account_info');
    expect(accountTool.description).toBeTruthy();
    expect(accountTool.execute).toBeInstanceOf(Function);
    expect(accountTool.output).toBeTruthy();
    expect(accountTool.output.schema).toBeTruthy();
    expect(accountTool.output.render).toBeInstanceOf(Function);

    expect(positionTool.name).toBe('position_list');
    expect(positionTool.description).toBeTruthy();
    expect(positionTool.execute).toBeInstanceOf(Function);
  });
});
