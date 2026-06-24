import { Router } from 'express';

const router = Router();

// TODO: Implement feature routes
router.get('/list', (req, res) => {
  res.json({ features: [] });
});

export default router;
