import { Router } from 'express';

const router = Router();

// TODO: Implement platform routes
router.get('/status', (req, res) => {
  res.json({ status: 'running' });
});

export default router;
