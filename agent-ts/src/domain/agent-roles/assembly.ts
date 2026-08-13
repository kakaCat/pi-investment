/**
 * Agent 装配（Assembly）——按 agentKind 装配工具集。
 *
 * fin 等价性铁律：`agentKind: 'fin'` 返回的列表与入参 allTools 逐字节一致
 * （零过滤、零重排）——fin 是现状全集，不因拆分而减配（含 memory_write /
 * evolution_run 等「归属别组」的工具，fin 依然保留，见 A0-T3 决议）。
 *
 * 其余 kind：SHARED_BASE + 对应工具组（EVOLUTION / MEMORY），
 * 结构上排除交易/池等写工具（assembly.test.ts 锁定）。
 */
import type { AgentKind } from './types.js';
import { getProfile } from './profiles.js';
import {
  SHARED_BASE_TOOLS,
  FIN_TOOLS,
  EVOLUTION_TOOLS,
  MEMORY_TOOLS,
} from '../../infrastructure/tools/groups.js';

const GROUP_BY_TOOL_GROUP = {
  FIN: FIN_TOOLS,
  EVOLUTION: EVOLUTION_TOOLS,
  MEMORY: MEMORY_TOOLS,
} as const;

export function selectToolsForKind<T extends { name: string }>(
  kind: AgentKind,
  allTools: readonly T[],
): T[] {
  // fin 等价性铁律：默认（现状）零变化。
  if (kind === 'fin') return [...allTools];

  const group = GROUP_BY_TOOL_GROUP[getProfile(kind).toolGroup];
  const allowed = new Set<string>();
  for (const t of SHARED_BASE_TOOLS) allowed.add(t.name);
  for (const t of group) allowed.add(t.name);

  // 按 allTools 顺序过滤，保留注册表原始对象引用与顺序。
  return allTools.filter((t) => allowed.has(t.name));
}
