import { describe, it, expect, vi, beforeEach } from 'vitest';
import { InvestmentAgentLoop } from '../src/agent-loop.js';
import type { AgentOSClient } from '../src/types.js';

describe('InvestmentAgentLoop', () => {
  let mockOSClient: AgentOSClient;
  let mockCtx: any;
  let agentLoop: InvestmentAgentLoop;

  beforeEach(() => {
    // Create mock OS client
    mockOSClient = {
      registry: {
        register: vi.fn().mockResolvedValue(undefined),
        heartbeat: vi.fn().mockResolvedValue(undefined),
        updateStatus: vi.fn().mockResolvedValue(undefined),
        unregister: vi.fn().mockResolvedValue(undefined),
      },
    };

    // Create mock Cordis context
    mockCtx = {
      sessions: {
        create: vi.fn().mockResolvedValue({ id: 'session-123' }),
      },
    };

    agentLoop = new InvestmentAgentLoop(mockCtx, {
      osClient: mockOSClient,
      agentType: 'worker',
      capabilities: ['data-analysis', 'backtest'],
    });
  });

  describe('create', () => {
    it('should create agent successfully', async () => {
      const agent = await agentLoop.create('session-123');

      expect(agent).toBeDefined();
      expect(agent.agentId).toBe('agent-session-123');
      expect(agent.sessionId).toBe('session-123');
      expect(mockOSClient.registry.register).toHaveBeenCalled();
      expect(mockOSClient.registry.updateStatus).toHaveBeenCalled();
    });

    it('should create agent with custom options', async () => {
      const agent = await agentLoop.create('session-456', {
        agentId: 'custom-agent',
        type: 'scheduler',
        capabilities: ['scheduling'],
      });

      expect(agent.agentId).toBe('custom-agent');
      expect(mockOSClient.registry.register).toHaveBeenCalledWith(
        expect.objectContaining({
          agent_id: 'custom-agent',
          type: 'scheduler',
          capabilities: ['scheduling'],
        })
      );
    });

    it('should store created agent', async () => {
      const agent = await agentLoop.create('session-789');

      const retrieved = agentLoop.getAgent(agent.agentId);
      expect(retrieved).toBe(agent);
    });
  });

  describe('resume', () => {
    it('should resume agent (currently creates new)', async () => {
      const agent = await agentLoop.resume('session-123');

      expect(agent).toBeDefined();
      expect(mockOSClient.registry.register).toHaveBeenCalled();
    });
  });

  describe('stopAgent', () => {
    it('should stop agent successfully', async () => {
      const agent = await agentLoop.create('session-123');
      
      await agentLoop.stopAgent(agent.agentId);

      expect(mockOSClient.registry.unregister).toHaveBeenCalledWith({
        agent_id: agent.agentId,
      });
      expect(agentLoop.getAgent(agent.agentId)).toBeUndefined();
    });

    it('should handle stopping non-existent agent', async () => {
      await expect(agentLoop.stopAgent('non-existent')).resolves.toBeUndefined();
    });
  });

  describe('stopAll', () => {
    it('should stop all agents', async () => {
      const agent1 = await agentLoop.create('session-1');
      const agent2 = await agentLoop.create('session-2');

      await agentLoop.stopAll();

      expect(agentLoop.getAllAgents()).toHaveLength(0);
      expect(mockOSClient.registry.unregister).toHaveBeenCalledTimes(2);
    });
  });

  describe('getAllAgents', () => {
    it('should return all agents', async () => {
      await agentLoop.create('session-1');
      await agentLoop.create('session-2');

      const agents = agentLoop.getAllAgents();
      expect(agents).toHaveLength(2);
    });
  });
});
