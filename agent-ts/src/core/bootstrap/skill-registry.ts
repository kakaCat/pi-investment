import { AgentOSClient, SkillMetadata } from '@pi-investment/agent-os-client';
import { logger } from '../../infrastructure/logging/index.js';
import fs from 'fs';
import path from 'path';

/**
 * In-memory skill registry (metadata only)
 */
let skillRegistry: SkillMetadata[] = [];

/**
 * Agent OS client instance (set by setAgentOSClient)
 */
let agentOSClient: AgentOSClient | null = null;

/**
 * Set the Agent OS client (called from bootstrap)
 */
export function setAgentOSClient(client: AgentOSClient): void {
  agentOSClient = client;
}

/**
 * Load skill registry from Agent OS
 */
export async function loadSkillRegistry(): Promise<void> {
  logger.info('[SkillRegistry] Loading skills from Agent OS...');

  if (!agentOSClient) {
    logger.error('[SkillRegistry] Agent OS client not initialized');
    await loadSkillsFromLocalFiles();
    return;
  }

  try {
    skillRegistry = await agentOSClient.skills.list({
      owner: 'fin-agent',
      status: 'active',
    });

    logger.info(`[SkillRegistry] ✅ Loaded ${skillRegistry.length} skills`);

    // Log all skills for debugging
    skillRegistry.forEach(skill => {
      const schedule = skill.metadata?.schedule;
      logger.info(`  - ${skill.name}: ${skill.description}${schedule ? ` (${schedule})` : ''}`);
    });
  } catch (error: any) {
    logger.error('[SkillRegistry] ❌ Failed to load skills from Agent OS:', error.message);

    // Fallback to local files
    logger.warn('[SkillRegistry] Falling back to local files...');
    await loadSkillsFromLocalFiles();
  }
}

/**
 * Get skill registry
 */
export function getSkillRegistry(): SkillMetadata[] {
  return skillRegistry;
}

/**
 * Find skill by name
 */
export function findSkillByName(name: string): SkillMetadata | undefined {
  return skillRegistry.find(s => s.name === name);
}

/**
 * Find skill by ID
 */
export function findSkillById(id: string): SkillMetadata | undefined {
  return skillRegistry.find(s => s.id === id);
}

/**
 * Search skills (fuzzy search by name or description)
 */
export function searchSkills(query: string): SkillMetadata[] {
  const lowerQuery = query.toLowerCase();
  return skillRegistry.filter(
    s =>
      s.name.toLowerCase().includes(lowerQuery) ||
      s.description.toLowerCase().includes(lowerQuery)
  );
}

/**
 * Fallback: load skills from local files
 *
 * This provides backward compatibility if Agent OS is unavailable.
 */
async function loadSkillsFromLocalFiles(): Promise<void> {
  try {
    const skillsDir = path.join(process.cwd(), 'skills');

    if (!fs.existsSync(skillsDir)) {
      logger.warn('[SkillRegistry] Local skills directory not found');
      skillRegistry = [];
      return;
    }

    const files = fs.readdirSync(skillsDir).filter(f => f.endsWith('.md'));

    skillRegistry = files.map((file, index) => {
      const name = path.basename(file, '.md');
      const content = fs.readFileSync(path.join(skillsDir, file), 'utf-8');

      // Parse frontmatter for description
      const descMatch = content.match(/description:\s*"([^"]+)"/);
      const description = descMatch ? descMatch[1] : `Skill: ${name}`;

      return {
        id: `local-${index}`,
        name,
        description,
        category: 'general',
        owner: 'fin-agent',
        status: 'active',
        metadata: { source: 'local-file', file },
      };
    });

    logger.info(`[SkillRegistry] ✅ Loaded ${skillRegistry.length} skills from local files`);
  } catch (error: any) {
    logger.error('[SkillRegistry] Failed to load local files:', error.message);
    skillRegistry = [];
  }
}
