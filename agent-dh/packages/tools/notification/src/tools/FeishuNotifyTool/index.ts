import { defineTool } from '@deepseek-ai/dsh-tools';
import { FeishuNotifyTool } from './FeishuNotifyTool';
import { AgentOSClient } from '@pi-investment/agent-os-client';

export { FeishuNotifyTool } from './FeishuNotifyTool';
export { feishuNotifyPrompt, type FeishuNotifyParams, type FeishuNotifyResult } from './prompt';

export function createFeishuNotifyTool(
  aos: AgentOSClient,
  agentSign: string,
  feishuWebhooks: Record<string, string>,
  aosBaseURL: string
) {
  const tool = new FeishuNotifyTool(aos, agentSign, feishuWebhooks, aosBaseURL);
  return defineTool(tool.toDSHToolDefinition());
}
