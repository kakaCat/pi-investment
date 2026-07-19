// src/services/health/startup-health-check.test.ts
import { describe, expect, jest, test } from "@jest/globals";
import {
  runStartupHealthCheck,
  formatHealthForPrompt,
  countMissingWeekdays,
} from "./startup-health-check.js";

const API = "http://127.0.0.1:5001";

/** 构造按 URL 分发的 mock fetch */
function mockFetch(routes: Record<string, { ok: boolean; body: any }>) {
  return (async (url: any) => {
    const u = String(url);
    for (const [pattern, resp] of Object.entries(routes)) {
      if (u.includes(pattern)) {
        return {
          ok: resp.ok,
          status: resp.ok ? 200 : 500,
          json: async () => resp.body,
        } as any;
      }
    }
    throw new Error(`unexpected url: ${u}`);
  }) as any;
}

const healthyRoutes = {
  "/api/health": { ok: true, body: { status: "ok", db_connected: true } },
  "/api/stock/600519/history": {
    ok: true,
    body: { success: true, data: { data: [{ date: "2026-07-17" }] } },
  },
  "/api/scheduler/tasks": {
    ok: true,
    body: { success: true, tasks: [{ enabled: true }, { enabled: true }] },
  },
  "/api/simulation/accounts/default": {
    ok: true,
    body: { success: true, data: { cash: "147070.15", total_value: "147070.15" } },
  },
};

// 2026-07-17 是周五，2026-07-19 是周日
const sunday = () => new Date("2026-07-19T10:00:00+08:00");

describe("countMissingWeekdays", () => {
  test("最新数据为周五、今天是周日 → 缺失 0 个工作日", () => {
    expect(countMissingWeekdays("2026-07-17", new Date("2026-07-19T10:00:00+08:00"))).toBe(0);
  });

  test("最新数据为周五、今天是下周一 → 缺失 1 个工作日", () => {
    expect(countMissingWeekdays("2026-07-17", new Date("2026-07-20T10:00:00+08:00"))).toBe(1);
  });

  test("最新数据为周五、今天是下周三 → 缺失 3 个工作日", () => {
    expect(countMissingWeekdays("2026-07-17", new Date("2026-07-22T10:00:00+08:00"))).toBe(3);
  });

  test("最新数据就是今天 → 缺失 0 个工作日", () => {
    expect(countMissingWeekdays("2026-07-20", new Date("2026-07-20T10:00:00+08:00"))).toBe(0);
  });
});

describe("runStartupHealthCheck", () => {
  test("全部正常时返回 green", async () => {
    const report = await runStartupHealthCheck({
      apiUrl: API,
      fetchFn: mockFetch(healthyRoutes),
      now: sunday,
    });

    expect(report.level).toBe("green");
    expect(report.checks.every((c) => c.status === "ok")).toBe(true);
    expect(report.backendRestarted).toBe(false);
  });

  test("后端宕机 → 自动重启成功 → green 且 backendRestarted=true", async () => {
    let healthCalls = 0;
    const fetchFn = (async (url: any) => {
      const u = String(url);
      if (u.includes("/api/health")) {
        healthCalls++;
        if (healthCalls === 1) throw new Error("connection refused");
        return { ok: true, status: 200, json: async () => ({ status: "ok" }) } as any;
      }
      return mockFetch(healthyRoutes)(url);
    }) as any;

    const restartBackend = jest.fn(async () => true);

    const report = await runStartupHealthCheck({
      apiUrl: API,
      fetchFn,
      restartBackend,
      now: sunday,
    });

    expect(restartBackend).toHaveBeenCalledTimes(1);
    expect(report.backendRestarted).toBe(true);
    expect(report.level).toBe("green");
  });

  test("后端宕机且重启失败 → red，其余检查标记 skipped", async () => {
    const fetchFn = (async () => {
      throw new Error("connection refused");
    }) as any;

    const report = await runStartupHealthCheck({
      apiUrl: API,
      fetchFn,
      restartBackend: async () => false,
      now: sunday,
    });

    expect(report.level).toBe("red");
    const backend = report.checks.find((c) => c.name === "backend_api");
    expect(backend?.status).toBe("fail");
    const others = report.checks.filter((c) => c.name !== "backend_api");
    expect(others.every((c) => c.message.includes("skipped"))).toBe(true);
  });

  test("K线缺失 3 个工作日 → yellow 且 data_freshness 为 warn", async () => {
    const report = await runStartupHealthCheck({
      apiUrl: API,
      fetchFn: mockFetch(healthyRoutes), // latest = 2026-07-17 周五
      now: () => new Date("2026-07-22T10:00:00+08:00"), // 周三
    });

    expect(report.level).toBe("yellow");
    const freshness = report.checks.find((c) => c.name === "data_freshness");
    expect(freshness?.status).toBe("warn");
  });

  test("K线缺失 ≥4 个工作日 → red", async () => {
    const report = await runStartupHealthCheck({
      apiUrl: API,
      fetchFn: mockFetch(healthyRoutes),
      now: () => new Date("2026-07-23T10:00:00+08:00"), // 周四，缺 4 天
    });

    expect(report.level).toBe("red");
  });

  test("账目恒等式被破坏 → red 且 blocking", async () => {
    const routes = {
      ...healthyRoutes,
      "/api/simulation/accounts/default": {
        ok: true,
        body: { success: true, data: { cash: "200000", total_value: "147070.15" } },
      },
    };

    const report = await runStartupHealthCheck({
      apiUrl: API,
      fetchFn: mockFetch(routes),
      now: sunday,
    });

    expect(report.level).toBe("red");
    const portfolio = report.checks.find((c) => c.name === "portfolio_sanity");
    expect(portfolio?.status).toBe("fail");
    expect(portfolio?.blocking).toBe(true);
  });

  test("调度器 0 个启用任务 → yellow", async () => {
    const routes = {
      ...healthyRoutes,
      "/api/scheduler/tasks": {
        ok: true,
        body: { success: true, tasks: [{ enabled: false }] },
      },
    };

    const report = await runStartupHealthCheck({
      apiUrl: API,
      fetchFn: mockFetch(routes),
      now: sunday,
    });

    expect(report.level).toBe("yellow");
    const sched = report.checks.find((c) => c.name === "scheduler");
    expect(sched?.status).toBe("warn");
  });
});

describe("formatHealthForPrompt", () => {
  test("输出包含等级、各检查项状态和阻塞警告", async () => {
    const routes = {
      ...healthyRoutes,
      "/api/simulation/accounts/default": {
        ok: true,
        body: { success: true, data: { cash: "200000", total_value: "147070.15" } },
      },
    };
    const report = await runStartupHealthCheck({
      apiUrl: API,
      fetchFn: mockFetch(routes),
      now: sunday,
    });

    const text = formatHealthForPrompt(report);
    expect(text).toContain("🔴");
    expect(text).toContain("backend_api");
    expect(text).toContain("portfolio_sanity");
    expect(text).toMatch(/禁止.*交易|blocking/i);
  });
});
