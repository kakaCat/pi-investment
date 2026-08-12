/**
 * FileBasedSchedulerStore
 *
 * Persists scheduler task definitions to `.pi-invest/scheduler/jobs.json`.
 *
 * **Why file-based instead of PostgreSQL?**
 *
 * 1. **No direct PG connection in agent-ts**: The agent does not and should not
 *    directly connect to PostgreSQL. All data persistence goes through the
 *    quantsys-v2 HTTP API.
 *
 * 2. **Avoid startup dependency**: Storing task definitions via v2 API would
 *    mean the agent cannot start its scheduler without a working v2 backend.
 *    This creates a circular dependency for system bootstrapping.
 *
 * 3. **Task definitions are configuration**: Unlike execution history (which
 *    goes to PG via v2 API), task definitions are relatively static configuration
 *    that should survive backend restarts and be version-controllable.
 *
 * 4. **Atomic writes**: File writes with tmp+rename pattern provide atomic
 *    persistence without needing distributed transaction coordination.
 *
 * This design is inspired by OpenClaw's isolated-agent scheduler persistence
 * pattern, adapted for the PI Investment architecture.
 */

import fs from 'node:fs';
import path from 'node:path';
import type { SchedulerStore, SchedulerTask, SchedulerRun } from './scheduler-service.js';

export interface FileBasedSchedulerStoreOptions {
  /**
   * Root directory for PI Investment data (defaults to ~/.pi-invest)
   */
  dataDir?: string;
}

export class FileBasedSchedulerStore implements SchedulerStore {
  private readonly jobsFilePath: string;
  private tasks = new Map<string, SchedulerTask>();
  private runs = new Map<string, SchedulerRun>();

  constructor(options: FileBasedSchedulerStoreOptions = {}) {
    const dataDir = options.dataDir ?? path.join(process.env.HOME ?? '/tmp', '.pi-invest');
    const schedulerDir = path.join(dataDir, 'scheduler');

    // Ensure directory exists
    fs.mkdirSync(schedulerDir, { recursive: true });

    this.jobsFilePath = path.join(schedulerDir, 'jobs.json');

    // Load existing tasks on initialization
    this.loadTasksFromFile();
  }

  /**
   * Load task definitions from jobs.json
   */
  private loadTasksFromFile(): void {
    try {
      if (fs.existsSync(this.jobsFilePath)) {
        const content = fs.readFileSync(this.jobsFilePath, 'utf-8');
        const data = JSON.parse(content);

        if (Array.isArray(data.tasks)) {
          this.tasks.clear();
          for (const task of data.tasks) {
            this.tasks.set(task.id, task);
          }
          console.log(`[FileBasedSchedulerStore] Loaded ${this.tasks.size} tasks from ${this.jobsFilePath}`);
        }
      } else {
        console.log(`[FileBasedSchedulerStore] No existing jobs.json found, starting fresh`);
      }
    } catch (error) {
      console.error(`[FileBasedSchedulerStore] Failed to load tasks from file:`, error);
      // Don't throw - allow starting with empty task set
    }
  }

  /**
   * Atomically persist tasks to jobs.json
   * Uses tmp+rename pattern for atomic write
   */
  private async persistTasksToFile(): Promise<void> {
    const tasks = Array.from(this.tasks.values());
    const data = {
      version: 1,
      updatedAt: new Date().toISOString(),
      tasks,
    };

    const tmpPath = `${this.jobsFilePath}.tmp`;

    try {
      // Write to temporary file
      fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2), 'utf-8');

      // Atomic rename
      fs.renameSync(tmpPath, this.jobsFilePath);
    } catch (error) {
      // Clean up tmp file if it exists
      try {
        fs.unlinkSync(tmpPath);
      } catch {
        // Ignore cleanup errors
      }
      throw error;
    }
  }

  async listTasks(options: { enabledOnly?: boolean; includeDeleted?: boolean } = {}): Promise<SchedulerTask[]> {
    return Array.from(this.tasks.values())
      .filter((task) => options.includeDeleted || !task.deletedAt)
      .filter((task) => !options.enabledOnly || task.enabled)
      .map((task) => ({ ...task, payload: { ...task.payload } }));
  }

  async getTask(id: string): Promise<SchedulerTask | undefined> {
    const task = this.tasks.get(id);
    return task ? { ...task, payload: { ...task.payload } } : undefined;
  }

  async createTask(task: SchedulerTask): Promise<SchedulerTask> {
    this.tasks.set(task.id, { ...task, payload: { ...task.payload } });
    await this.persistTasksToFile();
    return { ...task, payload: { ...task.payload } };
  }

  async updateTask(id: string, updates: Partial<SchedulerTask>): Promise<SchedulerTask> {
    const existing = this.tasks.get(id);
    if (!existing) {
      throw new Error(`Scheduler task not found: ${id}`);
    }
    const updated = { ...existing, ...updates, payload: updates.payload ?? existing.payload };
    this.tasks.set(id, updated);
    await this.persistTasksToFile();
    return { ...updated, payload: { ...updated.payload } };
  }

  async softDeleteTask(id: string, deletedAt: string): Promise<void> {
    await this.updateTask(id, { enabled: false, deletedAt, updatedAt: deletedAt });
  }

  // Run management stays in-memory (execution history goes to PG via v2 API)
  async createRun(run: SchedulerRun): Promise<SchedulerRun> {
    this.runs.set(run.id, { ...run, payload: { ...run.payload } });
    return { ...run, payload: { ...run.payload } };
  }

  async updateRun(id: string, updates: Partial<SchedulerRun>): Promise<SchedulerRun> {
    const existing = this.runs.get(id);
    if (!existing) {
      throw new Error(`Scheduler run not found: ${id}`);
    }
    const updated = { ...existing, ...updates, payload: updates.payload ?? existing.payload };
    this.runs.set(id, updated);
    return { ...updated, payload: { ...updated.payload } };
  }

  async listRuns(options: { taskId?: string; date?: string; limit?: number } = {}): Promise<SchedulerRun[]> {
    const runs = Array.from(this.runs.values())
      .filter((run) => !options.taskId || run.taskId === options.taskId)
      .filter((run) => !options.date || localDateKey(new Date(run.scheduledFor)) === options.date)
      .sort((left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt));
    return runs.slice(0, options.limit ?? runs.length).map((run) => ({ ...run, payload: { ...run.payload } }));
  }
}

function localDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}
