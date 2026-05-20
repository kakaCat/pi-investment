import fs from 'fs/promises';
import path from 'path';
import { randomUUID } from 'crypto';
import { QuantStrategy } from './types';
import { runQuantCli } from '../../infrastructure/quant/quant-cli-client.js';

export interface UpdateDataRequest {
  source: 'portfolio' | 'watchlist' | 'hs300' | 'all';
  days: number;
  async?: boolean;
  force?: boolean;
  symbols?: string[];
}

export interface UpdateDataResponse {
  success: boolean;
  source: string;
  days: number;
  total?: number;
  updated?: number;
  skipped?: number;
  failed?: number;
  details?: unknown[];
  stdout?: string;
  stderr?: string;
}

export interface AsyncJobResponse {
  success: boolean;
  job_id: string;
  message: string;
}

export class QuantService {
  private storageDir: string;

  constructor(storageDir: string = '.pi-invest/quant/strategies') {
    this.storageDir = storageDir;
  }

  async createStrategy(input: Omit<QuantStrategy, 'id' | 'created_at'>): Promise<QuantStrategy> {
    await fs.mkdir(this.storageDir, { recursive: true });

    const id = `strategy_${randomUUID()}`;
    const strategy: QuantStrategy = {
      ...input,
      id,
      created_at: new Date().toISOString(),
    };

    const filePath = path.join(this.storageDir, `${id}.json`);
    await fs.writeFile(filePath, JSON.stringify(strategy, null, 2), 'utf-8');

    return strategy;
  }

  async listStrategies(): Promise<QuantStrategy[]> {
    try {
      await fs.access(this.storageDir);
    } catch {
      return [];
    }

    const files = await fs.readdir(this.storageDir);
    const jsonFiles = files.filter(f => f.endsWith('.json'));

    const strategies: QuantStrategy[] = [];
    for (const file of jsonFiles) {
      try {
        const filePath = path.join(this.storageDir, file);
        const content = await fs.readFile(filePath, 'utf-8');
        strategies.push(JSON.parse(content));
      } catch (error) {
        console.warn(`Failed to parse strategy file ${file}:`, error);
      }
    }

    return strategies.sort((a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }

  async getStrategy(id: string): Promise<QuantStrategy | null> {
    const filePath = path.join(this.storageDir, `${id}.json`);

    try {
      const content = await fs.readFile(filePath, 'utf-8');
      const parsed = JSON.parse(content);
      if (!parsed.id || !parsed.created_at) {
        console.warn(`Invalid strategy format in ${id}.json`);
        return null;
      }
      return parsed;
    } catch (error) {
      console.debug(`Strategy ${id} not found or invalid:`, error);
      return null;
    }
  }

  async updateStrategy(id: string, updates: Partial<Omit<QuantStrategy, 'id' | 'created_at'>>): Promise<QuantStrategy | null> {
    const existing = await this.getStrategy(id);
    if (!existing) {
      return null;
    }

    const updated: QuantStrategy = {
      ...existing,
      ...updates,
      id: existing.id,
      created_at: existing.created_at,
    };

    const filePath = path.join(this.storageDir, `${id}.json`);
    await fs.writeFile(filePath, JSON.stringify(updated, null, 2), 'utf-8');

    return updated;
  }

  async deleteStrategy(id: string): Promise<boolean> {
    const filePath = path.join(this.storageDir, `${id}.json`);

    try {
      await fs.unlink(filePath);
      return true;
    } catch {
      return false;
    }
  }

  async enableStrategy(id: string): Promise<QuantStrategy | null> {
    return this.updateStrategy(id, { enabled: true });
  }

  async disableStrategy(id: string): Promise<QuantStrategy | null> {
    return this.updateStrategy(id, { enabled: false });
  }

  /**
   * 统一数据更新 - 委托给 QuantSys CLI
   */
  async updateStockData(params: UpdateDataRequest): Promise<UpdateDataResponse | AsyncJobResponse> {
    const response = await runQuantCli<{ stdout?: string; stderr?: string }>('data', 'update-klines', {
      days: params.days,
      symbols: params.symbols,
    });

    return {
      success: true,
      source: params.source,
      days: params.days,
      stdout: response.data?.stdout,
      stderr: response.data?.stderr,
    };
  }
}
