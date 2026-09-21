/**
 * ExperienceStatsTool - 经验库胜率统计
 */

import { defineTool } from '@deepseek-ai/dsh-tools';
import { ExperienceStatsTool } from './ExperienceStatsTool';

export { experienceStatsPrompt } from './prompt';
export type { ExperienceStatsParams } from './prompt';
export { ExperienceStatsTool } from './ExperienceStatsTool';

export function createExperienceStatsTool(agentOsBaseURL: string = 'http://localhost:8080') {
  const tool = new ExperienceStatsTool(agentOsBaseURL);
  return defineTool(tool.toDSHToolDefinition() as any);
}
