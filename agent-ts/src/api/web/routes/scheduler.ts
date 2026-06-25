import { Router } from 'express';
import { getSchedulerRuntime } from '../../../services/scheduler/scheduler-runtime.js';

const router = Router();

/**
 * GET /api/scheduler/tasks
 * 获取所有调度任务列表
 */
router.get('/tasks', async (req, res) => {
  try {
    const { service } = await getSchedulerRuntime();
    const summaries = await service.listTaskSummaries();

    res.json({
      success: true,
      data: summaries,
      count: summaries.length
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : String(error)
    });
  }
});

/**
 * POST /api/scheduler/tasks/:taskId/trigger
 * 手动触发任务执行
 */
router.post('/tasks/:taskId/trigger', async (req, res) => {
  try {
    const { taskId } = req.params;
    const { service } = await getSchedulerRuntime();

    const run = await service.triggerTask(taskId, 'manual');

    res.json({
      success: true,
      data: run
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : String(error)
    });
  }
});

/**
 * GET /api/scheduler/runs
 * 获取任务执行历史
 */
router.get('/runs', async (req, res) => {
  try {
    const { taskId, date, limit } = req.query;
    const { store } = await getSchedulerRuntime();

    const runs = await store.listRuns({
      taskId: taskId as string | undefined,
      date: date as string | undefined,
      limit: limit ? Number.parseInt(limit as string, 10) : undefined
    });

    res.json({
      success: true,
      data: runs,
      count: runs.length
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : String(error)
    });
  }
});

/**
 * PATCH /api/scheduler/tasks/:taskId
 * 更新任务配置（启用/禁用）
 */
router.patch('/tasks/:taskId', async (req, res) => {
  try {
    const { taskId } = req.params;
    const { enabled } = req.body;
    const { store, service } = await getSchedulerRuntime();

    const updatedTask = await store.updateTask(taskId, {
      enabled,
      updatedAt: new Date().toISOString()
    });

    // 重新加载任务
    await service.reloadTasks();

    res.json({
      success: true,
      data: updatedTask
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : String(error)
    });
  }
});

export default router;
