/**
 * Tool Search 元工具三件套（T8）单元测试
 */
import {
  toolSearchTool,
  toolDescribeTool,
  toolCallTool,
  toolSearchMetaTools,
} from "./tool-search-tools.js";
import { allCustomTools } from "../index.js";

const call = async (tool: any, params: any) => {
  const result = await tool.execute("test-call-id", params, undefined, undefined);
  return {
    text: result.content.map((c: any) => c.text).join("\n"),
    details: result.details,
  };
};

describe("tool_search meta tools", () => {
  test("三件套不注册进 allCustomTools（防自检索/自调用递归）", () => {
    const registered = new Set(allCustomTools.map((t) => t.name));
    for (const meta of toolSearchMetaTools) {
      expect(registered.has(meta.name)).toBe(false);
    }
  });

  test("tool_search 返回匹配列表与后续指引", async () => {
    const r = await call(toolSearchTool, { query: "pool" });
    expect(r.text).toContain("pool_manage");
    expect(r.text).toContain("tool_describe");
    expect(r.details.found).toBeGreaterThan(0);
  });

  test("tool_search 无匹配时给换词建议", async () => {
    const r = await call(toolSearchTool, { query: "zzz_nothing_zzz" });
    expect(r.text).toContain("未找到");
    expect(r.details.found).toBe(0);
  });

  test("tool_describe 返回完整 schema", async () => {
    const r = await call(toolDescribeTool, { name: "pool_validate" });
    expect(r.text).toContain("pool_validate");
    expect(r.text).toContain("参数 schema");
    expect(r.details.core).toBe(false);
  });

  test("tool_describe 未知名报错并引导 search", async () => {
    const r = await call(toolDescribeTool, { name: "nope_tool" });
    expect(r.text).toContain("不存在");
    expect(r.details.error).toBe("unknown_tool");
  });

  test("tool_call 拒绝元工具自递归", async () => {
    for (const name of ["tool_search", "tool_describe", "tool_call"]) {
      const r = await call(toolCallTool, { name, args: {} });
      expect(r.details.error).toBe("meta_tool_recursion");
    }
  });

  test("tool_call 未知名给近似建议", async () => {
    const r = await call(toolCallTool, { name: "pool_manag", args: {} });
    expect(r.details.error).toBe("unknown_tool");
    expect(r.details.suggestions).toContain("pool_manage");
  });

  test("tool_call 缺必填参数时拦截并报缺失", async () => {
    // data_fetch_quote 的 required 含 symbol（core 工具也可经 tool_call 调用，参数校验同理）
    const quote = allCustomTools.find((t) => t.name === "data_fetch_quote") as any;
    const required = quote.parameters.required ?? [];
    expect(required.length).toBeGreaterThan(0);
    const r = await call(toolCallTool, { name: "data_fetch_quote", args: {} });
    expect(r.details.error).toBe("missing_args");
    expect(r.details.missing).toEqual(required);
  });

  test("tool_call 真实调用目标工具并透传结果", async () => {
    // 用 task_list（纯本地、无副作用）验证端到端调用
    const r = await call(toolCallTool, { name: "task_list", args: {} });
    expect(r.text.length).toBeGreaterThan(0);
    expect(r.details?.error).toBeUndefined();
  });
});
