/**
 * npm run check:tool-refs — 手动运行工具引用 sanity check
 * 退出码：0=无问题，1=有疑似漂移（供 CI/人工检查）
 */
import { runToolReferenceCheckOnStartup } from "./tool-reference-check.js";

const issues = await runToolReferenceCheckOnStartup(process.cwd());
if (issues.length === 0) {
  console.log("[tool-ref-check] ✅ 所有文本源的工具引用均已注册");
  process.exit(0);
}
process.exit(1);
