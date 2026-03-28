import fs from 'fs/promises';
import path from 'path';
import { QuantStrategy } from './types';

export class QuantService {
  private strategiesDir = '.pi-invest/quant/strategies';

  async createStrategy(strategy: Omit<QuantStrategy, 'id' | 'created_at'>): Promise<QuantStrategy> {
    const id = `strategy_${Date.now()}`;
    const fullStrategy: QuantStrategy = {
      ...strategy,
      id,
      created_at: new Date().toISOString(),
    };

    await fs.mkdir(this.strategiesDir, { recursive: true });
    await fs.writeFile(
      path.join(this.strategiesDir, `${id}.json`),
      JSON.stringify(fullStrategy, null, 2)
    );

    return fullStrategy;
  }

  async listStrategies(): Promise<QuantStrategy[]> {
    try {
      const files = await fs.readdir(this.strategiesDir);
      const strategies = await Promise.all(
        files
          .filter(f => f.endsWith('.json'))
          .map(async f => {
            const content = await fs.readFile(path.join(this.strategiesDir, f), 'utf-8');
            return JSON.parse(content) as QuantStrategy;
          })
      );
      return strategies.sort((a, b) => b.created_at.localeCompare(a.created_at));
    } catch {
      return [];
    }
  }

  async getStrategy(id: string): Promise<QuantStrategy | null> {
    try {
      const content = await fs.readFile(
        path.join(this.strategiesDir, `${id}.json`),
        'utf-8'
      );
      return JSON.parse(content);
    } catch {
      return null;
    }
  }

  async deleteStrategy(id: string): Promise<boolean> {
    try {
      await fs.unlink(path.join(this.strategiesDir, `${id}.json`));
      return true;
    } catch {
      return false;
    }
  }

  async updateStrategy(id: string, updates: Partial<QuantStrategy>): Promise<QuantStrategy | null> {
    const strategy = await this.getStrategy(id);
    if (!strategy) return null;

    const updated = { ...strategy, ...updates, id, created_at: strategy.created_at };
    await fs.writeFile(
      path.join(this.strategiesDir, `${id}.json`),
      JSON.stringify(updated, null, 2)
    );
    return updated;
  }
}
