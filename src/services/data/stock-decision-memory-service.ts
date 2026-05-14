import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "fs";
import { join } from "path";

export class StockDecisionMemoryService {
  private readonly stocksDir: string;
  private readonly memories = new Map<string, string>();

  constructor(rootDir = process.cwd()) {
    this.stocksDir = join(rootDir, ".pi-invest", "memory", "stocks");
    this.load();
  }

  get(symbol: string): string | null {
    return this.memories.get(symbol) ?? null;
  }

  save(symbol: string, content: string): void {
    mkdirSync(this.stocksDir, { recursive: true });
    writeFileSync(this.getFilePath(symbol), content, "utf-8");
    this.memories.set(symbol, content);
  }

  append(symbol: string, section: string): string {
    const existing = this.get(symbol);
    const nextContent = existing
      ? `${existing.trimEnd()}\n\n${section.trim()}`
      : `# ${symbol}\n\n${section.trim()}\n`;

    this.save(symbol, nextContent.endsWith("\n") ? nextContent : `${nextContent}\n`);
    return this.memories.get(symbol)!;
  }

  private load(): void {
    if (!existsSync(this.stocksDir)) return;

    for (const fileName of readdirSync(this.stocksDir)) {
      if (!fileName.endsWith(".md")) continue;

      const filePath = join(this.stocksDir, fileName);

      try {
        if (!statSync(filePath).isFile()) continue;

        const symbol = fileName.slice(0, -3);
        const content = readFileSync(filePath, "utf-8");
        this.memories.set(symbol, content);
      } catch {
        continue;
      }
    }
  }

  private getFilePath(symbol: string): string {
    return join(this.stocksDir, `${symbol}.md`);
  }
}

export const stockDecisionMemoryService = new StockDecisionMemoryService();
