import express from 'express';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { strategiesRouter } from './routes/strategies.js';
import { signalsRouter } from './routes/signals.js';
import { backtestRouter } from './routes/backtest.js';
import { performanceRouter } from './routes/performance.js';
import { chartsRouter } from './routes/charts.js';
import { stocksRouter } from './routes/stocks.js';
import { featuresRouter } from './routes/features.js';
import { trainingRouter } from './routes/training.js';
import { errorHandler } from './middleware/error-handler.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.API_PORT || 3001;

// 中间件
app.use(cors({
  origin: process.env.CORS_ORIGIN || 'http://localhost:3000',
  credentials: true
}));
app.use(express.json());

// 请求日志
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  next();
});

// API路由
app.use('/api/strategies', strategiesRouter);
app.use('/api/signals', signalsRouter);
app.use('/api/backtest', backtestRouter);
app.use('/api/performance', performanceRouter);
app.use('/api/charts', chartsRouter);
app.use('/api/stocks', stocksRouter);
app.use('/api/training', trainingRouter);
app.use('/api', featuresRouter);

// 健康检查 (放在 /api 下以便前端统一访问)
app.get('/api/health', async (req, res) => {
  try {
    // 检查数据库连接（使用项目目录）
    const projectRoot = path.resolve(__dirname, '../../../');
    const dbPath = path.join(projectRoot, '.pi-invest/stock-db/stocks.db');
    const dbConnected = fs.existsSync(dbPath);

    // 检查模型文件是否存在
    let modelLoaded = false;
    const modelPath = path.join(__dirname, '../../../quant/quantsys/ml/models/xgboost_latest.pkl');
    modelLoaded = fs.existsSync(modelPath);

    res.json({
      status: 'ok',
      timestamp: new Date().toISOString(),
      db_connected: dbConnected,
      model_loaded: modelLoaded
    });
  } catch (error) {
    console.error('Health check error:', error);
    res.status(500).json({
      status: 'error',
      timestamp: new Date().toISOString(),
      db_connected: false,
      model_loaded: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

// 错误处理
app.use(errorHandler);

// 启动服务器
app.listen(PORT, () => {
  console.log(`🚀 Quant API Server running on http://localhost:${PORT}`);
  console.log(`📊 Health check: http://localhost:${PORT}/api/health`);
  console.log(`🔗 CORS enabled for: ${process.env.CORS_ORIGIN || 'http://localhost:3000'}`);
});

export default app;
