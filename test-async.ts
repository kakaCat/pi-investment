/**
 * 测试异步任务执行系统
 */
import { BackgroundTaskManager } from "./src/core/task/background-task-manager.js";

async function test() {
  console.log("🧪 测试异步任务系统\n");

  const bgManager = new BackgroundTaskManager(10000); // 10秒超时

  // 模拟启动3个并行任务
  console.log("📤 启动3个后台任务...");

  const task1 = await bgManager.run(1, "get_stock_info", { symbol: "600519" });
  console.log(`  ${task1}`);

  const task2 = await bgManager.run(2, "get_stock_info", { symbol: "000858" });
  console.log(`  ${task2}`);

  const task3 = await bgManager.run(3, "get_stock_info", { symbol: "601318" });
  console.log(`  ${task3}\n`);

  // 检查运行状态
  console.log("📊 当前运行中的任务数:", bgManager.getRunningCount());
  console.log("\n📋 所有任务状态:");
  console.log(bgManager.check());

  // 等待任务完成
  console.log("\n⏳ 等待任务完成...");
  await new Promise(resolve => setTimeout(resolve, 5000));

  // 获取通知
  const notifications = bgManager.drainNotifications();
  console.log(`\n📬 收到 ${notifications.length} 个通知:`);
  notifications.forEach(n => {
    console.log(`  Task #${n.taskId}: ${n.status} (${Math.round(n.duration/1000)}s)`);
    console.log(`  结果: ${JSON.stringify(n.result).slice(0, 100)}...\n`);
  });

  console.log("✅ 测试完成");
}

test().catch(console.error);
