/**
 * CLI 命令处理器
 *
 * 包含所有自定义命令的业务逻辑，由 .pi/extensions/commands.ts 调用
 */

/**
 * /evolution 命令处理器
 * 运行进化分析——评估表现，归因差距，生成优化建议
 */
export async function handleEvolution(_args: string): Promise<void> {
  const { runWeeklyEvolution } = await import(
    "../services/intelligence/evolution-service.js"
  );
  const { formatReportAsMarkdown } = await import(
    "../services/intelligence/evolution-reporter.js"
  );

  try {
    const result = await runWeeklyEvolution();
    const markdown = formatReportAsMarkdown(result.report);
    process.stdout.write("\n" + markdown + "\n\n");
    process.stdout.write(
      `✅ 进化报告已保存: ${result.reportPath}\n`
    );
  } catch (e) {
    process.stderr.write(
      `❌ 进化分析失败: ${e instanceof Error ? e.message : String(e)}\n`
    );
  }
}

/**
 * /help 命令处理器
 * 显示所有可用命令
 */
export async function handleHelp(_args: string): Promise<void> {
  process.stdout.write(`
┌────────────────────────────────────────────┐
│         PI Investment 命令参考              │
├────────────────────────────────────────────┤
│                                            │
│  内置命令 (SDK)                              │
│  /quit       退出程序                        │
│  /model      切换模型                        │
│  /compact    手动压缩上下文                   │
│  /settings   打开设置                        │
│  /reload     重载扩展和技能                   │
│  /export     导出会话为 HTML                  │
│  /session    显示会话信息                     │
│  /help       显示此帮助                      │
│                                            │
│  投资命令                                    │
│  /evolution  运行进化分析—评估表现并生成优化建议  │
│                                            │
│  CLI 命令                                   │
│  npm run evolution      手动运行进化分析      │
│  npm run portfolio      持仓 & 交易管理      │
│                                            │
└────────────────────────────────────────────┘
`);
}
