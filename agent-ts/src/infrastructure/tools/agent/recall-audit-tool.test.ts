import { beforeEach, describe, expect, jest, test } from "@jest/globals";

// Mock fetch globally
const mockFetch = jest.fn<typeof fetch>();
global.fetch = mockFetch as any;

const { recallAuditTool } = await import("./recall-audit-tool.js");

describe("recall_audit tool", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("list action", () => {
    test("查询审计日志（无筛选）", async () => {
      const mockResponse = {
        items: [
          {
            id: 1,
            ts: "2026-08-13T10:00:00+00:00",
            session_id: "s-test",
            flow: "chat",
            gate_result: "injected",
            hits: [{ memory_id: 101, score: 0.85 }],
          },
        ],
        total: 1,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await (recallAuditTool.execute as any)("test-call", {
        action: "list",
      });

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const callUrl = (mockFetch.mock.calls[0] as any)[0];
      expect(callUrl).toContain("/api/memory/recall-audit");

      const content0 = result.content[0];
      if (content0.type === "text") {
        const parsed = JSON.parse(content0.text);
        expect(parsed.total).toBe(1);
        expect(parsed.items[0].id).toBe(1);
      }
    });

    test("使用 flow 和 gate_result 筛选", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [], total: 0 }),
      } as Response);

      await (recallAuditTool.execute as any)("test-call", {
        action: "list",
        flow: "chat",
        gate_result: "suppressed",
        page: 2,
        page_size: 10,
      });

      const callUrl = (mockFetch.mock.calls[0] as any)[0];
      expect(callUrl).toContain("flow=chat");
      expect(callUrl).toContain("gate_result=suppressed");
      expect(callUrl).toContain("page=2");
      expect(callUrl).toContain("page_size=10");
    });

    test("使用日期范围筛选", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [], total: 0 }),
      } as Response);

      await (recallAuditTool.execute as any)("test-call", {
        action: "list",
        date_from: "2026-08-01",
        date_to: "2026-08-31",
      });

      const callUrl = (mockFetch.mock.calls[0] as any)[0];
      expect(callUrl).toContain("date_from=2026-08-01");
      expect(callUrl).toContain("date_to=2026-08-31");
    });

    test("HTTP 错误时抛出异常", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: async () => "Internal Server Error",
      } as Response);

      const result = await (recallAuditTool.execute as any)("test-call", {
        action: "list",
      });

      const content0 = result.content[0];
      if (content0.type === "text") {
        expect(content0.text).toContain("Error");
        expect(content0.text).toContain("500");
      }
    });
  });

  describe("stats action", () => {
    test("查询统计信息", async () => {
      const mockStats = {
        total: 10,
        injected: 7,
        suppressed: 3,
        injection_rate: 0.7,
        by_flow: {
          chat: { total: 8, injected: 6, suppressed: 2 },
          watch: { total: 2, injected: 1, suppressed: 1 },
        },
        suppress_reasons: {
          low_score: 2,
          duplicate: 1,
        },
        score_histogram: [
          { bucket: "0.0-0.1", count: 1 },
          { bucket: "0.8-0.9", count: 5 },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStats,
      } as Response);

      const result = await (recallAuditTool.execute as any)("test-call", {
        action: "stats",
      });

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const callUrl = (mockFetch.mock.calls[0] as any)[0];
      expect(callUrl).toContain("/api/memory/recall-audit/stats");

      const content0 = result.content[0];
      if (content0.type === "text") {
        const parsed = JSON.parse(content0.text);
        expect(parsed.total).toBe(10);
        expect(parsed.injection_rate).toBe(0.7);
      }
    });

    test("使用日期范围查询统计", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          total: 0,
          injected: 0,
          suppressed: 0,
          injection_rate: 0,
        }),
      } as Response);

      await (recallAuditTool.execute as any)("test-call", {
        action: "stats",
        date_from: "2026-08-01",
        date_to: "2026-08-31",
      });

      const callUrl = (mockFetch.mock.calls[0] as any)[0];
      expect(callUrl).toContain("date_from=2026-08-01");
      expect(callUrl).toContain("date_to=2026-08-31");
    });
  });

  describe("feedback action", () => {
    test("提交 agent 反馈", async () => {
      const mockFeedbackResponse = {
        hits: [
          {
            memory_id: 101,
            score: 0.85,
            feedback: "relevant",
            feedback_by: "agent",
            feedback_at: "2026-08-13T10:30:00+00:00",
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockFeedbackResponse,
      } as Response);

      const result = await (recallAuditTool.execute as any)("test-call", {
        action: "feedback",
        audit_id: 123,
        memory_id: 101,
        feedback: "relevant",
      });

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0] as any;
      expect(url).toContain("/api/memory/recall-audit/123/feedback");
      expect(options.method).toBe("POST");

      const body = JSON.parse(options.body);
      expect(body.memory_id).toBe(101);
      expect(body.feedback).toBe("relevant");
      expect(body.feedback_by).toBe("agent"); // 硬编码

      const content0 = result.content[0];
      if (content0.type === "text") {
        expect(content0.text).toContain("Feedback recorded");
        expect(content0.text).toContain("relevant");
        expect(content0.text).toContain("101");
      }
    });

    test("缺少 audit_id 时报错", async () => {
      const result = await (recallAuditTool.execute as any)("test-call", {
        action: "feedback",
        memory_id: 101,
        feedback: "relevant",
      });

      const content0 = result.content[0];
      if (content0.type === "text") {
        expect(content0.text).toContain("audit_id is required");
      }
    });

    test("缺少 memory_id 时报错", async () => {
      const result = await (recallAuditTool.execute as any)("test-call", {
        action: "feedback",
        audit_id: 123,
        feedback: "relevant",
      });

      const content0 = result.content[0];
      if (content0.type === "text") {
        expect(content0.text).toContain("memory_id is required");
      }
    });

    test("缺少 feedback 时报错", async () => {
      const result = await (recallAuditTool.execute as any)("test-call", {
        action: "feedback",
        audit_id: 123,
        memory_id: 101,
      });

      const content0 = result.content[0];
      if (content0.type === "text") {
        expect(content0.text).toContain("feedback is required");
      }
    });

    test("HTTP 409 冲突时抛出异常（agent 不能覆盖 human）", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 409,
        text: async () => "Cannot overwrite human feedback",
      } as Response);

      const result = await (recallAuditTool.execute as any)("test-call", {
        action: "feedback",
        audit_id: 123,
        memory_id: 101,
        feedback: "relevant",
      });

      const content0 = result.content[0];
      if (content0.type === "text") {
        expect(content0.text).toContain("409");
      }
    });
  });
});
