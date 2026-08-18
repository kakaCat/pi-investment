import { describe, it, expect, vi, beforeEach } from 'vitest';
import { RegistryClient } from '../src/registry-client.js';
import type { AgentOSClient, AgentInfo } from '../src/types.js';

describe('RegistryClient', () => {
  let mockOSClient: AgentOSClient;
  let registryClient: RegistryClient;

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

    registryClient = new RegistryClient(mockOSClient);
  });

  describe('register', () => {
    it('should register agent successfully', async () => {
      const agentInfo: AgentInfo = {
        agent_id: 'agent-123',
        session_id: 'session-123',
        type: 'worker',
        capabilities: ['data-analysis', 'backtest'],
        status: 'idle',
      };

      await registryClient.register(agentInfo);

      expect(mockOSClient.registry.register).toHaveBeenCalledWith(agentInfo);
      expect(mockOSClient.registry.register).toHaveBeenCalledTimes(1);
    });

    it('should throw error when registration fails', async () => {
      const agentInfo: AgentInfo = {
        agent_id: 'agent-123',
        session_id: 'session-123',
        type: 'worker',
        capabilities: [],
        status: 'idle',
      };

      mockOSClient.registry.register = vi.fn().mockRejectedValue(new Error('Network error'));

      await expect(registryClient.register(agentInfo)).rejects.toThrow('Network error');
    });
  });

  describe('heartbeat', () => {
    it('should send heartbeat successfully', async () => {
      await registryClient.heartbeat('agent-123', 'busy');

      expect(mockOSClient.registry.heartbeat).toHaveBeenCalledWith({
        agent_id: 'agent-123',
        status: 'busy',
        metadata: undefined,
      });
    });

    it('should not throw error when heartbeat fails', async () => {
      mockOSClient.registry.heartbeat = vi.fn().mockRejectedValue(new Error('Network error'));

      await expect(registryClient.heartbeat('agent-123', 'idle')).resolves.toBeUndefined();
    });
  });

  describe('updateStatus', () => {
    it('should update status successfully', async () => {
      await registryClient.updateStatus('agent-123', 'error', 'Task failed');

      expect(mockOSClient.registry.updateStatus).toHaveBeenCalledWith({
        agent_id: 'agent-123',
        status: 'error',
        message: 'Task failed',
      });
    });

    it('should throw error when status update fails', async () => {
      mockOSClient.registry.updateStatus = vi.fn().mockRejectedValue(new Error('Network error'));

      await expect(registryClient.updateStatus('agent-123', 'idle')).rejects.toThrow('Network error');
    });
  });

  describe('unregister', () => {
    it('should unregister agent successfully', async () => {
      await registryClient.unregister('agent-123');

      expect(mockOSClient.registry.unregister).toHaveBeenCalledWith({
        agent_id: 'agent-123',
      });
    });

    it('should not throw error when unregister fails', async () => {
      mockOSClient.registry.unregister = vi.fn().mockRejectedValue(new Error('Network error'));

      await expect(registryClient.unregister('agent-123')).resolves.toBeUndefined();
    });
  });
});
