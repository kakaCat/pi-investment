import { Router } from 'express';

const router = Router();

// TODO: Implement stock routes
router.get('/list', (req, res) => {
  res.json({ stocks: [] });
});

export default router;
