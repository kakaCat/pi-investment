import { Router } from 'express';
import { PythonBackendClient } from '../../../services/python/python-backend-client.js';

const router = Router();

// GET /api/performance/strategy/:id - 获取策略性能
router.get('/strategy/:id', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get(`/api/performance/strategy/${req.params.id}`, req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

// GET /api/performance/comparison - 多策略对比
router.get('/comparison', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/performance/comparison', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

export { router as performanceRouter };

// LEGACY: PerformanceAnalyzer and QuantService-based implementation - kept for rollback
// import { Router } from 'express';
// import { PerformanceAnalyzer } from '../../../services/quant/performance-analyzer.js';
// import { QuantService } from '../../../services/quant/quant-service.js';
// const router = Router();
// const performanceAnalyzer = new PerformanceAnalyzer();
// const quantService = new QuantService();
// router.get('/strategy/:id', async (req, res, next) => {
//   try {
//     const { id } = req.params;
//     const days = req.query.days ? parseInt(req.query.days as string) : 30;
//     const strategy = await quantService.getStrategy(id);
//     if (!strategy) {
//       res.status(404);
//       throw new Error('Strategy not found');
//     }
//     const metrics = await performanceAnalyzer.analyzeStrategy(
//       id,
//       strategy.name,
//       days
//     );
//     res.json({ success: true, data: metrics });
//   } catch (error) {
//     next(error);
//   }
// });
// router.get('/comparison', async (req, res, next) => {
//   try {
//     const days = req.query.days ? parseInt(req.query.days as string) : 30;
//     const strategies = await quantService.listStrategies();
//     const comparisons = await Promise.all(
//       strategies.map(async (strategy) => {
//         const metrics = await performanceAnalyzer.analyzeStrategy(
//           strategy.id,
//           strategy.name,
//           days
//         );
//         return metrics;
//       })
//     );
//     const validComparisons = comparisons.filter(c => c.total_signals > 0);
//     res.json({ success: true, data: validComparisons });
//   } catch (error) {
//     next(error);
//   }
// });
// export { router as performanceRouter };
