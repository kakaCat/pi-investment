import { config } from "dotenv";
import { createSchedulerPgPool } from "../services/scheduler/postgres-client.js";
import { PostgresSchedulerStore } from "../services/scheduler/postgres-scheduler-store.js";
import type { SchedulerTask } from "../services/scheduler/scheduler-service.js";

config();

const now = new Date().toISOString();

const tasks: SchedulerTask[] = [
  {
    id: "ipo-watch",
    name: "每日打新检查",
    enabled: true,
    scheduleKind: "cron",
    scheduleExpr: "30 8 * * 1-5",
    payload: { kind: "ipo_watch" },
    compensationEnabled: true,
    compensationCheckAfter: "09:30",
    compensationMaxAttempts: 1,
    deleteAfterRun: false,
    createdAt: now,
    updatedAt: now,
  },
  {
    id: "daily-review",
    name: "每日持仓复盘",
    enabled: true,
    scheduleKind: "cron",
    scheduleExpr: "35 15 * * 1-5",
    payload: { kind: "daily_review" },
    compensationEnabled: true,
    compensationCheckAfter: "16:00",
    compensationMaxAttempts: 1,
    deleteAfterRun: false,
    createdAt: now,
    updatedAt: now,
  },
  {
    id: "update-fx-rates",
    name: "更新汇率缓存",
    enabled: true,
    scheduleKind: "cron",
    scheduleExpr: "0 9 * * 1-5",
    payload: { kind: "system_event", message: "update_fx_rates" },
    compensationEnabled: true,
    compensationCheckAfter: "10:00",
    compensationMaxAttempts: 1,
    deleteAfterRun: false,
    createdAt: now,
    updatedAt: now,
  },
];

async function main() {
  const pool = createSchedulerPgPool();
  const store = new PostgresSchedulerStore(pool);
  await store.migrate();

  for (const task of tasks) {
    const existing = await store.getTask(task.id);
    if (existing) {
      await store.updateTask(task.id, {
        ...task,
        createdAt: existing.createdAt,
        updatedAt: now,
      });
      console.log(`updated ${task.id}`);
    } else {
      await store.createTask(task);
      console.log(`created ${task.id}`);
    }
  }

  await pool.end();
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
