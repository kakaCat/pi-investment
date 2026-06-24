import { Router } from 'express';

const router = Router();

// TODO: Implement backtest routes
router.post('/run', (req, res) => {
  res.json({ message: 'Backtest endpoint placeholder' });
});

export default router;
