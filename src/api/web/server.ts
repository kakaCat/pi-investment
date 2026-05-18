import express from 'express';
import cors from 'cors';
import { strategiesRouter } from './routes/strategies.js';
import { signalsRouter } from './routes/signals.js';
import { backtestRouter } from './routes/backtest.js';
import { performanceRouter } from './routes/performance.js';
import { chartsRouter } from './routes/charts.js';
import { stocksRouter } from './routes/stocks.js';
import { errorHandler } from './middleware/error-handler.js';

const app = express();
const PORT = process.env.API_PORT || 3001;

// 中间件
app.use(cors({
  origin: process.env.CORS_ORIGIN || 'http://localhost:5173',
  credentials: true
}));
app.use(express.json());

// 请求日志
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  next();
});

// 健康检查
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// API路由
app.use('/api/strategies', strategiesRouter);
app.use('/api/signals', signalsRouter);
app.use('/api/backtest', backtestRouter);
app.use('/api/performance', performanceRouter);
app.use('/api/charts', chartsRouter);
app.use('/api/stocks', stocksRouter);

// 错误处理
app.use(errorHandler);

// 启动服务器
app.listen(PORT, () => {
  console.log(`🚀 Quant API Server running on http://localhost:${PORT}`);
  console.log(`📊 Health check: http://localhost:${PORT}/health`);
  console.log(`🔗 CORS enabled for: ${process.env.CORS_ORIGIN || 'http://localhost:5173'}`);
});

export default app;
