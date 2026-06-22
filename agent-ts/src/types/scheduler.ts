/**
 * Scheduler types for cron tasks
 */

/**
 * Cron task context - passed to task handlers
 */
export interface CronTaskContext {
  logger: any;  // Logger instance
  toolRegistry: any;  // ToolRegistry instance
  [key: string]: any;
}

/**
 * Cron task definition
 */
export interface CronTask {
  name: string;
  cron: string;
  description: string;
  enabled: boolean;
  handler: (context: CronTaskContext) => Promise<void>;
}
