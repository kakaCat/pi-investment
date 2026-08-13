// types.ts
export type AgentKind = 'fin' | 'evolution' | 'memory';
export type ModelPreference = 'flash' | 'pro' | 'inherit';

export interface RoleProfile {
  kind: AgentKind;
  promptVariant: string;          // 提示词变体标识（A0-T3 使用）
  toolGroup: 'FIN' | 'EVOLUTION' | 'MEMORY';  // 对应 groups.ts 组名；SHARED_BASE 恒有
  modelPreference: ModelPreference;
  memoryWriteScopes: string[];    // 可写的记忆 scope 前缀
}
