/**
 * Bootstrap Loader - 加载 .pi-invest/ 目录下的 Bootstrap 文件
 *
 * 启动时加载 agent 的配置文件，支持三种模式：
 * - full: 主 agent，加载所有文件
 * - minimal: 子 agent / cron，只加载核心文件
 * - none: 最小化，不加载任何文件
 */
import { readFileSync, existsSync } from "fs";
import { join } from "path";

export const BOOTSTRAP_FILES = [
  "SOUL.md",
  "IDENTITY.md",
  "TOOLS.md",
  "MEMORY.md",
  "USER.md",
  "BOOTSTRAP.md",
  "PORTFOLIO.md",
  "AGENTS.md",
  "HEARTBEAT.md",
];

const MAX_FILE_CHARS = 20000;
const MAX_TOTAL_CHARS = 150000;

export class BootstrapLoader {
  private bootstrapDir: string;

  constructor(piDir: string) {
    this.bootstrapDir = join(piDir, "bootstrap");
  }

  loadFile(name: string): string {
    const path = join(this.bootstrapDir, name);
    if (!existsSync(path)) return "";
    try {
      const raw = readFileSync(path, "utf-8");
      // Strip leading HTML comment block used as file header metadata
      return raw.replace(/^<!--[\s\S]*?-->\s*/m, "");
    } catch {
      return "";
    }
  }

  truncateFile(content: string, maxChars = MAX_FILE_CHARS): string {
    if (content.length <= maxChars) return content;
    const cut = content.lastIndexOf("\n", maxChars);
    const pos = cut > 0 ? cut : maxChars;
    return content.slice(0, pos) + `\n\n[... truncated (${content.length} chars total, showing first ${pos}) ...]`;
  }

  loadAll(mode: "full" | "minimal" | "none" = "full"): Record<string, string> {
    if (mode === "none") return {};
    const names = mode === "minimal"
      ? ["AGENTS.md", "TOOLS.md"]
      : [...BOOTSTRAP_FILES];

    const result: Record<string, string> = {};
    let total = 0;

    for (const name of names) {
      const raw = this.loadFile(name);
      if (!raw) continue;
      let truncated = this.truncateFile(raw);
      if (total + truncated.length > MAX_TOTAL_CHARS) {
        const remaining = MAX_TOTAL_CHARS - total;
        if (remaining <= 0) break;
        truncated = this.truncateFile(raw, remaining);
      }
      result[name] = truncated;
      total += truncated.length;
    }

    return result;
  }
}
