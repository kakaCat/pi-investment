import { AgentOSClient } from '@pi-investment/agent-os-client';
import { logger } from '../../infrastructure/logging/index.js';
import { findSkillByName, findSkillById } from '../bootstrap/skill-registry.js';

/**
 * Agent OS client instance (set by setAgentOSClient)
 */
let agentOSClient: AgentOSClient | null = null;

/**
 * Simple LRU cache for skill content
 */
interface CacheEntry {
  content: string;
  timestamp: number;
}

const skillContentCache = new Map<string, CacheEntry>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes
const MAX_CACHE_SIZE = 50;

/**
 * Get cached skill content if still valid
 */
function getCachedContent(skillId: string): string | null {
  const entry = skillContentCache.get(skillId);
  if (!entry) return null;

  const age = Date.now() - entry.timestamp;
  if (age > CACHE_TTL) {
    skillContentCache.delete(skillId);
    return null;
  }

  return entry.content;
}

/**
 * Cache skill content with LRU eviction
 */
function cacheContent(skillId: string, content: string): void {
  // LRU eviction: remove oldest if cache is full
  if (skillContentCache.size >= MAX_CACHE_SIZE) {
    const firstKey = skillContentCache.keys().next().value;
    if (firstKey) skillContentCache.delete(firstKey);
  }

  skillContentCache.set(skillId, {
    content,
    timestamp: Date.now(),
  });
}

/**
 * Clear the skill content cache (useful after updates)
 */
export function clearSkillCache(): void {
  skillContentCache.clear();
  logger.info('[SkillExecutor] Cache cleared');
}

/**
 * Set the Agent OS client (called from bootstrap)
 */
export function setAgentOSClientForExecutor(client: AgentOSClient): void {
  agentOSClient = client;
}

/**
 * Execute skill by ID
 */
export async function executeSkillById(skillId: string, context?: any): Promise<string> {
  logger.info(`[SkillExecutor] Executing skill by ID: ${skillId}`);

  if (!agentOSClient) {
    throw new Error('Agent OS client not initialized');
  }

  try {
    // Check cache first
    const cached = getCachedContent(skillId);
    if (cached) {
      logger.info(`[SkillExecutor] Cache hit for skill: ${skillId}`);
      return cached;
    }

    // 1. Get skill detail from Agent OS
    const skill = await agentOSClient.skills.get(skillId);

    logger.info(`[SkillExecutor] Loaded skill: ${skill.name} (version: ${skill.version})`);

    // 2. Cache the content
    cacheContent(skillId, skill.content);

    // 3. Return the content (caller will use it as system prompt or instructions)
    return skill.content;
  } catch (error: any) {
    logger.error(`[SkillExecutor] ❌ Failed to load skill: ${skillId}`, error.message);
    throw error;
  }
}

/**
 * Execute skill by name (convenience method)
 */
export async function executeSkillByName(skillName: string, context?: any): Promise<string> {
  logger.info(`[SkillExecutor] Executing skill by name: ${skillName}`);

  const metadata = findSkillByName(skillName);
  if (!metadata) {
    throw new Error(`Skill not found: ${skillName}`);
  }

  return executeSkillById(metadata.id, context);
}

/**
 * Get skill content (alias for executeSkillById)
 */
export async function getSkillContent(skillId: string): Promise<string> {
  return executeSkillById(skillId);
}

/**
 * Get skill content by name
 */
export async function getSkillContentByName(skillName: string): Promise<string> {
  return executeSkillByName(skillName);
}
