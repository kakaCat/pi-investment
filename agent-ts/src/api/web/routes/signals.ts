import { Router } from 'express';

const router = Router();

// TODO: Implement signal routes
router.get('/list', (req, res) => {
  res.json({ signals: [] });
});

export default router;
