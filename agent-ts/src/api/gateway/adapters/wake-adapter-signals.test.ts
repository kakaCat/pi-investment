import { buildPromptFromEvent } from "./wake-adapter.js";

describe("signals_ready 事件 prompt", () => {
  const data = {
    trade_date: "2026-07-24",
    signal_count: 2,
    signals: [
      { id: 1, symbol: "600519.SH", signal_type: "买入", strength: 85, strategy: "v13" },
      { id: 2, symbol: "000858.SZ", signal_type: "买入", strength: 78, strategy: "v13" },
    ],
    account: "agent_virtual",
  };

  it("包含信号列表和 ID（判重依据）", () => {
    const prompt = buildPromptFromEvent("signals_ready", undefined, undefined, data);
    expect(prompt).toContain("600519.SH");
    expect(prompt).toContain("ID:1");
    expect(prompt).toContain("ID:2");
  });

  it("固定唯一账本 agent_virtual", () => {
    const prompt = buildPromptFromEvent("signals_ready", undefined, undefined, data);
    expect(prompt).toContain("agent_virtual");
  });

  it("包含判重指引（兜底重推不会重复交易）", () => {
    const prompt = buildPromptFromEvent("signals_ready", undefined, undefined, data);
    expect(prompt).toContain("判重");
    expect(prompt).toContain("decision_history");
  });

  it("包含服务端硬护栏说明", () => {
    const prompt = buildPromptFromEvent("signals_ready", undefined, undefined, data);
    expect(prompt).toContain("单日");
  });

  it("0 信号也能生成 prompt", () => {
    const prompt = buildPromptFromEvent("signals_ready", undefined, undefined, {
      trade_date: "2026-07-24",
      signal_count: 0,
      signals: [],
      account: "agent_virtual",
    });
    expect(prompt).toContain("0");
  });
});
