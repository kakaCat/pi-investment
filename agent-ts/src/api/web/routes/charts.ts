import { Router } from 'express';

const router = Router();

// TODO: Implement chart routes
router.get('/data', (req, res) => {
  res.json({ charts: [] });
});

export default router;
