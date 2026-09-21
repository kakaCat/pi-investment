import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { ManipulationDetectTool } from './ManipulationDetectTool';

export * from './ManipulationDetectTool';
export * from './prompt';

/**
 * Create Manipulation Detection Tool
 */
export function createManipulationDetectTool(qv2: QuantsysV2Client) {
  const tool = new ManipulationDetectTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}
