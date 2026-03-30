import { describe, expect, test } from "@jest/globals";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { StockDecisionMemoryService } from "./stock-decision-memory-service.js";

function makeRootDir(): string {
  return mkdtempSync(join(tmpdir(), "pi-invest-stock-decision-memory-"));
}

describe("StockDecisionMemoryService", () => {
  test("loads existing stock decision markdown from per-symbol files", () => {
    const rootDir = makeRootDir();
    const stocksDir = join(rootDir, ".pi-invest", "memory", "stocks");
    const existingContent = "# 600519\n\n## 2026-03-30\n- 回调到 5 日线再考虑加仓\n";

    mkdirSync(stocksDir, { recursive: true });
    writeFileSync(join(stocksDir, "600519.md"), existingContent, "utf-8");

    const service = new StockDecisionMemoryService(rootDir);

    expect(service.get("600519")).toBe(existingContent);
    expect(service.get("000001")).toBeNull();
  });

  test("ignores invalid markdown path entries when loading stock memory files", () => {
    const rootDir = makeRootDir();
    const stocksDir = join(rootDir, ".pi-invest", "memory", "stocks");

    mkdirSync(join(stocksDir, "archive.md"), { recursive: true });
    writeFileSync(join(stocksDir, "600519.md"), "# 600519\n\n## 2026-03-30\n- 继续持有\n", "utf-8");

    const service = new StockDecisionMemoryService(rootDir);

    expect(service.get("600519")).toContain("继续持有");
  });

  test("writes stock decision markdown to .pi-invest/memory/stocks/{symbol}.md", () => {
    const rootDir = makeRootDir();
    const service = new StockDecisionMemoryService(rootDir);
    const content = "# 002415\n\n## 2026-03-30\n- 维持观察，等待放量突破\n";
    const filePath = join(rootDir, ".pi-invest", "memory", "stocks", "002415.md");

    service.save("002415", content);

    expect(service.get("002415")).toBe(content);
    expect(existsSync(filePath)).toBe(true);
    expect(readFileSync(filePath, "utf-8")).toBe(content);
  });

  test("appends decision sections for the same symbol and reloads them from disk", () => {
    const rootDir = makeRootDir();
    const service = new StockDecisionMemoryService(rootDir);

    service.append("600519", "## 2026-03-30\n- 首次建仓 10%");
    service.append("600519", "## 2026-03-31\n- 不追高，等回踩确认");

    const saved = service.get("600519");
    const reloaded = new StockDecisionMemoryService(rootDir);

    expect(saved).toContain("## 2026-03-30\n- 首次建仓 10%");
    expect(saved).toContain("## 2026-03-31\n- 不追高，等回踩确认");
    expect(saved).toContain("\n\n## 2026-03-31");
    expect(reloaded.get("600519")).toBe(saved);
  });
});
