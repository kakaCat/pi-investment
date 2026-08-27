import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { AgentOSClient } from '@pi-investment/agent-os-client';

export interface Config {
  agentOS: {
    baseURL: string;
  };
}

/**
 * Window Manager Plugin
 * 
 * 提供窗口管理工具：创建、列出、更新、删除测试窗口
 * 用于测试和演示多窗口协作功能
 */
export default class WindowManagerPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    agentOS: z.object({
      baseURL: z.string().default('http://localhost:8080'),
    }).default({} as any),
  }).default({} as any);

  private aos: any;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'window-manager');
    this.aos = new AgentOSClient({
      baseURL: config.agentOS?.baseURL || 'http://localhost:8080',
    });
    this.registerTools();
  }

  private registerTools() {
    const ctx = this.ctx;

    // 工具 1: 创建测试窗口
    ctx.tools.register(defineTool({
      name: 'window_create',
      description: '创建测试窗口（仅注册表层面，用于演示和测试）。参数：窗口名称、角色、能力列表。返回：窗口ID和注册信息。',
      parameters: {
        name: {
          type: 'string',
          description: '窗口名称，如 "白酒板块监控" 或 "今天股市分析"',
          required: true,
        },
        role: {
          type: 'string',
          description: '窗口角色',
          enum: ['investor', 'researcher', 'trader', 'monitor', 'analyst'],
          default: 'investor',
        },
        capabilities: {
          type: 'array',
          items: { type: 'string' },
          description: '窗口能力列表，如 ["trading", "analysis"]',
          default: [],
        },
        status: {
          type: 'string',
          description: '初始状态',
          enum: ['idle', 'active'],
          default: 'idle',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean' },
            window: { type: 'string', description: '窗口ID' },
            name: { type: 'string' },
            message: { type: 'string' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => {
          if (value.success) {
            return [{ 
              type: 'text', 
              text: `✅ 测试窗口已创建\n\n- **窗口ID**: ${value.window}\n- **名称**: ${value.name}\n- **角色**: ${value.role}\n- **状态**: ${value.status}\n\n⚠️  这是测试窗口，仅存在于注册表中，无法接收真实消息或执行任务。` 
            }];
          } else {
            return [{ type: 'text', text: `❌ 创建失败: ${value.message}` }];
          }
        },
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        try {
          const windowId = `w-test-${Date.now()}`;
          const response = await this.aos.post('/api/v1/registry/agents/register', {
            agent_id: windowId,
            type: args.role || 'investor',
            name: args.name,
            instance: 'investment',
            session_id: `session-${windowId}`,
            status: args.status || 'idle',
            host: '127.0.0.1',
            port: 13080,
            pid: process.pid,
            capabilities: args.capabilities || [],
            metadata: {
              test_window: true,
              created_by: 'window_create_tool',
              created_at: new Date().toISOString(),
            },
          });

          return {
            success: true,
            window: windowId,
            name: args.name,
            role: args.role || 'investor',
            status: args.status || 'idle',
            message: '测试窗口已创建',
          } as any;
        } catch (err: any) {
          return {
            success: false,
            message: err?.message || String(err),
          } as any;
        }
      },
    } as any));

    // 工具 2: 删除测试窗口
    ctx.tools.register(defineTool({
      name: 'window_delete',
      description: '删除测试窗口（注销）。参数：窗口ID。仅能删除通过 window_create 创建的测试窗口。',
      parameters: {
        window: {
          type: 'string',
          description: '窗口ID，如 w-test-1234567890',
          required: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean' },
            message: { type: 'string' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{ 
          type: 'text', 
          text: value.success ? `✅ 窗口已删除` : `❌ 删除失败: ${value.message}` 
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        try {
          // 先检查是否是测试窗口
          const agent = await this.aos.get(`/api/v1/registry/agents/${args.window}`);
          if (!agent?.metadata?.test_window) {
            return {
              success: false,
              message: '只能删除测试窗口（通过 window_create 创建的）',
            } as any;
          }

          await this.aos.post('/api/v1/registry/agents/unregister', {
            agent_id: args.window,
          });

          return {
            success: true,
            message: '窗口已删除',
          } as any;
        } catch (err: any) {
          return {
            success: false,
            message: err?.message || String(err),
          } as any;
        }
      },
    } as any));

    // 工具 3: 批量创建测试窗口
    ctx.tools.register(defineTool({
      name: 'window_create_batch',
      description: '批量创建测试窗口场景。参数：场景类型（trading/research/monitoring）。用于快速搭建测试环境。',
      parameters: {
        scenario: {
          type: 'string',
          description: '场景类型',
          enum: ['trading', 'research', 'monitoring', 'mixed'],
          required: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean' },
            windows: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  window: { type: 'string' },
                  name: { type: 'string' },
                  role: { type: 'string' },
                },
                additionalProperties: true,
              },
            },
            count: { type: 'number' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => {
          if (value.success) {
            const lines = [
              `✅ 已创建 ${value.count} 个测试窗口\n`,
              ...value.windows.map((w: any) => 
                `- **${w.window}**: ${w.name} (${w.role})`
              ),
            ];
            return [{ type: 'text', text: lines.join('\n') }];
          } else {
            return [{ type: 'text', text: `❌ 批量创建失败: ${value.message}` }];
          }
        },
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        try {
          const scenarios: Record<string, Array<{name: string, role: string, capabilities: string[]}>> = {
            trading: [
              { name: '交易执行窗口', role: 'trader', capabilities: ['execution', 'order-management'] },
              { name: '风险控制窗口', role: 'analyst', capabilities: ['risk-management'] },
              { name: '投资决策窗口', role: 'investor', capabilities: ['trading', 'analysis'] },
            ],
            research: [
              { name: '白酒板块研究', role: 'researcher', capabilities: ['research', 'backtesting'] },
              { name: '科技股研究', role: 'researcher', capabilities: ['research', 'sector-analysis'] },
              { name: '市场情绪分析', role: 'analyst', capabilities: ['sentiment-analysis'] },
            ],
            monitoring: [
              { name: '白酒板块监控', role: 'monitor', capabilities: ['market-monitoring', 'alert'] },
              { name: '大盘指数监控', role: 'monitor', capabilities: ['market-monitoring', 'alert'] },
              { name: '北向资金监控', role: 'monitor', capabilities: ['flow-monitoring', 'alert'] },
            ],
            mixed: [
              { name: '今天股市分析', role: 'investor', capabilities: ['trading', 'analysis'] },
              { name: '贵州茅台研究', role: 'researcher', capabilities: ['research'] },
              { name: '白酒板块监控', role: 'monitor', capabilities: ['monitoring', 'alert'] },
              { name: '订单执行', role: 'trader', capabilities: ['execution'] },
            ],
          };

          const template = scenarios[args.scenario];
          if (!template) {
            return {
              success: false,
              message: `未知场景: ${args.scenario}`,
            } as any;
          }

          const windows = [];
          for (const spec of template) {
            const windowId = `w-test-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
            await this.aos.post('/api/v1/registry/agents/register', {
              agent_id: windowId,
              type: spec.role,
              name: spec.name,
              instance: 'investment',
              session_id: `session-${windowId}`,
              status: 'idle',
              host: '127.0.0.1',
              port: 13080,
              pid: process.pid,
              capabilities: spec.capabilities,
              metadata: {
                test_window: true,
                scenario: args.scenario,
                created_by: 'window_create_batch_tool',
                created_at: new Date().toISOString(),
              },
            });

            windows.push({
              window: windowId,
              name: spec.name,
              role: spec.role,
            });

            // 避免ID冲突
            await new Promise(resolve => setTimeout(resolve, 10));
          }

          return {
            success: true,
            windows,
            count: windows.length,
          } as any;
        } catch (err: any) {
          return {
            success: false,
            message: err?.message || String(err),
          } as any;
        }
      },
    } as any));

    // 工具 4: 清理所有测试窗口
    ctx.tools.register(defineTool({
      name: 'window_cleanup',
      description: '清理所有测试窗口（删除所有通过 window_create 创建的窗口）。用于测试结束后的清理工作。',
      parameters: {},
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean' },
            deleted: { type: 'number', description: '删除的窗口数' },
            windows: {
              type: 'array',
              items: { type: 'string' },
              description: '已删除的窗口ID列表',
            },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{ 
          type: 'text', 
          text: value.success 
            ? `✅ 已清理 ${value.deleted} 个测试窗口\n\n${value.windows.map((w: string) => `- ${w}`).join('\n')}` 
            : `❌ 清理失败: ${value.message}` 
        }],
      },
      timeoutMs: 30000,
      execute: async () => {
        try {
          const agents = await this.aos.get('/api/v1/registry/agents/available');
          const testWindows = agents.filter((a: any) => a.metadata?.test_window);

          const deleted = [];
          for (const agent of testWindows) {
            await this.aos.post('/api/v1/registry/agents/unregister', {
              agent_id: agent.agent_id,
            });
            deleted.push(agent.agent_id);
          }

          return {
            success: true,
            deleted: deleted.length,
            windows: deleted,
          } as any;
        } catch (err: any) {
          return {
            success: false,
            message: err?.message || String(err),
            deleted: 0,
            windows: [],
          } as any;
        }
      },
    } as any));
  }
}
