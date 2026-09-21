import { AgentOSClient } from '@pi-investment/agent-os-client';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

/**
 * Configuration for AgentDHClient
 */
export interface AgentDHClientConfig {
  agentOS?: {
    baseURL: string;
    timeout?: number;
  };
  quantsysV2?: {
    baseURL: string;
    timeout?: number;
  };
}

/**
 * Unified client for Agent-DH ecosystem
 * 
 * Provides access to:
 * - Agent OS Registry (agent management, task routing)
 * - QuantsysV2 (trading strategies, backtesting, market data)
 */
export class AgentDHClient {
  public agentOS: AgentOSClient;
  public quantsysV2: QuantsysV2Client;

  constructor(config: AgentDHClientConfig) {
    // Initialize Agent OS client
    this.agentOS = new AgentOSClient({
      baseURL: config.agentOS?.baseURL || 'http://localhost:8080',
      timeout: config.agentOS?.timeout,
    });

    // Initialize QuantsysV2 client
    this.quantsysV2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout,
    });
  }

  /**
   * Create a default client with standard URLs
   */
  static createDefault(): AgentDHClient {
    return new AgentDHClient({
      agentOS: {
        baseURL: process.env.AGENT_OS_BASE_URL || 'http://localhost:8080',
      },
      quantsysV2: {
        baseURL: process.env.QUANTSYS_V2_BASE_URL || 'http://localhost:5001',
      },
    });
  }
}

// Re-export types from sub-clients
export type {
  AgentInfo,
  AgentStatus,
  AgentHeartbeat,
  StatusUpdate,
  Agent,
} from '@pi-investment/agent-os-client';

export type {
  Stock,
  KlineData,
  Strategy,
  BacktestRequest,
  BacktestResult,
  Pool,
  PoolMember,
  Signal,
  FinancialData,
  WatchRule,
  Position,
  PortfolioSummary,
} from '@pi-investment/quantsys-v2-client';
