import { Router } from 'express';

export const signalsRouter = Router();
export const backtestRouter = Router();
export const performanceRouter = Router();
export const chartsRouter = Router();
export const stocksRouter = Router();
export const featuresRouter = Router();
export const trainingRouter = Router();
export const jobsRouter = Router();
export const platformRouter = Router();
export const schedulerRouter = Router();
export const pipelineRouter = Router();

// TODO: Implement all routes - placeholder for now
signalsRouter.get('/', (req, res) => res.json({ message: 'Not implemented' }));
backtestRouter.get('/', (req, res) => res.json({ message: 'Not implemented' }));
performanceRouter.get('/', (req, res) => res.json({ message: 'Not implemented' }));
chartsRouter.get('/', (req, res) => res.json({ message: 'Not implemented' }));
stocksRouter.get('/', (req, res) => res.json({ message: 'Not implemented' }));
featuresRouter.get('/', (req, res) => res.json({ message: 'Not implemented' }));
trainingRouter.get('/', (req, res) => res.json({ message: 'Not implemented' }));
jobsRouter.get('/', (req, res) => res.json({ message: 'Not implemented' }));
platformRouter.get('/', (req, res) => res.json({ message: 'Not implemented' }));
schedulerRouter.get('/', (req, res) => res.json({ message: 'Not implemented' }));
pipelineRouter.get('/', (req, res) => res.json({ message: 'Not implemented' }));
