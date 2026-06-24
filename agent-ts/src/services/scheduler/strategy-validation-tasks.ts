/**
 * 策略验证定时任务
 *
 * 每日自动验证所有策略，标记失效策略并告警
 */

import type { CronTask } from '../../types/scheduler.js';

export const strategyValidationTasks: CronTask[] = [
  {
    name: '每日策略验证',
    cron: '0 21 * * 1-5', // 工作日 21:00
    description: '批量回测所有策略，评估有效性',
    enabled: true,
    handler: async (context) => {
      const { logger, toolRegistry } = context;

      try {
        logger.info('开始每日策略验证...');

        // 1. 获取所有活跃策略
        const strategyListTool = toolRegistry.getTool('strategy_list');
        const strategies: any[] = await strategyListTool.execute('', {});

        if (!strategies?.success || !(strategies as any).data?.length) {
          logger.warn('未找到活跃策略');
          return;
        }

        logger.info(`找到 ${(strategies as any).data.length} 个策略，开始验证...`);

        // 2. 批量验证（最近30天）
        const now = new Date();
        const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

        const batchValidateTool = toolRegistry.getTool('strategy_batch_validate');
        const validation = await batchValidateTool.execute('', {
          strategy_ids: (strategies as any).data.map((s: any) => s.id),
          symbols: [
            '600519.SH', // 贵州茅台（代表消费）
            '000858.SZ', // 五粮液（代表白酒）
            '600036.SH', // 招商银行（代表金融）
            '000001.SZ', // 平安银行（代表银行）
            '600276.SH', // 恒瑞医药（代表医药）
          ],
          start_date: thirtyDaysAgo.toISOString().split('T')[0],
          end_date: now.toISOString().split('T')[0],
        });

        if (!validation?.success) {
          logger.error('批量验证失败', validation?.error);
          return;
        }

        // 3. 分析结果，标记失效策略
        const results = (validation as any).data?.results || [];
        const failedStrategies = results.filter((r: any) =>
          r.win_rate < 0.4 || r.sharpe < 0.5
        );

        const warningStrategies = results.filter((r: any) =>
          r.win_rate >= 0.4 && r.win_rate < 0.5 ||
          r.sharpe >= 0.5 && r.sharpe < 1.0
        );

        const goodStrategies = results.filter((r: any) =>
          r.win_rate >= 0.6 && r.sharpe >= 1.5
        );

        logger.info('验证完成', {
          total: results.length,
          failed: failedStrategies.length,
          warning: warningStrategies.length,
          good: goodStrategies.length,
        });

        // 4. 发送告警（如果有失效策略）
        if (failedStrategies.length > 0 || warningStrategies.length > 0) {
          const monitorAlertTool = toolRegistry.getTool('monitor_alert');

          if (failedStrategies.length > 0) {
            await monitorAlertTool.execute('', {
              level: 'error',
              title: `${failedStrategies.length}个策略表现异常`,
              message: `以下策略胜率<40%或夏普<0.5，建议停用：\n${
                failedStrategies.map((s: any) =>
                  `- ${s.strategy_name}: 胜率=${(s.win_rate * 100).toFixed(1)}%, 夏普=${s.sharpe.toFixed(2)}`
                ).join('\n')
              }`,
              metadata: {
                type: 'strategy_validation',
                failed_strategies: failedStrategies,
              },
            });
          }

          if (warningStrategies.length > 0) {
            await monitorAlertTool.execute('', {
              level: 'warning',
              title: `${warningStrategies.length}个策略需关注`,
              message: `以下策略表现一般，需持续观察：\n${
                warningStrategies.map((s: any) =>
                  `- ${s.strategy_name}: 胜率=${(s.win_rate * 100).toFixed(1)}%, 夏普=${s.sharpe.toFixed(2)}`
                ).join('\n')
              }`,
              metadata: {
                type: 'strategy_validation',
                warning_strategies: warningStrategies,
              },
            });
          }
        }

        // 5. 输出优秀策略（用于参考）
        if (goodStrategies.length > 0) {
          logger.info(`优秀策略 (${goodStrategies.length}个):`,
            goodStrategies.map((s: any) => ({
              name: s.strategy_name,
              win_rate: `${(s.win_rate * 100).toFixed(1)}%`,
              sharpe: s.sharpe.toFixed(2),
              return: `${(s.total_return * 100).toFixed(1)}%`,
            }))
          );
        }

        logger.info('每日策略验证完成');

      } catch (error) {
        logger.error('策略验证任务失败', error);
        throw error;
      }
    },
  },

  {
    name: '周末策略发现',
    cron: '0 10 * * 6', // 周六 10:00
    description: '自动发现新策略，探索参数空间',
    enabled: true,
    handler: async (context) => {
      const { logger, toolRegistry } = context;

      try {
        logger.info('开始周末策略发现...');

        // 1. 获取最近表现好的股票（作为测试集）
        const opportunityScanTool = toolRegistry.getTool('opportunity_scan');
        const opportunities = await opportunityScanTool.execute('', {
          enable_dynamic_weights: true,
          limit: 20,
          minScore: 70,
        });

        if (!opportunities?.success || !(opportunities as any).data?.opportunities?.length) {
          logger.warn('未找到合适的测试股票');
          return;
        }

        const topSymbols = (opportunities as any).data.opportunities
          .slice(0, 10)
          .map((o: any) => o.symbol);

        logger.info(`选择 ${topSymbols.length} 只股票进行策略发现`);

        // 2. 运行策略发现
        const discoveryTool = toolRegistry.getTool('strategy_discovery');
        const discovery = await discoveryTool.execute('', {
          action: 'run',
          symbols: topSymbols,
          start_date: '2025-06-01',
          end_date: '2026-06-04',
          metric: 'sharpe',
          max_combinations: 50,
        });

        if (!discovery?.success) {
          logger.error('策略发现失败', discovery?.error);
          return;
        }

        // 3. 输出发现的策略
        const discovered = (discovery as any).data?.strategies || [];
        logger.info(`发现 ${discovered.length} 个潜在策略`);

        if (discovered.length > 0) {
          const top5 = discovered.slice(0, 5);
          logger.info('Top 5 策略:', top5.map((s: any) => ({
            archetype: s.archetype,
            params: s.params,
            sharpe: s.sharpe.toFixed(2),
            return: `${(s.return * 100).toFixed(1)}%`,
            win_rate: `${(s.win_rate * 100).toFixed(1)}%`,
          })));

          // 4. 发送通知
          const monitorAlertTool = toolRegistry.getTool('monitor_alert');
          await monitorAlertTool.execute('', {
            level: 'info',
            title: `策略发现完成，找到${discovered.length}个候选策略`,
            message: `Top 5 策略：\n${
              top5.map((s: any, i: number) =>
                `${i + 1}. ${s.archetype} - 夏普=${s.sharpe.toFixed(2)}, 收益=${(s.return * 100).toFixed(1)}%`
              ).join('\n')
            }`,
            metadata: {
              type: 'strategy_discovery',
              strategies: top5,
            },
          });
        }

        logger.info('周末策略发现完成');

      } catch (error) {
        logger.error('策略发现任务失败', error);
        throw error;
      }
    },
  },
];
