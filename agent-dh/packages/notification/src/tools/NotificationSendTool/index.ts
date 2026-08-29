import { defineTool } from '@deepseek-ai/dsh-tools';
import { NotificationSendTool } from './NotificationSendTool';
import { AgentOSClient } from '@pi-investment/agent-os-client';

export { NotificationSendTool } from './NotificationSendTool';
export { notificationSendPrompt, type NotificationSendParams, type NotificationSendResult } from './prompt';

export function createNotificationSendTool(
  aos: AgentOSClient,
  agentSign: string,
  feishuWebhooks: Record<string, string>,
  aosBaseURL: string
) {
  const tool = new NotificationSendTool(aos, agentSign, feishuWebhooks, aosBaseURL);
  return defineTool(tool.toDSHToolDefinition());
}
