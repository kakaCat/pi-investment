import { Router } from 'express';

const router = Router();

// TODO: Implement scheduler routes
router.get('/tasks', (req, res) => {
  res.json({ tasks: [] });
});

export default router;
