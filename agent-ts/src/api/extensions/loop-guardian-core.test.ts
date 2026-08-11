import {
  createGuardianState,
  evaluateTurnEnd,
  NUDGE_INTERVAL,
  FILE_CHECKPOINT_INTERVAL,
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
