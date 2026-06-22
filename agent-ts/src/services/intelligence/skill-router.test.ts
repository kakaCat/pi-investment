import { beforeEach, describe, expect, test } from "@jest/globals";
import { detectForcedSkill, initSkillRouter, rewritePromptWithSkill } from "./skill-router.js";

describe("skill-router", () => {
  beforeEach(() => {
    initSkillRouter([
      { name: "deep-analysis" },
      { name: "market-analysis" },
      { name: "portfolio" },
      { name: "portfolio-review" },
      { name: "stock-screener" },
      { name: "risk-manager" },
      { name: "candlestick-analysis" },
      { name: "add-holding" },
      { name: "add-trade" },
    ] as any);
  });

  test("routes single-stock analysis to deep-analysis", () => {
    expect(detectForcedSkill("分析一下中粮糖业的股票")).toBe("deep-analysis");
  });

  test("routes plain stock analysis phrasing to deep-analysis", () => {
    expect(detectForcedSkill("分析一下中粮糖业")).toBe("deep-analysis");
  });

  test("routes market questions to market-analysis", () => {
    expect(detectForcedSkill("现在市场怎么样，适合加仓吗")).toBe("market-analysis");
  });

  test("routes holdings overview to portfolio", () => {
    expect(detectForcedSkill("看下我现在的持仓")).toBe("portfolio");
  });

  test("routes holdings review to portfolio-review", () => {
    expect(detectForcedSkill("帮我复盘一下持仓，顺便给点调仓建议")).toBe("portfolio-review");
  });

  test("routes stock selection requests to stock-screener", () => {
    expect(detectForcedSkill("帮我找白酒板块值得买的股票")).toBe("stock-screener");
  });

  test("routes risk requests to risk-manager", () => {
    expect(detectForcedSkill("这笔仓位应该怎么分配，止损放哪里")).toBe("risk-manager");
  });

  test("routes candlestick questions to candlestick-analysis", () => {
    expect(detectForcedSkill("看看这根K线是不是锤子线")).toBe("candlestick-analysis");
  });

  test("routes explicit trade logging to add-trade", () => {
    expect(detectForcedSkill("帮我记录交易，我卖了茅台100股")).toBe("add-trade");
  });

  test("routes holding updates to add-holding", () => {
    expect(detectForcedSkill("帮我录入持仓，茅台100股均价1450")).toBe("add-holding");
  });

  test("does not rewrite generic concept questions", () => {
    expect(detectForcedSkill("什么是市盈率")).toBeNull();
  });

  test("does not rewrite explicit slash commands", () => {
    expect(rewritePromptWithSkill("/skill:portfolio 看持仓")).toEqual({
      prompt: "/skill:portfolio 看持仓",
      forcedSkill: null,
    });
  });

  test("rewrites matched prompts into skill commands", () => {
    expect(rewritePromptWithSkill("分析一下中粮糖业的股票")).toEqual({
      prompt: "/skill:deep-analysis 分析一下中粮糖业的股票",
      forcedSkill: "deep-analysis",
    });
  });
});
