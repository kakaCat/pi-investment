import { loopGuardianExtension } from "./loop-guardian.js";
import { NUDGE_INTERVAL } from "./loop-guardian-core.js";

type Handler = (event: any) => void;

function createMockPi() {
  const handlers = new Map<string, Handler[]>();
  const sent: Array<{ content: string; deliverAs?: string }> = [];
  const pi = {
    on(event: string, handler: Handler) {
      handlers.set(event, [...(handlers.get(event) ?? []), handler]);
    },
    sendUserMessage(content: string, options?: { deliverAs?: string }) {
      sent.push({ content, deliverAs: options?.deliverAs });
    },
    emit(event: string, payload: any = {}) {
      for (const h of handlers.get(event) ?? []) h({ type: event, ...payload });
    },
    sent,
  };
  return pi;
}

describe("loopGuardianExtension 接线", () => {
  test(`turn_end ×${NUDGE_INTERVAL} → steer 注入一次`, () => {
    const pi = createMockPi();
    loopGuardianExtension(pi as any);
    pi.emit("agent_start");
    for (let i = 0; i < NUDGE_INTERVAL; i++) {
      pi.emit("turn_end", { turnIndex: i, message: {}, toolResults: [{}] });
    }
    expect(pi.sent).toHaveLength(1);
    expect(pi.sent[0].deliverAs).toBe("steer");
    expect(pi.sent[0].content).toContain("停止无新信息的重试");
  });

  test("agent_end 大代码块无工具 → followUp 追问", () => {
    const pi = createMockPi();
    loopGuardianExtension(pi as any);
    pi.emit("agent_start");
    pi.emit("agent_end", {
      messages: [{
        role: "assistant",
        content: [{ type: "text", text: "```python\n" + "x = 1\n".repeat(20) + "```" }],
      }],
    });
    expect(pi.sent).toHaveLength(1);
    expect(pi.sent[0].deliverAs).toBe("followUp");
  });

  test("agent_start 重置状态（新任务重新计数）", () => {
    const pi = createMockPi();
    loopGuardianExtension(pi as any);
    pi.emit("agent_start");
    for (let i = 0; i < NUDGE_INTERVAL; i++) {
      pi.emit("turn_end", { turnIndex: i, message: {}, toolResults: [{}] });
    }
    pi.emit("agent_start"); // 新任务
    for (let i = 0; i < NUDGE_INTERVAL; i++) {
      pi.emit("turn_end", { turnIndex: i, message: {}, toolResults: [{}] });
    }
    expect(pi.sent).toHaveLength(2); // 两个任务各触发一次 R1
  });
});
