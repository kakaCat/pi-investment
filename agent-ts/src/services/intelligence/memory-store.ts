/**
 * Memory Store - 跨会话持久化记忆系统
 *
 * 两层存储：
 * - MEMORY.md: 长期事实（手动维护）
 * - memory/daily/{date}.jsonl: 每日日志（agent 工具自动写入）
 *
 * 搜索：TF-IDF + 向量模拟 + MMR 重排，纯 Node.js 实现
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from "fs";
import { join } from "path";
import { chinaDate } from "../../utils/china-time.js";

export interface MemoryChunk {
  path: string;
  text: string;
}

export interface MemoryResult {
  path: string;
  score: number;
  snippet: string;
}

export class MemoryStore {
  private memoryDir: string;

  constructor(private piDir: string) {
    this.memoryDir = join(piDir, "memory", "daily");
    mkdirSync(this.memoryDir, { recursive: true });
  }

  // -------------------------------------------------------------------------
  // 写入
  // -------------------------------------------------------------------------

  writeMemory(content: string, category = "general"): string {
    const today = chinaDate();
    const path = join(this.memoryDir, `${today}.jsonl`);
    const entry = {
      ts: new Date().toISOString(),
      category,
      content,
    };
    try {
      const line = JSON.stringify(entry) + "\n";
      writeFileSync(path, line, { flag: "a", encoding: "utf-8" });
      return `Memory saved to ${today}.jsonl [${category}]`;
    } catch (e) {
      return `Error writing memory: ${e}`;
    }
  }

  loadEvergreen(): string {
    const path = join(this.piDir, "MEMORY.md");
    if (!existsSync(path)) return "";
    try {
      return readFileSync(path, "utf-8").trim();
    } catch {
      return "";
    }
  }

  // -------------------------------------------------------------------------
  // 加载所有记忆块
  // -------------------------------------------------------------------------

  private loadAllChunks(): MemoryChunk[] {
    const chunks: MemoryChunk[] = [];

    const evergreen = this.loadEvergreen();
    if (evergreen) {
      for (const para of evergreen.split("\n\n")) {
        const t = para.trim();
        if (t) chunks.push({ path: "MEMORY.md", text: t });
      }
    }

    if (existsSync(this.memoryDir)) {
      const files = readdirSync(this.memoryDir)
        .filter(f => f.endsWith(".jsonl"))
        .sort();
      for (const file of files) {
        try {
          const lines = readFileSync(join(this.memoryDir, file), "utf-8").split("\n");
          for (const line of lines) {
            const l = line.trim();
            if (!l) continue;
            const entry = JSON.parse(l);
            const text = entry.content || "";
            if (text) {
              const label = entry.category ? `${file} [${entry.category}]` : file;
              chunks.push({ path: label, text });
            }
          }
        } catch {
          continue;
        }
      }
    }

    return chunks;
  }

  // -------------------------------------------------------------------------
  // TF-IDF 关键词搜索
  // -------------------------------------------------------------------------

  private static tokenize(text: string): string[] {
    const tokens = text.toLowerCase().match(/[a-z0-9\u4e00-\u9fff]+/g) || [];
    return tokens.filter(t => t.length > 1 || /[\u4e00-\u9fff]/.test(t));
  }

  private keywordSearch(query: string, chunks: MemoryChunk[], topK = 10): Array<{ chunk: MemoryChunk; score: number }> {
    const queryTokens = MemoryStore.tokenize(query);
    if (!queryTokens.length) return [];

    const chunkTokens = chunks.map(c => MemoryStore.tokenize(c.text));
    const n = chunks.length;
    const df: Record<string, number> = {};
    for (const tokens of chunkTokens) {
      for (const t of new Set(tokens)) {
        df[t] = (df[t] || 0) + 1;
      }
    }

    const tfidf = (tokens: string[]): Record<string, number> => {
      const tf: Record<string, number> = {};
      for (const t of tokens) tf[t] = (tf[t] || 0) + 1;
      const result: Record<string, number> = {};
      for (const [t, c] of Object.entries(tf)) {
        result[t] = c * (Math.log((n + 1) / ((df[t] || 0) + 1)) + 1);
      }
      return result;
    };

    const cosine = (a: Record<string, number>, b: Record<string, number>): number => {
      const common = Object.keys(a).filter(k => k in b);
      if (!common.length) return 0;
      const dot = common.reduce((s, k) => s + a[k] * b[k], 0);
      const na = Math.sqrt(Object.values(a).reduce((s, v) => s + v * v, 0));
      const nb = Math.sqrt(Object.values(b).reduce((s, v) => s + v * v, 0));
      return na && nb ? dot / (na * nb) : 0;
    };

    const qvec = tfidf(queryTokens);
    const scored: Array<{ chunk: MemoryChunk; score: number }> = [];
    for (let i = 0; i < chunks.length; i++) {
      if (!chunkTokens[i].length) continue;
      const score = cosine(qvec, tfidf(chunkTokens[i]));
      if (score > 0) scored.push({ chunk: chunks[i], score });
    }
    return scored.sort((a, b) => b.score - a.score).slice(0, topK);
  }

  // -------------------------------------------------------------------------
  // 模拟向量搜索（hash projection）
  // -------------------------------------------------------------------------

  private static hashVector(text: string, dim = 64): number[] {
    const tokens = MemoryStore.tokenize(text);
    const vec = new Array(dim).fill(0);
    for (const token of tokens) {
      let h = 0;
      for (let i = 0; i < token.length; i++) {
        h = Math.imul(31, h) + token.charCodeAt(i) | 0;
      }
      for (let i = 0; i < dim; i++) {
        vec[i] += ((h >> (i % 30)) & 1) ? 1 : -1;
      }
    }
    const norm = Math.sqrt(vec.reduce((s, v) => s + v * v, 0)) || 1;
    return vec.map(v => v / norm);
  }

  private static vectorCosine(a: number[], b: number[]): number {
    const dot = a.reduce((s, v, i) => s + v * b[i], 0);
    const na = Math.sqrt(a.reduce((s, v) => s + v * v, 0));
    const nb = Math.sqrt(b.reduce((s, v) => s + v * v, 0));
    return na && nb ? dot / (na * nb) : 0;
  }

  private vectorSearch(query: string, chunks: MemoryChunk[], topK = 10): Array<{ chunk: MemoryChunk; score: number }> {
    const qvec = MemoryStore.hashVector(query);
    const scored = chunks.map(chunk => ({
      chunk,
      score: MemoryStore.vectorCosine(qvec, MemoryStore.hashVector(chunk.text)),
    })).filter(r => r.score > 0);
    return scored.sort((a, b) => b.score - a.score).slice(0, topK);
  }

  // -------------------------------------------------------------------------
  // 合并 + 时间衰减 + MMR 重排
  // -------------------------------------------------------------------------

  private static mergeResults(
    vector: Array<{ chunk: MemoryChunk; score: number }>,
    keyword: Array<{ chunk: MemoryChunk; score: number }>,
    vw = 0.7,
    kw = 0.3,
  ): Array<{ chunk: MemoryChunk; score: number }> {
    const merged = new Map<string, { chunk: MemoryChunk; score: number }>();
    for (const r of vector) {
      const key = r.chunk.text.slice(0, 100);
      merged.set(key, { chunk: r.chunk, score: r.score * vw });
    }
    for (const r of keyword) {
      const key = r.chunk.text.slice(0, 100);
      const existing = merged.get(key);
      if (existing) existing.score += r.score * kw;
      else merged.set(key, { chunk: r.chunk, score: r.score * kw });
    }
    return [...merged.values()].sort((a, b) => b.score - a.score);
  }

  private static temporalDecay(
    results: Array<{ chunk: MemoryChunk; score: number }>,
    decayRate = 0.01,
  ): Array<{ chunk: MemoryChunk; score: number }> {
    const now = Date.now();
    return results.map(r => {
      const match = r.chunk.path.match(/(\d{4}-\d{2}-\d{2})/);
      let ageDays = 0;
      if (match) {
        const d = new Date(match[1]).getTime();
        ageDays = (now - d) / 86400000;
      }
      return { ...r, score: r.score * Math.exp(-decayRate * ageDays) };
    });
  }

  private static mmrRerank(
    results: Array<{ chunk: MemoryChunk; score: number }>,
    lambda = 0.7,
  ): Array<{ chunk: MemoryChunk; score: number }> {
    if (results.length <= 1) return results;
    const tokenized = results.map(r => new Set(MemoryStore.tokenize(r.chunk.text)));
    const selected: number[] = [];
    const remaining = results.map((_, i) => i);
    const reranked: Array<{ chunk: MemoryChunk; score: number }> = [];

    while (remaining.length) {
      let bestIdx = -1;
      let bestMmr = -Infinity;
      for (const idx of remaining) {
        const relevance = results[idx].score;
        let maxSim = 0;
        for (const selIdx of selected) {
          const a = tokenized[idx];
          const b = tokenized[selIdx];
          const inter = [...a].filter(t => b.has(t)).length;
          const union = new Set([...a, ...b]).size;
          const sim = union ? inter / union : 0;
          if (sim > maxSim) maxSim = sim;
        }
        const mmr = lambda * relevance - (1 - lambda) * maxSim;
        if (mmr > bestMmr) { bestMmr = mmr; bestIdx = idx; }
      }
      selected.push(bestIdx);
      remaining.splice(remaining.indexOf(bestIdx), 1);
      reranked.push(results[bestIdx]);
    }
    return reranked;
  }

  // -------------------------------------------------------------------------
  // 公开接口
  // -------------------------------------------------------------------------

  hybridSearch(query: string, topK = 5): MemoryResult[] {
    const chunks = this.loadAllChunks();
    if (!chunks.length) return [];

    const keyword = this.keywordSearch(query, chunks, 10);
    const vector = this.vectorSearch(query, chunks, 10);
    const merged = MemoryStore.mergeResults(vector, keyword);
    const decayed = MemoryStore.temporalDecay(merged);
    const reranked = MemoryStore.mmrRerank(decayed);

    return reranked.slice(0, topK).map(r => ({
      path: r.chunk.path,
      score: Math.round(r.score * 10000) / 10000,
      snippet: r.chunk.text.length > 200 ? r.chunk.text.slice(0, 200) + "..." : r.chunk.text,
    }));
  }

  getStats(): { evergreenChars: number; dailyFiles: number; dailyEntries: number } {
    const evergreen = this.loadEvergreen();
    let dailyFiles = 0;
    let dailyEntries = 0;
    if (existsSync(this.memoryDir)) {
      const files = readdirSync(this.memoryDir).filter(f => f.endsWith(".jsonl"));
      dailyFiles = files.length;
      for (const file of files) {
        try {
          const lines = readFileSync(join(this.memoryDir, file), "utf-8").split("\n");
          dailyEntries += lines.filter(l => l.trim()).length;
        } catch { continue; }
      }
    }
    return { evergreenChars: evergreen.length, dailyFiles, dailyEntries };
  }
}

// -------------------------------------------------------------------------
// 单例管理
// -------------------------------------------------------------------------

let memoryStore: MemoryStore;

export function initMemoryStore(piDir: string): void {
  memoryStore = new MemoryStore(piDir);
}

export function getMemoryStore(): MemoryStore {
  if (!memoryStore) throw new Error("MemoryStore not initialized. Call initMemoryStore() first.");
  return memoryStore;
}
