/**
 * Decision Record Tool 测试
 *
 * 覆盖链路三（agent 操作 → 落库 → web 展示）的写路径：
 * agent 通过该工具把决策记录 POST 到 v2 /api/decisions/record
 */
import { decisionRecordTool } from "./decision-record-tool.js";

const mockFetch = jest.fn();
(global as any).fetch = mockFetch;

describe("decisionRecordTool", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("POST /api/decisions/record 并返回决策ID", async () => {
    mockFetch.mockResolvedValue({
      json: async () => ({
        success: true,
        data: { decision_id: "dec_123", decision_type: "create_pool" },
      }),
    });

    const result = await decisionRecordTool.execute("call-1", {
      decision_type: "create_pool",
      reasoning: "散户恐慌抛售，创建抄底池",
      context: { market_phase: "panic" },
      parameters: { name: "恐慌抄底池" },
      related_entity_type: "pool",
      related_entity_id: "5",
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/decisions/record");
    expect(options.method).toBe("POST");
    const body = JSON.parse(options.body);
    expect(body.decision_type).toBe("create_pool");
    expect(body.reasoning).toBe("散户恐慌抛售，创建抄底池");
    expect(body.context).toEqual({ market_phase: "panic" });
    expect(body.related_entity_id).toBe("5");

    expect((result.content[0] as any).text).toContain("dec_123");
    expect((result.details as any).decision_id).toBe("dec_123");
  });

  it("后端返回失败时返回错误信息", async () => {
    mockFetch.mockResolvedValue({
      json: async () => ({ success: false, error: "decision_type 必填" }),
    });

    const result = await decisionRecordTool.execute("call-2", {
      decision_type: "create_pool",
      reasoning: "test",
    });

    expect((result.content[0] as any).text).toContain("❌");
    expect((result.content[0] as any).text).toContain("decision_type 必填");
    expect(result.details).toBeNull();
  });

  it("网络异常时返回错误信息而不抛出", async () => {
    mockFetch.mockRejectedValue(new Error("fetch failed"));

    const result = await decisionRecordTool.execute("call-3", {
      decision_type: "refresh_pool",
      reasoning: "test",
    });

    expect((result.content[0] as any).text).toContain("❌");
    expect((result.content[0] as any).text).toContain("fetch failed");
    expect(result.details).toBeNull();
  });

  it("有会话上下文时自动携带 session_key", async () => {
    const { setSessionContext, resetSessionEventState } = await import("../../../api/gateway/session-events.js");
    setSessionContext("agent:main:wake:default", "/tmp/x");

    mockFetch.mockResolvedValue({
      json: async () => ({ success: true, data: { decision_id: "dec_9" } }),
    });

    await decisionRecordTool.execute("call-4", {
      decision_type: "refresh_pool",
      reasoning: "定时刷新",
    });

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.session_key).toBe("agent:main:wake:default");
    resetSessionEventState();
  });
});
