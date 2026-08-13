/**
 * Tool Catalog（T8）单元测试
 */
import {
  CORE_TOOL_NAMES,
  getToolCatalog,
  getCoreTools,
  getToolByName,
  searchCatalog,
  describeTool,
  isToolSearchMode,
} from "./catalog.js";
import { allCustomTools } from "./index.js";

describe("tool catalog", () => {
  test("core 集全部存在于注册表（防名单漂移）", () => {
    const registered = new Set(allCustomTools.map((t) => t.name));
    for (const name of CORE_TOOL_NAMES) {
      expect(registered.has(name)).toBe(true);
    }
  });

  test("core 集规模在 15-35 之间（常驻集语义约束）", () => {
    expect(CORE_TOOL_NAMES.size).toBeGreaterThanOrEqual(15);
    expect(CORE_TOOL_NAMES.size).toBeLessThanOrEqual(35);
  });

  test("目录覆盖全量注册表且带 core 标记", () => {
    const catalog = getToolCatalog();
    expect(catalog.length).toBe(allCustomTools.length);
    const coreCount = catalog.filter((e) => e.core).length;
    expect(coreCount).toBe(CORE_TOOL_NAMES.size);
    for (const e of catalog) {
      expect(e.name).toBeTruthy();
      expect(e.summary.length).toBeLessThanOrEqual(83); // 80 + "…"
    }
  });

  test("getCoreTools 保持注册表原顺序", () => {
    const core = getCoreTools();
    const registryOrder = allCustomTools.map((t) => t.name);
    const coreIndices = core.map((t) => registryOrder.indexOf(t.name));
    const sorted = [...coreIndices].sort((a, b) => a - b);
    expect(coreIndices).toEqual(sorted);
  });

  test("searchCatalog：名字精确匹配排第一", () => {
    const hits = searchCatalog("pool_manage");
    expect(hits.length).toBeGreaterThan(0);
    expect(hits[0].name).toBe("pool_manage");
  });

  test("searchCatalog：功能关键词能命中相关工具", () => {
    const hits = searchCatalog("回测");
    expect(hits.length).toBeGreaterThan(0);
    // 回测相关工具应在结果中
    const names = hits.map((h) => h.name);
    expect(names.some((n) => n.includes("backtest") || n.includes("strategy"))).toBe(true);
  });

  test("searchCatalog：空查询返回空", () => {
    expect(searchCatalog("")).toEqual([]);
    expect(searchCatalog("   ")).toEqual([]);
  });

  test("searchCatalog：无匹配返回空数组", () => {
    expect(searchCatalog("zzz_nonexistent_zzz")).toEqual([]);
  });

  test("getToolByName / describeTool 契约", () => {
    const tool = getToolByName("data_fetch_quote");
    expect(tool).toBeDefined();
    const info = describeTool("data_fetch_quote");
    expect(info).toBeDefined();
    expect(info!.name).toBe("data_fetch_quote");
    expect(info!.parameters).toBeDefined();
    expect(info!.core).toBe(true);

    const nonCore = describeTool("pool_validate");
    expect(nonCore).toBeDefined();
    expect(nonCore!.core).toBe(false);

    expect(getToolByName("nonexistent_tool")).toBeUndefined();
    expect(describeTool("nonexistent_tool")).toBeUndefined();
  });

  test("isToolSearchMode 默认开，PI_TOOL_SEARCH=off 关闭", () => {
    delete process.env.PI_TOOL_SEARCH;
    expect(isToolSearchMode()).toBe(true);
    process.env.PI_TOOL_SEARCH = "off";
    expect(isToolSearchMode()).toBe(false);
    delete process.env.PI_TOOL_SEARCH;
  });
});
