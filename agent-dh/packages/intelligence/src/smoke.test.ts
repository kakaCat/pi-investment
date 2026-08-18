import { describe, it, expect } from 'vitest';
import { createEvolutionStatusTool, createWatchListTool } from '../src/index.js';
import { AgentDHClient } from '@pi-investment/agent-dh-client';

describe('Intelligence Tools Registration Smoke Test', () => {
  it('should create all 2 intelligence tools without errors', () => {
    // Create mock client
    const mockClient = new AgentDHClient({
      agentOS: { baseURL: 'http://localhost:8080' },
      quantsysV2: { baseURL: 'http://localhost:5001' },
    });

    // Create all tools
    const evolutionTool = createEvolutionStatusTool(mockClient);
    const watchListTool = createWatchListTool(mockClient);

    // Verify all tools have correct names and required properties
    expect(evolutionTool.name).toBe('evolution_status');
    expect(evolutionTool.description).toBeTruthy();
    expect(evolutionTool.execute).toBeInstanceOf(Function);
    expect(evolutionTool.output).toBeTruthy();
    expect(evolutionTool.output.schema).toBeTruthy();
    expect(evolutionTool.output.render).toBeInstanceOf(Function);

    expect(watchListTool.name).toBe('watch_list');
    expect(watchListTool.description).toBeTruthy();
    expect(watchListTool.execute).toBeInstanceOf(Function);
  });
});
