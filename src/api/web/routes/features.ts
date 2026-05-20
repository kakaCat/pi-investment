import { Router } from 'express';
import { FactorAnalysisService } from '../../../services/quant/factor-analysis-service.js';

export const featuresRouter = Router();

const factorService = new FactorAnalysisService();

// GET /api/feature-importance - 获取因子重要性分析
featuresRouter.get('/feature-importance', async (req, res, next) => {
  try {
    const result = await factorService.getFeatureImportance();

    // 转换为前端期望的格式
    res.json({
      features: result.top_features,
      total_features: result.total_features,
      top_20_percent_count: result.top_20_percent_count
    });
  } catch (error) {
    next(error);
  }
});

// GET /api/factor-explanations - 获取因子解释文档
featuresRouter.get('/factor-explanations', (req, res) => {
  const explanations = factorService.getFactorExplanations();
  res.json(explanations);
});
