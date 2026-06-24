import { Router } from 'express';

export const strategiesRouter = Router();

// TODO: Implement strategies routes
strategiesRouter.get('/', (req, res) => {
  res.json({ message: 'Strategies route - not implemented' });
});
