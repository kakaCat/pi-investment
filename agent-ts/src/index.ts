/**
 * PI Investment - AI 股票投资顾问
 * Entry point
 */
import "./infrastructure/tui/pi-tui-compat.js";
import "./api/index.js";
import { initAgentDecisionTasks } from "./services/scheduler/init-agent-tasks.js";

// 注意：调度器已迁移到 quantsys-v2
// Agent 只保留 AI 决策任务，通过 agent_turn 类型执行
// 数据处理任务由 quantsys-v2 的调度器自主完成

// 初始化 Agent AI 决策任务到数据库
console.log("🤖 正在初始化 Agent AI 决策任务...");
initAgentDecisionTasks()
  .then(() => {
    console.log("✅ Agent AI 决策任务初始化完成");
  })
  .catch((err) => {
    console.error("❌ Agent AI 任务初始化失败:", err);
  });
