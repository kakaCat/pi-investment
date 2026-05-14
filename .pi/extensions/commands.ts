/**
 * 投资顾问自定义命令扩展（注册层）
 *
 * SDK 在 <cwd>/.pi/extensions/ 自动发现并加载 .ts 扩展文件。
 * 注册的命令可直接用 /命令名 触发，不经 LLM。
 *
 * 业务逻辑在 src/cli/handlers.ts，此文件只负责注册。
 */
import { handleEvolution, handleHelp } from "../../src/cli/handlers.js";

export default function (pi: any) {
  pi.registerCommand("evolution", {
    description: "运行进化分析——评估表现，归因差距，生成优化建议",
    handler: handleEvolution,
  });

  pi.registerCommand("help", {
    description: "显示所有可用命令",
    handler: handleHelp,
  });

  console.log("✅ 自定义命令已注册: /evolution, /help");
}
