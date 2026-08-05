/**
 * 会话启动健康自检
 *
 * Agent 每次启动时执行四项检查：
 *   1. backend_api      — quantsys-v2 REST API 心跳（宕机时尝试自动重启一次）
 *   2. data_freshness   — K线数据新鲜度（按缺失工作日数分级）
 *   3. scheduler        — v2 调度器任务状态（启用任务数）
 *   4. portfolio_sanity — 虚拟仓账目恒等式（破坏时阻塞交易）
 *
 * 结果同时用于：
 *   - 终端打印（人类可见）
 *   - formatHealthForPrompt 注入系统提示词 Runtime 层（Agent 自知）
 */

export type HealthStatus = "ok" | "warn" | "fail";
export type HealthLevel = "green" | "yellow" | "red";

export interface HealthCheckItem {
  name: "backend_api" | "data_freshness" | "scheduler" | "portfolio_sanity";
  status: HealthStatus;
  message: string;
  /** true = 该项异常时禁止交易操作 */
  blocking?: boolean;
}

export interface StartupHealthReport {
  level: HealthLevel;
  startedAt: string;
  durationMs: number;
  backendRestarted: boolean;
  checks: HealthCheckItem[];
}

export interface StartupHealthOptions {
  apiUrl: string;
  fetchFn?: typeof fetch;
  /** 后端宕机时的重启函数，返回是否重启成功。不提供则不尝试重启 */
  restartBackend?: () => Promise<boolean>;
  now?: () => Date;
  /** 用于探测数据新鲜度的参照股票，默认 600519 */
  klineSymbol?: string;
  /** 单请求超时毫秒，默认 3000 */
  timeoutMs?: number;
}

const DEFAULT_TIMEOUT = 3000;

/** 统计 latestDate（含）之后到 today（含）之间缺失的工作日数 */
export function countMissingWeekdays(latestDate: string, today: Date): number {
  const latest = new Date(latestDate + "T00:00:00");
  if (Number.isNaN(latest.getTime())) return 999;

  let count = 0;
  const cursor = new Date(latest);
  cursor.setDate(cursor.getDate() + 1); // 从最新数据的下一天开始数

  const end = new Date(today);
  end.setHours(0, 0, 0, 0);

  while (cursor <= end) {
    const dow = cursor.getDay();
    if (dow !== 0 && dow !== 6) count++;
    cursor.setDate(cursor.getDate() + 1);
  }
  return count;
}

async function fetchJson(
  fetchFn: typeof fetch,
  url: string,
  timeoutMs: number
): Promise<any> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetchFn(url, { signal: controller.signal } as any);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } finally {
    clearTimeout(timer);
  }
}

async function checkBackend(
  fetchFn: typeof fetch,
  apiUrl: string,
  timeoutMs: number,
  restartBackend?: () => Promise<boolean>
): Promise<{ item: HealthCheckItem; restarted: boolean }> {
  const probe = async () => {
    const body = await fetchJson(fetchFn, `${apiUrl}/api/health`, timeoutMs);
    return body?.status === "ok";
  };

  try {
    if (await probe()) {
      return {
        item: { name: "backend_api", status: "ok", message: "REST API 正常" },
        restarted: false,
      };
    }
    throw new Error("health status not ok");
  } catch (err: any) {
    // 第一次探测失败 → 尝试自动重启
    if (restartBackend) {
      const restarted = await restartBackend().catch(() => false);
      if (restarted) {
        try {
          if (await probe()) {
            return {
              item: {
                name: "backend_api",
                status: "ok",
                message: "REST API 异常后已自动重启恢复",
              },
              restarted: true,
            };
          }
        } catch {
          /* fall through */
        }
      }
    }
    return {
      item: {
        name: "backend_api",
        status: "fail",
        message: `REST API 不可用: ${err?.message ?? err}`,
        blocking: true,
      },
      restarted: false,
    };
  }
}

async function checkDataFreshness(
  fetchFn: typeof fetch,
  apiUrl: string,
  symbol: string,
  today: Date,
  timeoutMs: number
): Promise<HealthCheckItem> {
  try {
    const body = await fetchJson(
      fetchFn,
      `${apiUrl}/api/stock/${symbol}/history?limit=1`,
      timeoutMs
    );
    const rows = body?.data?.data ?? body?.data ?? [];
    const latest: string | undefined = Array.isArray(rows) ? rows[0]?.date : undefined;
    if (!latest) {
      return {
        name: "data_freshness",
        status: "fail",
        message: `无法获取 ${symbol} K线数据`,
      };
    }
    const missing = countMissingWeekdays(latest, today);
    if (missing <= 1) {
      return {
        name: "data_freshness",
        status: "ok",
        message: `K线最新至 ${latest}（缺失 ${missing} 个工作日）`,
      };
    }
    if (missing <= 3) {
      return {
        name: "data_freshness",
        status: "warn",
        message: `K线停留在 ${latest}，缺失 ${missing} 个工作日`,
      };
    }
    return {
      name: "data_freshness",
      status: "fail",
      message: `K线严重滞后：停留在 ${latest}，缺失 ${missing} 个工作日`,
    };
  } catch (err: any) {
    return {
      name: "data_freshness",
      status: "fail",
      message: `K线检查失败: ${err?.message ?? err}`,
    };
  }
}

async function checkScheduler(
  fetchFn: typeof fetch,
  apiUrl: string,
  timeoutMs: number
): Promise<HealthCheckItem> {
  try {
    const body = await fetchJson(
      fetchFn,
      `${apiUrl}/api/scheduler/tasks?pageSize=100`,
      timeoutMs
    );
    const tasks: any[] = body?.tasks ?? body?.data?.items ?? [];
    const enabled = tasks.filter((t) => t.enabled).length;
    if (enabled > 0) {
      return {
        name: "scheduler",
        status: "ok",
        message: `调度器 ${enabled}/${tasks.length} 任务启用`,
      };
    }
    return {
      name: "scheduler",
      status: "warn",
      message: `调度器 ${tasks.length} 个任务全部禁用`,
    };
  } catch (err: any) {
    return {
      name: "scheduler",
      status: "fail",
      message: `调度器检查失败: ${err?.message ?? err}`,
    };
  }
}

async function checkPortfolioSanity(
  fetchFn: typeof fetch,
  apiUrl: string,
  timeoutMs: number
): Promise<HealthCheckItem> {
  try {
    const body = await fetchJson(
      fetchFn,
      `${apiUrl}/api/simulation/accounts/default`,
      timeoutMs
    );
    const data = body?.data ?? body;
    const cash = Number(data?.cash ?? data?.cash_available ?? data?.cashAvailable);
    const totalValue = Number(data?.total_value ?? data?.totalValue);

    if (!Number.isFinite(cash) || !Number.isFinite(totalValue)) {
      return {
        name: "portfolio_sanity",
        status: "warn",
        message: "虚拟仓字段缺失，无法校验恒等式",
      };
    }
    // total_value 语义 = 总资产（含现金）。恒等式：total_value >= cash（持仓市值 >= 0）
    if (cash < 0 || totalValue < cash - 0.01) {
      return {
        name: "portfolio_sanity",
        status: "fail",
        message: `账目不平：cash=${cash}, total_value=${totalValue}，禁止交易`,
        blocking: true,
      };
    }
    return {
      name: "portfolio_sanity",
      status: "ok",
      message: `账目正常（现金 ¥${cash.toFixed(2)}）`,
    };
  } catch (err: any) {
    return {
      name: "portfolio_sanity",
      status: "warn",
      message: `虚拟仓检查跳过: ${err?.message ?? err}`,
    };
  }
}

export async function runStartupHealthCheck(
  options: StartupHealthOptions
): Promise<StartupHealthReport> {
  const {
    apiUrl,
    fetchFn = fetch,
    restartBackend,
    now = () => new Date(),
    klineSymbol = "600519",
    timeoutMs = DEFAULT_TIMEOUT,
  } = options;

  const startedAt = now();
  const checks: HealthCheckItem[] = [];

  // 1. 后端心跳（含自动重启）
  const backend = await checkBackend(fetchFn, apiUrl, timeoutMs, restartBackend);
  checks.push(backend.item);

  if (backend.item.status === "fail") {
    // 后端不可用 → 其余检查无法执行
    for (const name of ["data_freshness", "scheduler", "portfolio_sanity"] as const) {
      checks.push({ name, status: "fail", message: "skipped: backend unavailable" });
    }
  } else {
    // 2-4. 并行执行其余检查
    const [freshness, scheduler, portfolio] = await Promise.all([
      checkDataFreshness(fetchFn, apiUrl, klineSymbol, now(), timeoutMs),
      checkScheduler(fetchFn, apiUrl, timeoutMs),
      checkPortfolioSanity(fetchFn, apiUrl, timeoutMs),
    ]);
    checks.push(freshness, scheduler, portfolio);
  }

  const level: HealthLevel = checks.some((c) => c.status === "fail")
    ? "red"
    : checks.some((c) => c.status === "warn")
      ? "yellow"
      : "green";

  const report: StartupHealthReport = {
    level,
    startedAt: startedAt.toISOString(),
    durationMs: now().getTime() - startedAt.getTime(),
    backendRestarted: backend.restarted,
    checks,
  };
  lastReport = report;
  return report;
}

let lastReport: StartupHealthReport | null = null;

/** 最近一次自检结果（供系统提示词注入使用） */
export function getLastHealthReport(): StartupHealthReport | null {
  return lastReport;
}

const LEVEL_ICON: Record<HealthLevel, string> = {
  green: "🟢",
  yellow: "🟡",
  red: "🔴",
};

const STATUS_ICON: Record<HealthStatus, string> = {
  ok: "✅",
  warn: "⚠️",
  fail: "❌",
};

const LEVEL_LABEL: Record<HealthLevel, string> = {
  green: "全部正常",
  yellow: "降级运行",
  red: "存在阻塞",
};

/** 格式化为系统提示词 Runtime 层文本 */
export function formatHealthForPrompt(report: StartupHealthReport): string {
  const lines = report.checks.map(
    (c) => `- ${STATUS_ICON[c.status]} ${c.name}: ${c.message}`
  );
  const blocking = report.checks.filter((c) => c.blocking && c.status === "fail");
  if (blocking.length > 0) {
    lines.push(
      `- 🚫 阻塞项（blocking）: ${blocking.map((c) => c.name).join(", ")} — 修复前禁止交易类操作`
    );
  }
  if (report.backendRestarted) {
    lines.push("- ♻️ 后端曾在启动时宕机，已自动重启恢复");
  }
  return (
    `[系统健康: ${LEVEL_ICON[report.level]} ${LEVEL_LABEL[report.level]}]\n` +
    lines.join("\n")
  );
}

/** 格式化为终端打印文本 */
export function formatHealthForConsole(report: StartupHealthReport): string {
  const header =
    `\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
    `🏥 启动健康自检 ${LEVEL_ICON[report.level]} ${LEVEL_LABEL[report.level]}（耗时 ${report.durationMs}ms）\n` +
    `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`;
  const lines = report.checks.map(
    (c) => `  ${STATUS_ICON[c.status]} ${c.name}: ${c.message}`
  );
  return header + "\n" + lines.join("\n") + "\n";
}
