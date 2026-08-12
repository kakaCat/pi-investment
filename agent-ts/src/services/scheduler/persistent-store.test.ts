import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import fs from 'node:fs';
import path from 'node:path';
import { FileBasedSchedulerStore } from './persistent-store.js';
import type { SchedulerTask } from './scheduler-service.js';

describe('FileBasedSchedulerStore', () => {
  let testDataDir: string;
  let store: FileBasedSchedulerStore;

  beforeEach(() => {
    // Use a temporary directory for tests
    testDataDir = path.join(process.cwd(), '.test-scheduler-data', `test-${Date.now()}`);
    store = new FileBasedSchedulerStore({ dataDir: testDataDir });
  });

  afterEach(() => {
    // Clean up test data
    if (fs.existsSync(testDataDir)) {
      fs.rmSync(testDataDir, { recursive: true, force: true });
    }
  });

  describe('persistence', () => {
    it('should persist tasks to jobs.json on create', async () => {
      const task: SchedulerTask = {
        id: 'task-1',
        name: 'test-task',
        enabled: true,
        scheduleKind: 'cron',
        scheduleExpr: '0 9 * * *',
        payload: { action: 'test' },
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      await store.createTask(task);

      // Verify file exists
      const jobsFilePath = path.join(testDataDir, 'scheduler', 'jobs.json');
      expect(fs.existsSync(jobsFilePath)).toBe(true);

      // Verify content
      const content = JSON.parse(fs.readFileSync(jobsFilePath, 'utf-8'));
      expect(content.version).toBe(1);
      expect(content.tasks).toHaveLength(1);
      expect(content.tasks[0].id).toBe('task-1');
      expect(content.tasks[0].name).toBe('test-task');
    });

    it('should reload tasks from file on initialization', async () => {
      // Create a task with first store instance
      const task: SchedulerTask = {
        id: 'task-reload',
        name: 'reload-test',
        enabled: true,
        scheduleKind: 'every',
        everySeconds: 3600,
        payload: {},
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      await store.createTask(task);

      // Create a new store instance pointing to the same directory
      const newStore = new FileBasedSchedulerStore({ dataDir: testDataDir });

      // Verify task was loaded
      const tasks = await newStore.listTasks();
      expect(tasks).toHaveLength(1);
      expect(tasks[0].id).toBe('task-reload');
      expect(tasks[0].name).toBe('reload-test');
    });

    it('should persist updates to tasks', async () => {
      const task: SchedulerTask = {
        id: 'task-update',
        name: 'update-test',
        enabled: true,
        scheduleKind: 'cron',
        scheduleExpr: '0 10 * * *',
        payload: {},
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      await store.createTask(task);
      await store.updateTask('task-update', { enabled: false, scheduleExpr: '0 11 * * *' });

      // Create new store to verify persistence
      const newStore = new FileBasedSchedulerStore({ dataDir: testDataDir });
      const updatedTask = await newStore.getTask('task-update');

      expect(updatedTask?.enabled).toBe(false);
      expect(updatedTask?.scheduleExpr).toBe('0 11 * * *');
    });

    it('should handle atomic writes (tmp+rename pattern)', async () => {
      const task: SchedulerTask = {
        id: 'task-atomic',
        name: 'atomic-test',
        enabled: true,
        scheduleKind: 'cron',
        scheduleExpr: '0 12 * * *',
        payload: {},
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      await store.createTask(task);

      // Verify no .tmp file remains
      const tmpPath = path.join(testDataDir, 'scheduler', 'jobs.json.tmp');
      expect(fs.existsSync(tmpPath)).toBe(false);
    });
  });

  describe('task operations', () => {
    it('should list tasks with filters', async () => {
      await store.createTask({
        id: 'task-1',
        name: 'enabled-task',
        enabled: true,
        scheduleKind: 'cron',
        scheduleExpr: '0 9 * * *',
        payload: {},
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      });

      await store.createTask({
        id: 'task-2',
        name: 'disabled-task',
        enabled: false,
        scheduleKind: 'cron',
        scheduleExpr: '0 10 * * *',
        payload: {},
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      });

      const allTasks = await store.listTasks();
      expect(allTasks).toHaveLength(2);

      const enabledTasks = await store.listTasks({ enabledOnly: true });
      expect(enabledTasks).toHaveLength(1);
      expect(enabledTasks[0].name).toBe('enabled-task');
    });

    it('should soft delete tasks', async () => {
      await store.createTask({
        id: 'task-delete',
        name: 'delete-test',
        enabled: true,
        scheduleKind: 'cron',
        scheduleExpr: '0 9 * * *',
        payload: {},
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      });

      await store.softDeleteTask('task-delete', new Date().toISOString());

      const allTasks = await store.listTasks({ includeDeleted: true });
      expect(allTasks).toHaveLength(1);
      expect(allTasks[0].deletedAt).toBeDefined();
      expect(allTasks[0].enabled).toBe(false);

      const activeTasks = await store.listTasks();
      expect(activeTasks).toHaveLength(0);
    });
  });

  describe('error handling', () => {
    it('should handle corrupted jobs.json gracefully', async () => {
      // Write corrupted JSON
      const jobsFilePath = path.join(testDataDir, 'scheduler', 'jobs.json');
      fs.mkdirSync(path.dirname(jobsFilePath), { recursive: true });
      fs.writeFileSync(jobsFilePath, 'not valid json', 'utf-8');

      // Should not throw, just start with empty task set
      const newStore = new FileBasedSchedulerStore({ dataDir: testDataDir });
      const tasks = await newStore.listTasks();
      expect(tasks).toHaveLength(0);
    });

    it('should handle missing directory gracefully', async () => {
      const nonExistentDir = path.join(testDataDir, 'non-existent');
      const newStore = new FileBasedSchedulerStore({ dataDir: nonExistentDir });
      const tasks = await newStore.listTasks();
      expect(tasks).toHaveLength(0);
    });
  });
});
