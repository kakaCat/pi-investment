import { Router } from 'express';

const router = Router();

// TODO: Implement pipeline routes
router.get('/status', (req, res) => {
  res.json({ pipelines: [] });
});

export default router;
