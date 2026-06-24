import { Router } from 'express';

const router = Router();

// TODO: Implement performance routes
router.get('/summary', (req, res) => {
  res.json({ performance: {} });
});

export default router;
