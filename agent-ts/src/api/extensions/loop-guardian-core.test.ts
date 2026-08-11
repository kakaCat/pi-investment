import {
  createGuardianState,
  evaluateTurnEnd,
  evaluateToolCall,
  evaluateAgentEnd,
  NUDGE_INTERVAL,
  FILE_CHECKPOINT_INTERVAL,
  REPEAT_CALL_THRESHOLD,
  HARD_TURN_LIMIT,
  type Intervention,
} from "./loop-guardian-core.js";

describe("R1/R2 轮次纠偏", () => {
  test("普通轮次不干预", () => {
    const s = createGuardianState();
    s.turnCount = 5;
    expect(evaluateTurnEnd(s)).toEqual([]);
  });

  test(`turn=${NUDGE_INTERVAL} 触发 R1 steer`, () => {
    const s = createGuardianState();
    s.turnCount = NUDGE_INTERVAL;
    const out = evaluateTurnEnd(s);
    expect(out).toHaveLength(1);
    const iv = out[0];
    expect(iv.kind).toBe("steer");
    if (iv.kind === "steer") expect(iv.text).toContain("停止无新信息的重试");
  });

  test("同一档位不重复触发", () => {
    const s = createGuardianState();
    s.turnCount = NUDGE_INTERVAL;
    evaluateTurnEnd(s); // 第一次，消费掉
    expect(evaluateTurnEnd(s)).toEqual([]); // 同档位不再发
  });

  test(`turn=${FILE_CHECKPOINT_INTERVAL} 触发 R2 写文件提示`, () => {
    const s = createGuardianState();
    s.turnCount = FILE_CHECKPOINT_INTERVAL;
    const out = evaluateTurnEnd(s);
    expect(out.some(i => i.kind === "steer" && i.text.includes("写入文件"))).toBe(true);
  });
});

describe("R3 重复调用检测", () => {
  test(`同 tool+args 连续 ${REPEAT_CALL_THRESHOLD} 次触发 steer`, () => {
    const s = createGuardianState();
    let out: Intervention[] = [];
    for (let i = 0; i < REPEAT_CALL_THRESHOLD; i++) {
      out = evaluateToolCall(s, "data_fetch_quote", { symbol: "600519" });
    }
    expect(out).toHaveLength(1);
    const iv = out[0];
    expect(iv.kind).toBe("steer");
    if (iv.kind === "steer") expect(iv.text).toContain("data_fetch_quote");
  });

  test("同 tool 不同 args 不触发", () => {
    const s = createGuardianState();
    let out: Intervention[] = [];
    for (let i = 0; i < REPEAT_CALL_THRESHOLD; i++) {
      out = evaluateToolCall(s, "data_fetch_quote", { symbol: `60051${i}` });
    }
    expect(out).toEqual([]);
  });

  test("R3 触发后不重复刷屏", () => {
    const s = createGuardianState();
    for (let i = 0; i < REPEAT_CALL_THRESHOLD + 1; i++) {
      evaluateToolCall(s, "data_fetch_quote", { symbol: "600519" });
    }
    const out = evaluateToolCall(s, "data_fetch_quote", { symbol: "600519" });
    expect(out).toEqual([]);
  });
});

describe("R4 硬上限", () => {
  test(`turn=${HARD_TURN_LIMIT} 触发 notify + steer 两个动作`, () => {
    const s = createGuardianState();
    s.turnCount = HARD_TURN_LIMIT;
    const out = evaluateTurnEnd(s);
    expect(out.some(i => i.kind === "notify")).toBe(true);
    expect(out.some(i => i.kind === "steer" && i.text.includes("收尾"))).toBe(true);
  });

  test("硬上限每任务只触发一次", () => {
    const s = createGuardianState();
    s.turnCount = HARD_TURN_LIMIT;
    evaluateTurnEnd(s);
    s.turnCount = HARD_TURN_LIMIT + NUDGE_INTERVAL; // 更高档位仍不再发 R4
    const out = evaluateTurnEnd(s);
    expect(out.some(i => i.kind === "notify")).toBe(false);
  });
});

describe("R5/R6 agent_end 检查", () => {
  test("R5: 0 工具 + 单个大代码块结尾 → followUp", () => {
    const s = createGuardianState(); // toolCallCount = 0
    const text = "分析如下：\n```python\n" + "x = 1\n".repeat(20) + "```";
    const out = evaluateAgentEnd(s, text);
    expect(out).toHaveLength(1);
    const iv = out[0];
    expect(iv.kind).toBe("followUp");
    if (iv.kind === "followUp") expect(iv.text).toContain("未调用任何工具");
  });

  test("R5: 代码块后有大段解释 → 不触发", () => {
    const s = createGuardianState();
    const text = "```python\n" + "x = 1\n".repeat(20) + "```\n以上代码仅供你参考，"
      + "这是详细的说明文字，超过三十个字符的解释内容，不需要执行。";
    expect(evaluateAgentEnd(s, text)).toEqual([]);
  });

  test("R5: 本周期调过工具 → 不触发", () => {
    const s = createGuardianState();
    s.toolCallCount = 2;
    const text = "```python\n" + "x = 1\n".repeat(20) + "```";
    expect(evaluateAgentEnd(s, text)).toEqual([]);
  });

  test("R5 防追问循环：每任务最多追问一次", () => {
    const s = createGuardianState();
    const text = "```python\n" + "x = 1\n".repeat(20) + "```";
    evaluateAgentEnd(s, text); // 第一次追问
    expect(evaluateAgentEnd(s, text)).toEqual([]); // 第二次放行
  });

  test("R6: 空回复 → followUp", () => {
    const s = createGuardianState();
    const out = evaluateAgentEnd(s, "   ");
    expect(out).toHaveLength(1);
    expect(out[0].kind).toBe("followUp");
  });
});
