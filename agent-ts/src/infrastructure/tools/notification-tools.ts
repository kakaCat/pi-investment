/**
 * Notification Tools - Agent 通知工具
 *
 * 让 Agent 能够通过 Agent OS 的通知系统发送消息
 */

export interface NotificationSendArgs {
  channel: string;
  title: string;
  content: string;
  color?: 'blue' | 'green' | 'red' | 'orange' | 'grey' | 'purple';
  urgency?: 'low' | 'normal' | 'high' | 'critical';
}

export const notificationSendTool = {
  name: 'notification_send',
  description: `发送通知消息到指定渠道。你应该先生成好消息内容，然后调用此工具发送。

可用渠道：
- trading: 交易群（交易信号、执行确认、盘前/盘后报告）
- alerts: 告警群（风险预警、系统异常、紧急告警）
- reports: 报告群（日报、周报、月报）

使用场景：
- 盘前准备报告 → trading
- 交易信号触发 → alerts
- 每日总结报告 → reports
- 风险预警 → alerts

注意：
1. 内容使用 Markdown 格式
2. 根据重要程度选择合适的颜色
3. 标题简短有力（<50 字）
4. 内容清晰易读（<500 字为佳）`,

  inputSchema: {
    type: 'object',
    properties: {
      channel: {
        type: 'string',
        enum: ['trading', 'alerts', 'reports'],
        description: '渠道代码'
      },
      title: {
        type: 'string',
        description: '消息标题（简短有力）'
      },
      content: {
        type: 'string',
        description: '消息内容（支持 Markdown 格式）'
      },
      color: {
        type: 'string',
        enum: ['blue', 'green', 'red', 'orange', 'grey', 'purple'],
        description: '卡片颜色（blue=信息，green=成功，red=告警，orange=警告）'
      }
    },
    required: ['channel', 'title', 'content']
  },

  async execute(args: NotificationSendArgs): Promise<string> {
    // 直接调用 Agent OS CLI
    return await executeCLI(args);
  }
};

export const notificationListChannelsTool = {
  name: 'notification_list_channels',
  description: '查询可用的通知渠道列表及其状态',

  inputSchema: {
    type: 'object',
    properties: {},
    required: []
  },

  async execute(): Promise<string> {
    // 直接调用 Agent OS CLI
    return await executeCLIList();
  }
};

// Fallback: 直接调用 CLI（当 API 不可用时）
async function executeCLI(args: NotificationSendArgs): Promise<string> {
  const { exec } = await import('child_process');
  const { promisify } = await import('util');
  const execAsync = promisify(exec);

  // Agent OS 路径（从环境变量或默认路径）
  const agentOsBin = process.env.AGENT_OS_BIN || '../../agent-os/agent-os';

  const cmd = [
    agentOsBin,
    'notify send',
    `--channel ${args.channel}`,
    `--title "${args.title.replace(/"/g, '\\"')}"`,
    `--content "${args.content.replace(/"/g, '\\"')}"`,
    args.color ? `--color ${args.color}` : ''
  ].filter(Boolean).join(' ');

  try {
    const { stdout, stderr } = await execAsync(cmd, {
      env: { ...process.env, PGDATABASE: process.env.PGDATABASE || 'quant_investment' },
      cwd: process.cwd()
    });

    if (stderr && stderr.includes('Failed')) {
      return `❌ 发送失败: ${stderr}`;
    }

    // 解析 log ID
    const logIdMatch = stdout.match(/Log ID: ([a-f0-9-]+)/);
    const logId = logIdMatch ? logIdMatch[1] : '';

    return `✅ 通知已发送到 ${args.channel} 群${logId ? `\n日志ID: ${logId}` : ''}`;
  } catch (error: any) {
    return `❌ 发送失败: ${error.message}`;
  }
}

async function executeCLIList(): Promise<string> {
  const { exec } = await import('child_process');
  const { promisify } = await import('util');
  const execAsync = promisify(exec);

  const agentOsBin = process.env.AGENT_OS_BIN || '../../agent-os/agent-os';

  try {
    const { stdout } = await execAsync(`${agentOsBin} notify list`, {
      env: { ...process.env, PGDATABASE: process.env.PGDATABASE || 'quant_investment' },
      cwd: process.cwd()
    });

    return `可用渠道：\n\`\`\`\n${stdout}\n\`\`\``;
  } catch (error: any) {
    return `❌ 查询失败: ${error.message}`;
  }
}

// 导出所有工具
export const notificationTools = [
  notificationSendTool,
  notificationListChannelsTool
];
