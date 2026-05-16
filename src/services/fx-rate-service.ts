import { readFileSync, writeFileSync, existsSync } from "fs";
import { join } from "path";
import { fetchSinaFxRate } from "../infrastructure/data-sources/sina-fx.js";

export interface FxRatesFile {
  rates: {
    [pair: string]: {
      rate: number;
      date: string;
      updated_at: string;
      source: string;
    };
  };
  last_updated: string;
}

export class FxRateService {
  private cachePath: string;

  constructor(piDir: string) {
    this.cachePath = join(piDir, "fx-rates.json");
    this.ensureCache();
  }

  private ensureCache(): void {
    if (!existsSync(this.cachePath)) {
      const empty: FxRatesFile = {
        rates: {},
        last_updated: ""
      };
      writeFileSync(this.cachePath, JSON.stringify(empty, null, 2), "utf-8");
    }
  }

  private loadCache(): FxRatesFile {
    try {
      const content = readFileSync(this.cachePath, "utf-8");
      return JSON.parse(content) as FxRatesFile;
    } catch (error) {
      return { rates: {}, last_updated: "" };
    }
  }

  private saveCache(data: FxRatesFile): void {
    writeFileSync(this.cachePath, JSON.stringify(data, null, 2), "utf-8");
  }

  async fetchRateFromSina(pair: "HKDCNY"): Promise<number> {
    return fetchSinaFxRate(pair);
  }
}
