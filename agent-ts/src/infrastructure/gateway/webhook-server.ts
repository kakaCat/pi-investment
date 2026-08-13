/**
 * Webhook Server - Receive task triggers from Agent OS Scheduler
 *
 * 接收 Agent OS 触发的任务请求，创建新的 agent session 执行任务
 */

import express, { Request, Response } from 'express';
import type { Express } from 'express';

export interface WebhookPayload {
  task: string;         // 任务名称
  prompt: string;       // 执行提示词
  execution_id?: string; // Agent OS 的执行 ID（可选）
}

export interface TaskExecutor {
  executeTask(params: {
    taskName: string;
    prompt: string;
    executionId?: string;
  }): Promise<any>;
}

/**
 * Create webhook server to receive Agent OS task triggers
 */
export function createWebhookServer(
  taskExecutor: TaskExecutor,
  options: {
    port?: number;
    host?: string;
  } = {}
): Express {
  const app = express();
  const port = options.port || 3000;
  const host = options.host || '0.0.0.0';

  // Middleware
  app.use(express.json());

  // Request logging middleware
  app.use((req, _res, next) => {
    console.log(`[Webhook] ${req.method} ${req.path}`);
    next();
  });

  /**
   * POST /api/agent/trigger
   *
   * Agent OS 调用此接口触发任务执行
   */
  app.post('/api/agent/trigger', async (req: Request, res: Response) => {
    const payload: WebhookPayload = req.body;

    console.log(`[Webhook] Received task trigger: ${payload.task}`);

    // 验证请求参数
    if (!payload.task || !payload.prompt) {
      res.status(400).json({
        success: false,
        error: 'Missing required fields: task, prompt',
      });
      return;
    }

    try {
      // 执行任务
      const result = await taskExecutor.executeTask({
        taskName: payload.task,
        prompt: payload.prompt,
        executionId: payload.execution_id,
      });

      console.log(`[Webhook] Task completed: ${payload.task}`);

      res.json({
        success: true,
        task: payload.task,
        result: result,
      });
    } catch (error: any) {
      console.error(`[Webhook] Task execution failed: ${payload.task}`, error);

      res.status(500).json({
        success: false,
        error: error.message,
        stack: process.env.NODE_ENV === 'development' ? error.stack : undefined,
      });
    }
  });

  /**
   * GET /health
   *
   * 健康检查接口
   */
  app.get('/health', (_req: Request, res: Response) => {
    res.json({
      status: 'ok',
      service: 'agent-ts-webhook',
      timestamp: new Date().toISOString(),
    });
  });

  /**
   * GET /api/agent/status
   *
   * Agent 状态查询接口（可选）
   */
  app.get('/api/agent/status', (_req: Request, res: Response) => {
    res.json({
      status: 'running',
      uptime: process.uptime(),
      memoryUsage: process.memoryUsage(),
      nodeVersion: process.version,
    });
  });

  // 404 handler
  app.use((_req: Request, res: Response) => {
    res.status(404).json({
      success: false,
      error: 'Not found',
    });
  });

  // Error handler
  app.use((err: Error, _req: Request, res: Response, _next: any) => {
    console.error('[Webhook] Unhandled error:', err);
    res.status(500).json({
      success: false,
      error: 'Internal server error',
      message: err.message,
    });
  });

  return app;
}

/**
 * Start webhook server
 */
export function startWebhookServer(
  app: Express,
  port: number = 3000,
  host: string = '0.0.0.0'
): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      const server = app.listen(port, host, () => {
        console.log(`✓ Webhook server listening on http://${host}:${port}`);
        console.log(`  - Trigger endpoint: http://localhost:${port}/api/agent/trigger`);
        console.log(`  - Health check: http://localhost:${port}/health`);
        resolve();
      });

      server.on('error', (error: any) => {
        if (error.code === 'EADDRINUSE') {
          console.error(`✗ Port ${port} is already in use`);
        } else {
          console.error(`✗ Failed to start webhook server:`, error);
        }
        reject(error);
      });
    } catch (error) {
      reject(error);
    }
  });
}
