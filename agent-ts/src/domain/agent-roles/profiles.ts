// profiles.ts
import type { AgentKind, RoleProfile } from './types.js';

export const ROLE_PROFILES: Record<AgentKind, RoleProfile> = {
  fin: {
    kind: 'fin',
    promptVariant: 'fin',
    toolGroup: 'FIN',
    modelPreference: 'inherit',
    memoryWriteScopes: ['daily', 'experience', 'watch', 'portfolio', 'global'],
  },
  evolution: {
    kind: 'evolution',
    promptVariant: 'evolution',
    toolGroup: 'EVOLUTION',
    modelPreference: 'pro',
    memoryWriteScopes: ['evolution'],
  },
  memory: {
    kind: 'memory',
    promptVariant: 'memory',
    toolGroup: 'MEMORY',
    modelPreference: 'flash',
    memoryWriteScopes: ['memory', 'recall-audit'],
  },
};

export function getProfile(kind: AgentKind): RoleProfile {
  const p = ROLE_PROFILES[kind];
  if (!p) throw new Error(`unknown agent kind: ${kind}`);
  return p;
}
