import { Router } from 'express';
import { PythonBackendClient } from '../../../services/python/python-backend-client.js';

export const featuresRouter = Router();

// GET /api/feature-importance - 获取因子重要性分析
featuresRouter.get('/feature-importance', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/feature-importance', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

// GET /api/factor-explanations - 获取因子解释文档
featuresRouter.get('/factor-explanations', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/factor-explanations', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

// LEGACY: FactorAnalysisService-based implementation - kept for rollback
// import { Router } from 'express';
// import { FactorAnalysisService } from '../../../services/quant/factor-analysis-service.js';
// export const featuresRouter = Router();
// const factorService = new FactorAnalysisService();
// featuresRouter.get('/feature-importance', async (req, res, next) => {
//   try {
//     const result = await factorService.getFeatureImportance();
//     res.json({
//       features: result.top_features,
//       total_features: result.total_features,
//       top_20_percent_count: result.top_20_percent_count
//     });
//   } catch (error) {
//     next(error);
//   }
// });
// featuresRouter.get('/factor-explanations', (req, res) => {
//   const explanations = factorService.getFactorExplanations();
//   res.json(explanations);
// });
