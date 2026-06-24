import { Router } from 'express';

const router = Router();

// TODO: Implement job routes
router.get('/list', (req, res) => {
  res.json({ jobs: [] });
});

export default router;
