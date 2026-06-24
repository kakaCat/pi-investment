import { Router } from 'express';

const router = Router();

// TODO: Implement training routes
router.post('/start', (req, res) => {
  res.json({ message: 'Training endpoint placeholder' });
});

export default router;
