import { BaseTool, type ToolMetadata, type ValidationResult, type ToolContext, type ToolResponse, ErrorType } from '@pi-investment/core-tool';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import { notificationChannelsPrompt, type NotificationChannelsParams, type NotificationChannelsResult } from './prompt';

export class NotificationChannelsTool extends BaseTool<NotificationChannelsParams, NotificationChannelsResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'notification_channels',
    category: 'notification',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = notificationChannelsPrompt;

  constructor(private aos: AgentOSClient) {
    super();
  }

  protected validate(params: NotificationChannelsParams): ValidationResult {
    const errors: string[] = [];

    if (params.log_limit !== undefined) {
      if (typeof params.log_limit !== 'number') {
        errors.push('log_limit 必须是数字');
      } else if (params.log_limit < 1 || params.log_limit > 100) {
        errors.push('log_limit 必须在 1-100 之间');
      }
    }

    if (errors.length > 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        issue: errors.join('; '),
      };
    }

    return { success: true };
  }

  protected async execute(
    params: NotificationChannelsParams,
    context: ToolContext
  ): Promise<NotificationChannelsResult> {
    const [channelsRes, logsRes] = await Promise.all([
      this.aos.notification.listChannels(),
      this.aos.notification.listLogs(params.log_limit ?? 10),
    ]);

    const channels = channelsRes.channels || [];
    const codeById = new Map(channels.map((c: any) => [c.id, c.code]));

    const maskHook = (hook?: string) =>
      hook ? hook.slice(0, 45) + '...' + hook.slice(-6) : null;

    const logs = (logsRes.logs || []).map((l: any) => ({
      title: l.title ?? null,
      status: l.status ?? null,
      channel: codeById.get(l.channel_id) ?? l.channel_id ?? null,
      created_at: l.created_at ?? null,
    }));

    const statusSummary: Record<string, number> = {};
    for (const l of logs) {
      const st = l.status ?? 'unknown';
      statusSummary[st] = (statusSummary[st] ?? 0) + 1;
    }

    return {
      channels: channels.map((c: any) => ({
        code: c.code,
        name: c.name ?? null,
        enabled: c.enabled !== false,
        webhook: maskHook(c.config?.webhook),
      })),
      recent_logs: logs,
      status_summary: statusSummary,
    };
  }

  protected wrap(data: NotificationChannelsResult, context: ToolContext): ToolResponse<NotificationChannelsResult> {
    return {
      success: true,
      data,
    };
  }
}
