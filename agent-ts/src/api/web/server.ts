import express from 'express';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { Client } from 'pg';
import { strategiesRouter } from './routes/strategies.js';
import {
  signalsRouter,
  backtestRouter,
  performanceRouter,
  chartsRouter,
  stocksRouter,
  featuresRouter,
  trainingRouter,
  jobsRouter,
  platformRouter,
  schedulerRouter,
  pipelineRouter
} from './routes/placeholder-routes.js';
import { portfolioRouter } from './routes/portfolio.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.API_PORT || 3001;

function getDatabaseProvider(): 'postgres' | 'sqlite' {
  return process.env.QUANT_DB_PROVIDER?.trim().toLowerCase() === 'sqlite'
    ? 'sqlite'
    : 'postgres';
}

async function getPostgresHealthInfo(): Promise<{
  connected: boolean;
  info: Record<string, unknown> | null;
  error?: string;
}> {
  const connectionString = process.env.QUANT_DATABASE_URL
    || process.env.DATABASE_URL
    || process.env.POSTGRES_DSN;
  const client = new Client(connectionString
    ? { connectionString }
    : {
        database: process.env.PGDATABASE || 'quant_investment',
        host: process.env.PGHOST,
        port: process.env.PGPORT ? Number(process.env.PGPORT) : undefined,
        user: process.env.PGUSER,
        password: process.env.PGPASSWORD,
      });

  try {
    await client.connect();
    const result = await client.query('SELECT current_database() AS database, pg_database_size(current_database()) AS size_bytes');
    const row = result.rows[0] as { database?: string; size_bytes?: string | number } | undefined;
    const sizeBytes = Number(row?.size_bytes ?? 0);
    const sizeMb = sizeBytes / (1024 * 1024);

    return {
      connected: true,
      info: {
        provider: 'postgres',
        database: row?.database ?? process.env.PGDATABASE ?? 'quant_investment',
        size_mb: Math.round(sizeMb * 100) / 100,
        size_display: sizeMb >= 1024 ? `${(sizeMb / 1024).toFixed(1)} GB` : `${sizeMb.toFixed(1)} MB`,
      },
    };
  } catch (error) {
    return {
      connected: false,
      info: {
        provider: 'postgres',
        database: process.env.PGDATABASE ?? 'quant_investment',
      },
      error: error instanceof Error ? error.message : 'Unknown PostgreSQL connection error',
    };
  } finally {
    await client.end().catch(() => undefined);
  }
}

// 中间件
app.use(cors({
  origin: process.env.CORS_ORIGIN || 'http://127.0.0.1:3000',
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
app.use('/api/jobs', jobsRouter);
app.use('/api/platform', platformRouter);
app.use('/api/scheduler', schedulerRouter);
app.use('/api/pipeline', pipelineRouter);
app.use('/api/portfolio', portfolioRouter);
app.use('/api', featuresRouter);

// 健康检查 (放在 /api 下以便前端统一访问)
app.get('/api/health', async (req, res) => {
  try {
    let dbConnected = false;
    let dbInfo = null;

    if (getDatabaseProvider() === 'postgres') {
      const health = await getPostgresHealthInfo();
      dbConnected = health.connected;
      dbInfo = health.info;
      if (!health.connected && health.error) {
        dbInfo = { ...dbInfo, error: health.error };
      }
    } else {
      // 检查 SQLite 文件连接（仅显式 QUANT_DB_PROVIDER=sqlite 时使用）
      const projectRoot = path.resolve(__dirname, '../../../');
      const dbPath = path.join(projectRoot, '.pi-invest/stock-db/stocks.db');
      dbConnected = fs.existsSync(dbPath);

      if (dbConnected) {
        try {
          const stats = fs.statSync(dbPath);
          const sizeBytes = stats.size;
          const sizeMb = sizeBytes / (1024 * 1024);

          let sizeDisplay: string;
          if (sizeMb < 1) {
            sizeDisplay = `${(sizeBytes / 1024).toFixed(1)} KB`;
          } else if (sizeMb < 1024) {
            sizeDisplay = `${sizeMb.toFixed(1)} MB`;
          } else {
            sizeDisplay = `${(sizeMb / 1024).toFixed(1)} GB`;
          }

          dbInfo = {
            provider: 'sqlite',
            path: dbPath,
            size_mb: Math.round(sizeMb * 100) / 100,
            size_display: sizeDisplay
          };
        } catch (error) {
          console.error('Failed to get database file info:', error);
        }
      }
    }

    // 检查模型文件是否存在
    let modelLoaded = false;
    const modelPath = path.join(__dirname, '../../../quant/quantsys/ml/models/xgboost_latest.pkl');
    modelLoaded = fs.existsSync(modelPath);

    res.json({
      status: 'ok',
      timestamp: new Date().toISOString(),
      db_connected: dbConnected,
      model_loaded: modelLoaded,
      db_info: dbInfo
    });
  } catch (error) {
    console.error('Health check error:', error);
    res.status(500).json({
      status: 'error',
      timestamp: new Date().toISOString(),
      db_connected: false,
      model_loaded: false,
      db_info: null,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

// 错误处理
app.use((err: any, req: any, res: any, next: any) => {
  console.error('Error:', err);
  res.status(500).json({ error: err.message || 'Internal server error' });
});

// 启动服务器
app.listen(PORT, () => {
  console.log(`🚀 Quant API Server running on http://127.0.0.1:${PORT}`);
  console.log(`📊 Health check: http://127.0.0.1:${PORT}/api/health`);
  console.log(`🔗 CORS enabled for: ${process.env.CORS_ORIGIN || 'http://127.0.0.1:3000'}`);
});

export default app;
