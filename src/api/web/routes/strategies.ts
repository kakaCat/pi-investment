import { Router } from 'express';
import { QuantService } from '../../../services/quant/quant-service.js';
import { requireOpsAuth } from '../middleware/ops-auth.js';

const router = Router();
const quantService = new QuantService();

function routeParam(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] : value ?? '';
}

// GET /api/strategies - 列出所有策略
router.get('/', async (req, res, next) => {
  try {
    const strategies = await quantService.listStrategies();
    res.json({ success: true, data: strategies });
  } catch (error) {
    next(error);
  }
});

// GET /api/strategies/:id - 获取单个策略
router.get('/:id', async (req, res, next) => {
  try {
    const strategy = await quantService.getStrategy(routeParam(req.params.id));
    if (!strategy) {
      res.status(404);
      throw new Error('Strategy not found');
    }
    res.json({ success: true, data: strategy });
  } catch (error) {
    next(error);
  }
});

// POST /api/strategies - 创建策略
router.post('/', requireOpsAuth(), async (req, res, next) => {
  try {
    const strategy = await quantService.createStrategy(req.body);
    res.status(201).json({ success: true, data: strategy });
  } catch (error) {
    next(error);
  }
});

// PUT /api/strategies/:id - 更新策略
router.put('/:id', requireOpsAuth(), async (req, res, next) => {
  try {
    const strategy = await quantService.updateStrategy(routeParam(req.params.id), req.body);
    if (!strategy) {
      res.status(404);
      throw new Error('Strategy not found');
    }
    res.json({ success: true, data: strategy });
  } catch (error) {
    next(error);
  }
});

// DELETE /api/strategies/:id - 删除策略
router.delete('/:id', requireOpsAuth(), async (req, res, next) => {
  try {
    const success = await quantService.deleteStrategy(routeParam(req.params.id));
    if (!success) {
      res.status(404);
      throw new Error('Strategy not found');
    }
    res.json({ success: true, message: 'Strategy deleted' });
  } catch (error) {
    next(error);
  }
});

// POST /api/strategies/:id/enable - 启用策略
router.post('/:id/enable', requireOpsAuth(), async (req, res, next) => {
  try {
    const strategy = await quantService.enableStrategy(routeParam(req.params.id));
    if (!strategy) {
      res.status(404);
      throw new Error('Strategy not found');
    }
    res.json({ success: true, data: strategy });
  } catch (error) {
    next(error);
  }
});

// POST /api/strategies/:id/disable - 禁用策略
router.post('/:id/disable', requireOpsAuth(), async (req, res, next) => {
  try {
    const strategy = await quantService.disableStrategy(routeParam(req.params.id));
    if (!strategy) {
      res.status(404);
      throw new Error('Strategy not found');
    }
    res.json({ success: true, data: strategy });
  } catch (error) {
    next(error);
  }
});

export { router as strategiesRouter };
