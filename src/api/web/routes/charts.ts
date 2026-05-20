import { Router } from 'express';
import { PythonBackendClient } from '../../../services/python/python-backend-client.js';

const router = Router();

// GET /api/charts/accuracy - 准确率趋势图
router.get('/accuracy', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/charts/accuracy', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

// GET /api/charts/equity - 权益曲线图
router.get('/equity', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/charts/equity', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

// GET /api/charts/comparison - 策略对比图
router.get('/comparison', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/charts/comparison', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

// GET /api/charts/importance - 特征重要性图
router.get('/importance', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/charts/importance', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

// GET /api/charts/image/:type - 获取图表图片
router.get('/image/:type', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get(`/api/charts/image/${req.params.type}`, req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

export { router as chartsRouter };

// LEGACY: callPythonResilient-based implementation - kept for rollback
// import { Router } from 'express';
// import { callPythonResilient } from '../../../infrastructure/tools/shared/python-caller-resilient-adapter.js';
// import { readFileSync, existsSync } from 'fs';
// const router = Router();
// router.get('/accuracy', async (req, res, next) => {
//   try {
//     const days = req.query.days ? parseInt(req.query.days as string) : 90;
//     const result = await callPythonResilient('plot_model_accuracy_trend', { days });
//     res.json({ success: true, data: result });
//   } catch (error) {
//     next(error);
//   }
// });
// router.get('/equity', async (req, res, next) => {
//   try {
//     const { backtest_result } = req.body;
//     if (!backtest_result) {
//       res.status(400);
//       throw new Error('Missing required parameter: backtest_result');
//     }
//     const result = await callPythonResilient('plot_equity_curve', {
//       backtest_result
//     });
//     res.json({ success: true, data: result });
//   } catch (error) {
//     next(error);
//   }
// });
// router.get('/comparison', async (req, res, next) => {
//   try {
//     const { strategies_performance } = req.body;
//     if (!strategies_performance || !Array.isArray(strategies_performance)) {
//       res.status(400);
//       throw new Error('Missing required parameter: strategies_performance (array)');
//     }
//     const result = await callPythonResilient('plot_strategy_comparison', {
//       strategies_performance
//     });
//     res.json({ success: true, data: result });
//   } catch (error) {
//     next(error);
//   }
// });
// router.get('/importance', async (req, res, next) => {
//   try {
//     const result = await callPythonResilient('plot_feature_importance', {});
//     res.json({ success: true, data: result });
//   } catch (error) {
//     next(error);
//   }
// });
// router.get('/image/:type', (req, res, next) => {
//   try {
//     const { type } = req.params;
//     const validTypes = ['accuracy_trend', 'equity_curve', 'strategy_comparison', 'feature_importance'];
//     if (!validTypes.includes(type)) {
//       res.status(400);
//       throw new Error(`Invalid chart type. Must be one of: ${validTypes.join(', ')}`);
//     }
//     const imagePath = `.pi-invest/quant/charts/${type}.png`;
//     if (!existsSync(imagePath)) {
//       res.status(404);
//       throw new Error('Chart image not found');
//     }
//     const imageBuffer = readFileSync(imagePath);
//     res.contentType('image/png');
//     res.send(imageBuffer);
//   } catch (error) {
//     next(error);
//   }
// });
// export { router as chartsRouter };
