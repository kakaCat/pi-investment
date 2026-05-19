import { Router } from 'express';
import { spawn } from 'child_process';
import * as path from 'path';
import { fileURLToPath } from 'url';
import * as fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const router = Router();

// 训练任务状态管理
interface TrainingTask {
  id: string;
  status: 'running' | 'completed' | 'failed';
  progress: number;
  startTime: string;
  endTime?: string;
  params: TrainingParams;
  result?: any;
  error?: string;
  logs: string[];
}

interface TrainingParams {
  days: number;
  model: 'xgboost' | 'lightgbm' | 'random_forest';
  cvSplits: number;
  useFeatureEngineering: boolean;
}

const trainingTasks = new Map<string, TrainingTask>();

// POST /api/training/start - 启动模型训练
router.post('/start', async (req, res, next) => {
  try {
    const {
      days = 90,
      model = 'xgboost',
      cvSplits = 5,
      useFeatureEngineering = true
    }: TrainingParams = req.body;

    // 验证参数
    if (days < 30 || days > 365) {
      res.status(400);
      throw new Error('days must be between 30 and 365');
    }

    if (!['xgboost', 'lightgbm', 'random_forest'].includes(model)) {
      res.status(400);
      throw new Error('model must be one of: xgboost, lightgbm, random_forest');
    }

    if (cvSplits < 2 || cvSplits > 10) {
      res.status(400);
      throw new Error('cvSplits must be between 2 and 10');
    }

    // 生成任务ID
    const taskId = `train_${Date.now()}`;

    // 创建任务记录
    const task: TrainingTask = {
      id: taskId,
      status: 'running',
      progress: 0,
      startTime: new Date().toISOString(),
      params: { days, model, cvSplits, useFeatureEngineering },
      logs: []
    };
    trainingTasks.set(taskId, task);

    // 构建训练命令
    const scriptPath = path.join(__dirname, '../../../../quant/scripts/ml_retrain.py');
    const args = [
      scriptPath,
      '--days', days.toString(),
      '--model', model,
      '--cv-splits', cvSplits.toString()
    ];

    if (useFeatureEngineering) {
      args.push('--use-feature-engineering');
    }

    // 异步执行训练
    const pythonProcess = spawn('python3', args, {
      cwd: path.join(__dirname, '../../../../quant')
    });

    // 捕获输出
    pythonProcess.stdout.on('data', (data) => {
      const log = data.toString();
      task.logs.push(log);
      console.log(`[Training ${taskId}] ${log}`);

      // 解析进度（如果日志中包含进度信息）
      const progressMatch = log.match(/进度[：:]\s*(\d+)%/);
      if (progressMatch) {
        task.progress = parseInt(progressMatch[1]);
      }
    });

    pythonProcess.stderr.on('data', (data) => {
      const log = data.toString();
      task.logs.push(`ERROR: ${log}`);
      console.error(`[Training ${taskId}] ERROR: ${log}`);
    });

    pythonProcess.on('close', (code) => {
      if (code === 0) {
        task.status = 'completed';
        task.progress = 100;
        task.endTime = new Date().toISOString();

        // 读取训练报告
        try {
          const reportPath = path.join(__dirname, '../../../../quant/quantsys/ml/models/training_report_latest.json');
          if (fs.existsSync(reportPath)) {
            const reportContent = fs.readFileSync(reportPath, 'utf-8');
            task.result = JSON.parse(reportContent);
          }
        } catch (error) {
          console.error('Failed to read training report:', error);
        }

        console.log(`[Training ${taskId}] Completed successfully`);
      } else {
        task.status = 'failed';
        task.endTime = new Date().toISOString();
        task.error = `Training process exited with code ${code}`;
        console.error(`[Training ${taskId}] Failed with code ${code}`);
      }
    });

    res.json({
      success: true,
      data: {
        taskId,
        status: 'running',
        message: 'Training started successfully'
      }
    });
  } catch (error) {
    next(error);
  }
});

// GET /api/training/status/:taskId - 查询训练状态
router.get('/status/:taskId', async (req, res, next) => {
  try {
    const { taskId } = req.params;
    const task = trainingTasks.get(taskId);

    if (!task) {
      res.status(404);
      throw new Error('Training task not found');
    }

    res.json({
      success: true,
      data: {
        id: task.id,
        status: task.status,
        progress: task.progress,
        startTime: task.startTime,
        endTime: task.endTime,
        params: task.params,
        result: task.result,
        error: task.error
      }
    });
  } catch (error) {
    next(error);
  }
});

// GET /api/training/logs/:taskId - 获取训练日志
router.get('/logs/:taskId', async (req, res, next) => {
  try {
    const { taskId } = req.params;
    const task = trainingTasks.get(taskId);

    if (!task) {
      res.status(404);
      throw new Error('Training task not found');
    }

    res.json({
      success: true,
      data: {
        taskId: task.id,
        logs: task.logs
      }
    });
  } catch (error) {
    next(error);
  }
});

// GET /api/training/tasks - 获取所有训练任务
router.get('/tasks', async (req, res, next) => {
  try {
    const tasks = Array.from(trainingTasks.values()).map(task => ({
      id: task.id,
      status: task.status,
      progress: task.progress,
      startTime: task.startTime,
      endTime: task.endTime,
      params: task.params
    }));

    res.json({
      success: true,
      data: tasks
    });
  } catch (error) {
    next(error);
  }
});

// GET /api/training/reports - 获取历史训练报告列表
router.get('/reports', async (req, res, next) => {
  try {
    const modelsDir = path.join(__dirname, '../../../../quant/quantsys/ml/models');

    if (!fs.existsSync(modelsDir)) {
      res.json({ success: true, data: [] });
      return;
    }

    const files = fs.readdirSync(modelsDir);
    const reportFiles = files
      .filter(f => f.startsWith('training_report_') && f.endsWith('.json') && f !== 'training_report_latest.json')
      .sort()
      .reverse();

    const reports = reportFiles.slice(0, 20).map(filename => {
      const filePath = path.join(modelsDir, filename);
      const content = fs.readFileSync(filePath, 'utf-8');
      const report = JSON.parse(content);

      // 从文件名提取时间戳
      const timestamp = filename.replace('training_report_', '').replace('.json', '');

      return {
        filename,
        timestamp,
        metrics: report.metrics,
        params: report.params,
        n_features: report.n_features
      };
    });

    res.json({
      success: true,
      data: reports
    });
  } catch (error) {
    next(error);
  }
});

// GET /api/training/report/:filename - 获取特定训练报告详情
router.get('/report/:filename', async (req, res, next) => {
  try {
    const { filename } = req.params;

    // 安全检查：防止路径遍历攻击
    if (filename.includes('..') || filename.includes('/')) {
      res.status(400);
      throw new Error('Invalid filename');
    }

    const reportPath = path.join(__dirname, '../../../../quant/quantsys/ml/models', filename);

    if (!fs.existsSync(reportPath)) {
      res.status(404);
      throw new Error('Report not found');
    }

    const content = fs.readFileSync(reportPath, 'utf-8');
    const report = JSON.parse(content);

    res.json({
      success: true,
      data: report
    });
  } catch (error) {
    next(error);
  }
});

// GET /api/training/history - 获取训练历史记录
router.get('/history', async (req, res, next) => {
  try {
    const modelsDir = path.join(__dirname, '../../../../quant/quantsys/ml/models');

    if (!fs.existsSync(modelsDir)) {
      res.json({ history: [] });
      return;
    }

    const files = fs.readdirSync(modelsDir);
    const reportFiles = files
      .filter(f => f.startsWith('training_report_') && f.endsWith('.json') && f !== 'training_report_latest.json')
      .sort()
      .reverse();

    const history = reportFiles.slice(0, 50).map(filename => {
      try {
        const filePath = path.join(modelsDir, filename);
        const content = fs.readFileSync(filePath, 'utf-8');
        const report = JSON.parse(content);

        return {
          timestamp: report.timestamp,
          model_type: report.model_type,
          n_features: report.data?.n_features || 0,
          total_samples: report.data?.total_samples || 0,
          cv_accuracy: report.cv_results?.mean_scores?.accuracy || 0,
          cv_auc: report.cv_results?.mean_scores?.auc || 0,
          test_accuracy: report.test_metrics?.accuracy || 0,
          test_auc: report.test_metrics?.auc || 0,
          class_balance: report.data?.class_balance || 0
        };
      } catch (error) {
        console.warn(`Failed to parse training report ${filename}:`, error);
        return null;
      }
    }).filter(record => record !== null);

    res.json({ history });
  } catch (error) {
    next(error);
  }
});

export { router as trainingRouter };
