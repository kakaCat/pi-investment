/**
 * Scheduler Manage Tool - 字段映射回归测试
 *
 * 历史 bug：v2 API 返回 scheduleExpr/nextRunAt/payload.command，
 * 工具却读 cron/command/run_count，导致列表显示 undefined/0，
 * 曾据此误判"调度器形同虚设"。
 */
import { describe, expect, test } from "@jest/globals";
import {
  normalizeSchedulerTask,
  formatTaskList,
} from "./scheduler-manage-tool.js";

// 真实 v2 API 响应形态（/api/scheduler/tasks?pageSize=100）
const apiTask = {
  id: "232",
  name: "每日数据质量检查",
  enabled: true,
  scheduleExpr: "0 0 * * *",
  scheduleKind: "cron",
  nextRunAt: "2026-07-20 08:00:00+08:00",
  createdAt: "2026-06-04 12:40:09.067549+08:00",
  updatedAt: "2026-07-19 08:07:46+08:00",
  todayTriggered: true,
  todaySuccess: true,
  payload: { command: "data_quality_check", days: 365 },
  lastRun: {
    status: "success",
    finishedAt: "2026-07-19 08:07:46.167100+08:00",
    error: null,
  },
};

describe("normalizeSchedulerTask", () => {
  test("enterprise API 字段映射为显示模型", () => {
    const t = normalizeSchedulerTask(apiTask);

    expect(t.id).toBe("232");
    expect(t.name).toBe("每日数据质量检查");
    expect(t.cron).toBe("0 0 * * *");
    expect(t.command).toBe("data_quality_check");
    expect(t.enabled).toBe(true);
    expect(t.next_run).toBe("2026-07-20 08:00:00+08:00");
    expect(t.last_run_at).toBe("2026-07-19 08:07:46.167100+08:00");
    expect(t.last_run_status).toBe("success");
    expect(t.today_triggered).toBe(true);
  });

  test("兼容 snake_case 老字段（cron / next_run）", () => {
    const t = normalizeSchedulerTask({
      id: "1",
      name: "x",
      cron: "0 9 * * *",
      command: "data_update",
      enabled: false,
      next_run: "2026-07-20 09:00:00",
    });

    expect(t.cron).toBe("0 9 * * *");
    expect(t.command).toBe("data_update");
    expect(t.enabled).toBe(false);
  });

  test("缺失字段时 cron/command 为空字符串而非 undefined", () => {
    const t = normalizeSchedulerTask({ id: "3", name: "y" });
    expect(t.cron).toBe("");
    expect(t.command).toBe("");
    expect(t.last_run_status).toBeNull();
  });
});

describe("formatTaskList", () => {
  test("列表展示 cron/下次执行/上次执行，不出现 undefined", () => {
    const text = formatTaskList({
      tasks: [normalizeSchedulerTask(apiTask)],
      total: 1,
    });

    expect(text).toContain("0 0 * * *");
    expect(text).toContain("2026-07-20");
    expect(text).toContain("2026-07-19");
    expect(text).not.toContain("undefined");
    expect(text).not.toContain("` `"); // 空的 cron 反引号
  });

  test("上次执行失败时标记 ❌", () => {
    const failed = normalizeSchedulerTask({
      ...apiTask,
      lastRun: { status: "failed", finishedAt: "2026-07-19 08:00:00+08:00", error: "boom" },
    });
    const text = formatTaskList({ tasks: [failed], total: 1 });
    expect(text).toContain("❌");
  });
});
