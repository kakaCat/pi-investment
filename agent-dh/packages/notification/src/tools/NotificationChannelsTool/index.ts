import { defineTool } from '@deepseek-ai/dsh-tools';
import { NotificationChannelsTool } from './NotificationChannelsTool';
import { AgentOSClient } from '@pi-investment/agent-os-client';

export { NotificationChannelsTool } from './NotificationChannelsTool';
export { notificationChannelsPrompt, type NotificationChannelsParams, type NotificationChannelsResult } from './prompt';

export function createNotificationChannelsTool(aos: AgentOSClient) {
  const tool = new NotificationChannelsTool(aos);
  return defineTool(tool.toDSHToolDefinition());
}
