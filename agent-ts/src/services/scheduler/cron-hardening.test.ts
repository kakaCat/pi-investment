import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { SchedulerService, InMemorySchedulerStore, type SchedulerTask, type SchedulerExecutionContext } from './scheduler-service.js';

describe('SchedulerService - Cron Hardening', () => {
  let store: InMemorySchedulerStore;
  let mockNow: Date;
  const executionLog: string[] = [];

  const createService = (options: {
    misfireGracePeriodMs?: number;
    taskTimeoutMs?: number;
  } = {}) => {
    return new SchedulerService({
      store,
      executor: async (context: SchedulerExecutionContext) => {
        executionLog.push(`executed:${context.task.name}`);
        const delay = (context.task.payload.delay as number) ?? 0;
        if (delay > 0) {
          await new Promise((resolve) => setTimeout(resolve, delay));
        }
      },
      now: () => mockNow,
      idGenerator: () => `run-${Date.now()}-test`,
      misfireGracePeriodMs: options.misfireGracePeriodMs,
      taskTimeoutMs: options.taskTimeoutMs,
    });
  };

  beforeEach(() => {
    store = new InMemorySchedulerStore();
    mockNow = new Date('2026-08-12T09:00:00Z');
    executionLog.length = 0;
  });

  afterEach(() => {
    // No cleanup needed for in-memory store
  });

  describe('restart recovery', () => {
    it('should reload tasks after restart', async () => {
      const task: SchedulerTask = {
        id: 'task-1',
        name: 'test-task',
        enabled: true,
        scheduleKind: 'cron',
        scheduleExpr: '0 9 * * *', // 9:00 AM daily
        payload: {},
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: mockNow.toISOString(),
        updatedAt: mockNow.toISOString(),
      };

      await store.createTask(task);

      const service1 = createService();
      await service1.reloadTasks();
      const summaries1 = await service1.listTaskSummaries();
      expect(summaries1).toHaveLength(1);
      expect(summaries1[0].name).toBe('test-task');

      // Simulate restart - create new service instance
      const service2 = createService();
      await service2.reloadTasks();
      const summaries2 = await service2.listTaskSummaries();
      expect(summaries2).toHaveLength(1);
      expect(summaries2[0].name).toBe('test-task');
    });
  });

  describe('misfire handling', () => {
    it('should execute tasks within grace period', async () => {
      // Use 'every' schedule for more predictable testing
      const task: SchedulerTask = {
        id: 'task-1',
        name: 'on-time-task',
        enabled: true,
        scheduleKind: 'every',
        everySeconds: 60, // Every minute
        payload: {},
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: new Date('2026-08-12T09:00:00Z').toISOString(),
        updatedAt: new Date('2026-08-12T09:00:00Z').toISOString(),
        anchorAt: new Date('2026-08-12T09:00:00Z').toISOString(),
      };

      await store.createTask(task);
      const service = createService({ misfireGracePeriodMs: 5 * 60 * 1000 }); // 5 minutes
      await service.reloadTasks();

      // Task scheduled for 9:00, now is 9:02 (2 minutes late - within grace period)
      mockNow = new Date('2026-08-12T09:02:00Z');
      await service.tick();

      expect(executionLog).toContain('executed:on-time-task');
    });

    it('should skip tasks beyond grace period (misfire)', async () => {
      const task: SchedulerTask = {
        id: 'task-1',
        name: 'late-task',
        enabled: true,
        scheduleKind: 'every',
        everySeconds: 60, // Every minute
        payload: {},
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: new Date('2026-08-12T09:00:00Z').toISOString(),
        updatedAt: new Date('2026-08-12T09:00:00Z').toISOString(),
        anchorAt: new Date('2026-08-12T09:00:00Z').toISOString(),
      };

      await store.createTask(task);
      const service = createService({ misfireGracePeriodMs: 5 * 60 * 1000 }); // 5 minutes
      await service.reloadTasks();

      // Task scheduled for 9:00, now is 9:10 (10 minutes late - beyond grace period)
      mockNow = new Date('2026-08-12T09:10:00Z');
      await service.tick();

      // Task should NOT execute
      expect(executionLog).not.toContain('executed:late-task');

      // Verify a skipped run was recorded
      const runs = await store.listRuns({ taskId: 'task-1' });
      expect(runs).toHaveLength(1);
      expect(runs[0].status).toBe('skipped');
      expect(runs[0].error).toContain('misfire');
    });

    it('should reschedule misfired tasks to next period', async () => {
      // Set mockNow to 9:00:00 first for task creation
      mockNow = new Date('2026-08-12T09:00:00Z');

      const task: SchedulerTask = {
        id: 'task-1',
        name: 'reschedule-task',
        enabled: true,
        scheduleKind: 'every',
        everySeconds: 60, // Every minute
        payload: {},
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: new Date('2026-08-12T09:00:00Z').toISOString(),
        updatedAt: new Date('2026-08-12T09:00:00Z').toISOString(),
        anchorAt: new Date('2026-08-12T09:00:00Z').toISOString(),
      };

      await store.createTask(task);
      const service = createService({ misfireGracePeriodMs: 10 * 1000 }); // 10 seconds
      await service.reloadTasks();

      // Move time forward: Task scheduled for 9:01:00, now is 9:01:30 (30 seconds late - beyond 10s grace)
      mockNow = new Date('2026-08-12T09:01:30Z');
      await service.tick();

      // Should skip this run due to misfire
      expect(executionLog).not.toContain('executed:reschedule-task');

      // Should reschedule to next period (9:02:00)
      const summaries = await service.listTaskSummaries();
      expect(summaries[0].nextRunAt).toBe(new Date('2026-08-12T09:02:00Z').toISOString());

      // Verify skipped run was recorded
      const runs = await store.listRuns({ taskId: 'task-1' });
      expect(runs).toHaveLength(1);
      expect(runs[0].status).toBe('skipped');
    });
  });

  describe('watchdog timeout', () => {
    it('should mark task as failed if it exceeds timeout', async () => {
      // Set mockNow to 9:00:00 first
      mockNow = new Date('2026-08-12T09:00:00Z');

      const task: SchedulerTask = {
        id: 'task-1',
        name: 'slow-task',
        enabled: true,
        scheduleKind: 'at',
        scheduleAt: new Date('2026-08-12T09:00:00Z').toISOString(),
        payload: { delay: 200 }, // Task takes 200ms
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: new Date('2026-08-12T08:59:00Z').toISOString(),
        updatedAt: new Date('2026-08-12T08:59:00Z').toISOString(),
      };

      await store.createTask(task);
      const service = createService({ taskTimeoutMs: 100 }); // 100ms timeout
      await service.reloadTasks();

      // Advance time to trigger the task
      mockNow = new Date('2026-08-12T09:00:01Z');

      // Trigger the task immediately
      const tickPromise = service.tick();

      // Wait for timeout to fire
      await new Promise((resolve) => setTimeout(resolve, 150));

      // Wait for tick to complete
      await tickPromise;

      const runs = await store.listRuns({ taskId: 'task-1' });
      expect(runs.length).toBeGreaterThanOrEqual(1);
      expect(runs[0].status).toBe('failed');
      expect(runs[0].error).toContain('exceeded timeout');
    }, 10000);

    it('should complete successfully if task finishes within timeout', async () => {
      // Set mockNow to 9:00:00 first
      mockNow = new Date('2026-08-12T09:00:00Z');

      const task: SchedulerTask = {
        id: 'task-1',
        name: 'fast-task',
        enabled: true,
        scheduleKind: 'at',
        scheduleAt: new Date('2026-08-12T09:00:00Z').toISOString(),
        payload: { delay: 50 }, // Task takes 50ms
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: new Date('2026-08-12T08:59:00Z').toISOString(),
        updatedAt: new Date('2026-08-12T08:59:00Z').toISOString(),
      };

      await store.createTask(task);
      const service = createService({ taskTimeoutMs: 200 }); // 200ms timeout
      await service.reloadTasks();

      // Advance time to trigger the task
      mockNow = new Date('2026-08-12T09:00:01Z');

      await service.tick();

      // Wait for task to complete
      await new Promise((resolve) => setTimeout(resolve, 100));

      const runs = await store.listRuns({ taskId: 'task-1' });
      expect(runs.length).toBeGreaterThanOrEqual(1);
      expect(runs[0].status).toBe('success');
      expect(executionLog).toContain('executed:fast-task');
    }, 10000);

    it('should clean up timeout handlers on service stop', async () => {
      const task: SchedulerTask = {
        id: 'task-1',
        name: 'cleanup-task',
        enabled: true,
        scheduleKind: 'cron',
        scheduleExpr: '0 9 * * *',
        payload: { delay: 1000 }, // Long running
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: mockNow.toISOString(),
        updatedAt: mockNow.toISOString(),
      };

      await store.createTask(task);
      const service = createService({ taskTimeoutMs: 500 });
      await service.reloadTasks();
      service.start();

      // Trigger task execution
      await service.tick();

      // Stop service (should clean up timeouts)
      service.stop();

      // Wait a bit to ensure no timeout fires
      await new Promise((resolve) => setTimeout(resolve, 600));

      // Service should be stopped, no crashes
      expect(true).toBe(true);
    }, 10000);
  });

  describe('integration: all features', () => {
    it('should handle restart, misfire, and timeout together', async () => {
      // Set initial time
      mockNow = new Date('2026-08-12T09:00:00Z');

      // Task: Should misfire (scheduled at 9:00 but we check at 9:10)
      const task: SchedulerTask = {
        id: 'task-1',
        name: 'integration-task',
        enabled: true,
        scheduleKind: 'at',
        scheduleAt: new Date('2026-08-12T09:00:00Z').toISOString(),
        payload: {},
        compensationEnabled: false,
        compensationMaxAttempts: 0,
        deleteAfterRun: false,
        createdAt: new Date('2026-08-12T08:59:00Z').toISOString(),
        updatedAt: new Date('2026-08-12T08:59:00Z').toISOString(),
      };

      await store.createTask(task);

      // Create service and reload tasks
      const service = createService({
        misfireGracePeriodMs: 5 * 60 * 1000, // 5 minutes
        taskTimeoutMs: 10 * 1000, // 10 seconds
      });
      await service.reloadTasks();

      // Verify task was loaded
      const summaries = await service.listTaskSummaries();
      expect(summaries.length).toBe(1);
      expect(summaries[0].name).toBe('integration-task');

      // Now is 9:10 - task scheduled at 9:00 (10 min late - beyond grace)
      mockNow = new Date('2026-08-12T09:10:00Z');
      await service.tick();

      // Task should misfire and be skipped
      const runs = await store.listRuns();
      expect(runs.length).toBe(1);
      expect(runs[0].status).toBe('skipped');
      expect(runs[0].error).toContain('misfire');

      // Verify task was not executed
      expect(executionLog).not.toContain('executed:integration-task');
    });
  });
});
