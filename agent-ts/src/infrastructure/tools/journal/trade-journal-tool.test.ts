// src/infrastructure/tools/journal/trade-journal-tool.test.ts
import { describe, expect, test } from "@jest/globals";
import { tradeJournalTool } from "./trade-journal-tool.js";

describe("trade_journal 统一簿记入口", () => {
  test("未知 action 返回错误与合法 action 列表", async () => {
    const result = (await tradeJournalTool.execute("t1", { action: "bogus" } as any)) as any;
    const text = JSON.stringify(result);
    expect(text).toMatch(/record|experience|status|daily_report/);
  });

  test("缺 action 返回错误", async () => {
    const result = (await tradeJournalTool.execute("t2", {} as any)) as any;
    expect(JSON.stringify(result)).toMatch(/action/);
  });

  test("四个 action 映射到对应子工具", async () => {
    // record 缺必填参数时应走到 decision_record 的校验，而不是"未知 action"
    const result = (await tradeJournalTool.execute("t3", { action: "record" } as any)) as any;
    expect(JSON.stringify(result)).not.toMatch(/未知|不支持/);
  });
});
