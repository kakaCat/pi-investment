// src/infrastructure/tools/tool-reference-check.test.ts
import { describe, expect, test } from "@jest/globals";
import { extractToolRefs, checkToolRefs } from "./tool-reference-check.js";

describe("extractToolRefs 候选工具名提取", () => {
  test("提取反引号包裹的 snake_case 名称", () => {
    const refs = extractToolRefs("使用 `pool_manage` 和 `watch_manage` 两个工具");
    expect(refs).toContain("pool_manage");
    expect(refs).toContain("watch_manage");
  });

  test("提取'使用/调用 X'句式中的工具名", () => {
    const refs = extractToolRefs("- 使用 market_alert 检查预警\n- 调用 decision_record 记录");
    expect(refs).toContain("market_alert");
    expect(refs).toContain("decision_record");
  });

  test("提取调用写法的工具名 X({...})", () => {
    const refs = extractToolRefs("pool_manage({ action: 'list' }) 获取所有池");
    expect(refs).toContain("pool_manage");
  });

  test("忽略普通英文单词和非 snake_case", () => {
    const refs = extractToolRefs("Use the tool carefully. total_value 是字段");
    expect(refs).not.toContain("total_value");
    expect(refs).not.toContain("use");
  });
});

describe("checkToolRefs 注册表比对", () => {
  const registry = new Set(["pool_manage", "watch_manage", "decision_record"]);
  const allowlist = new Set(["total_pnl_pct"]);

  const sources = [
    { path: "skills/a.md", text: "使用 pool_manage 和 pool_list\n`total_pnl_pct` 是字段" },
    { path: "tasks.ts", text: "调用 alert_check 检查" },
  ];

  test("未注册且不在白名单的名字被报告，含来源与行号", () => {
    const issues = checkToolRefs(sources, registry, allowlist);
    const names = issues.map(i => i.name);
    expect(names).toContain("pool_list");
    expect(names).toContain("alert_check");
    expect(names).not.toContain("pool_manage");
    expect(names).not.toContain("total_pnl_pct");
    const poolList = issues.find(i => i.name === "pool_list");
    expect(poolList?.path).toBe("skills/a.md");
    expect(poolList?.line).toBe(1);
  });

  test("同一来源同一名称只报告一次", () => {
    const dup = [{ path: "x.md", text: "使用 ghost_tool\n再次使用 ghost_tool" }];
    const issues = checkToolRefs(dup, registry, allowlist);
    expect(issues.filter(i => i.name === "ghost_tool")).toHaveLength(1);
  });
});
