/**
 * Canonical Session Key — 全局唯一会话寻址
 * 格式: agent:{agentId}:{channel}:{peerId}
 * 参考 OpenClaw canonical session key 设计
 */
export type ChannelName = 'feishu' | 'wake' | 'cli';

export function buildSessionKey(channel: ChannelName, peerId: string, agentId = 'main'): string {
  const safePeer = peerId.replace(/[^A-Za-z0-9_-]/g, '_');
  return `agent:${agentId}:${channel}:${safePeer}`;
}

export function parseSessionKey(key: string): { agentId: string; channel: string; peerId: string } {
  const parts = key.split(':');
  if (parts.length !== 4 || parts[0] !== 'agent') {
    throw new Error(`Invalid session key: ${key}`);
  }
  return { agentId: parts[1], channel: parts[2], peerId: parts[3] };
}
