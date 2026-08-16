import { AgentOSClient } from '@pi-investment/agent-os-client';
import { logger } from '../../infrastructure/logging/index.js';
import { findSkillByName, findSkillById } from '../bootstrap/skill-registry.js';

/**
 * Agent OS client instance (set by setAgentOSClient)
 */
let agentOSClient: AgentOSClient | null = null;

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
    // 1. Get skill detail from Agent OS
    const skill = await agentOSClient.skills.get(skillId);

    logger.info(`[SkillExecutor] Loaded skill: ${skill.name} (version: ${skill.version})`);

    // 2. Return the content (caller will use it as system prompt or instructions)
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
