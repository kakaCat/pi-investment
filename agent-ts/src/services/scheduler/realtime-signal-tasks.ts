/**
 * 实时信号扫描定时任务
 *
 * 盘中每5分钟扫描市场，生成买卖信号并推送
 */

import type { CronTask } from '../../types/scheduler.js';

export const realtimeSignalTasks: CronTask[] = [
  {
    name: '开盘前市场扫描',
    cron: '25 9 * * 1-5', // 工作日 09:25
    description: '开盘前扫描热门股票，准备监控列表',
    enabled: true,
    handler: async (context) => {
      const { logger, toolRegistry } = context;

      try {
        logger.info('开始开盘前市场扫描...');

        // 1. 扫描机会
        const opportunityScanTool = toolRegistry.getTool('opportunity_scan');
        const scan = await opportunityScanTool.execute('', {
          enable_dynamic_weights: true,
          limit: 50,
          minScore: 65,
        });

        if (!scan?.success || !(scan as any).data?.opportunities?.length) {
          logger.warn('未找到投资机会');
          return;
        }

        const opportunities = (scan as any).data.opportunities;
        logger.info(`找到 ${opportunities.length} 个投资机会`);

        // 2. 筛选高质量标的（评分>75，低风险）
        const highQuality = opportunities.filter((o: any) =>
          o.score >= 75 && o.risk_level === 'low'
        );

        const mediumQuality = opportunities.filter((o: any) =>
          o.score >= 70 && o.score < 75 && o.risk_level !== 'high'
        );

        logger.info('分类结果', {
          high_quality: highQuality.length,
          medium_quality: mediumQuality.length,
          total: opportunities.length,
        });

        // 3. 输出今日关注列表
        if (highQuality.length > 0) {
          logger.info('今日重点关注 (高质量):',
            highQuality.slice(0, 10).map((o: any) => ({
              symbol: o.symbol,
              name: o.name,
              score: o.score,
              technical: o.technical_score,
              fundamental: o.fundamental_score,
            }))
          );
        }

        // 4. 发送开盘提醒
        const monitorAlertTool = toolRegistry.getTool('monitor_alert');
        await monitorAlertTool.execute('', {
          level: 'info',
          title: `开盘前扫描完成，发现${opportunities.length}个机会`,
          message: `高质量标的 (${highQuality.length}个)：\n${
            highQuality.slice(0, 5).map((o: any) =>
              `- ${o.name} (${o.symbol}): 评分=${o.score}, 风险=${o.risk_level}`
            ).join('\n')
          }${highQuality.length > 5 ? `\n... 还有${highQuality.length - 5}个` : ''}`,
          metadata: {
            type: 'market_scan',
            opportunities: highQuality,
          },
        });

        logger.info('开盘前市场扫描完成');

      } catch (error) {
        logger.error('开盘前扫描任务失败', error);
        throw error;
      }
    },
  },

  {
    name: '实时信号监控',
    cron: '*/5 9-14 * * 1-5', // 工作日 09:00-14:55，每5分钟
    description: '盘中实时扫描，检测买卖信号',
    enabled: true,
    handler: async (context) => {
      const { logger, toolRegistry, sessionContext } = context;

      try {
        // 静默运行，不输出常规日志（避免刷屏）
        const startTime = Date.now();

        // 1. 获取监控列表（优先使用 session 存储的列表，否则快速扫描）
        let watchList: string[] = sessionContext?.get('realtime_watch_list') || [];

        if (watchList.length === 0) {
          // 快速扫描获取前20只高评分股票
          const opportunityScanTool = toolRegistry.getTool('opportunity_scan');
          const scan = await opportunityScanTool.execute('', {
            enable_dynamic_weights: false, // 使用固定权重（更快）
            limit: 20,
            minScore: 70,
          });

          if (scan?.success && (scan as any).data?.opportunities?.length > 0) {
            watchList = (scan as any).data.opportunities
              .slice(0, 15)
              .map((o: any) => o.symbol);
            sessionContext?.set('realtime_watch_list', watchList);
          } else {
            logger.warn('无法获取监控列表，跳过本次扫描');
            return;
          }
        }

        // 2. 对每只股票执行策略（使用多因子波段策略v9）
        const strategyExecuteTool = toolRegistry.getTool('strategy_execute');
        const signals: any[] = [];

        for (const symbol of watchList.slice(0, 10)) { // 限制前10只，避免超时
          try {
            const result = await strategyExecuteTool.execute('', {
              action: 'single',
              symbol,
              strategy: '53', // 多因子波段策略v9
              return_detail: true,
            });

            if (result?.success && (result as any).data) {
              const signal = (result as any).data;

              // 只记录买入/卖出信号（忽略 hold）
              if (signal.signal !== 'hold' && signal.risk_level !== 'high') {
                signals.push({
                  symbol,
                  name: signal.stock_name || symbol,
                  action: signal.signal,
                  price: signal.current_price,
                  reasons: signal.reasons || [],
                  risk_level: signal.risk_level,
                  confidence: signal.confidence || 0,
                  timestamp: new Date().toISOString(),
                });
              }
            }
          } catch (error) {
            // 忽略单只股票错误，继续处理下一只
            logger.debug(`处理 ${symbol} 失败:`, error);
          }
        }

        // 3. 如果有信号，推送到 WebSocket（通过 backend）
        if (signals.length > 0) {
          logger.info(`检测到 ${signals.length} 个信号`);

          for (const signal of signals) {
            logger.info(`📊 ${signal.action.toUpperCase()} 信号:`, {
              stock: `${signal.name} (${signal.symbol})`,
              price: signal.price,
              reasons: signal.reasons.join(', '),
              risk: signal.risk_level,
            });

            // TODO: 推送到 WebSocket
            // 当前 quantsys-v2 的 WebSocket 服务已实现，需要添加推送接口
            // 临时方案：通过告警系统推送重要信号
            if (signal.confidence >= 0.7 && signal.risk_level === 'low') {
              const monitorAlertTool = toolRegistry.getTool('monitor_alert');
              await monitorAlertTool.execute('', {
                level: signal.action === 'buy' ? 'info' : 'warning',
                title: `${signal.action === 'buy' ? '买入' : '卖出'}信号: ${signal.name}`,
                message: `价格: ${signal.price}\n原因: ${signal.reasons.join('、')}\n风险: ${signal.risk_level}\n置信度: ${(signal.confidence * 100).toFixed(0)}%`,
                metadata: {
                  type: 'trading_signal',
                  signal,
                },
              });
            }
          }
        }

        const duration = Date.now() - startTime;
        logger.debug(`实时扫描完成，耗时 ${duration}ms，检测到 ${signals.length} 个信号`);

      } catch (error) {
        logger.error('实时信号监控任务失败', error);
        // 不抛出错误，避免中断后续定时任务
      }
    },
  },

  {
    name: '午间信号汇总',
    cron: '5 12 * * 1-5', // 工作日 12:05
    description: '汇总上午产生的信号',
    enabled: true,
    handler: async (context) => {
      const { logger } = context;

      try {
        logger.info('开始午间信号汇总...');

        // TODO: 查询今日上午的所有信号（需要 quantsys-v2 提供接口）
        // 临时方案：输出统计信息
        logger.info('午间汇总功能待实现，需要后端提供信号历史查询接口');

      } catch (error) {
        logger.error('午间汇总任务失败', error);
      }
    },
  },

  {
    name: '收盘信号复盘',
    cron: '5 15 * * 1-5', // 工作日 15:05
    description: '复盘今日所有信号，计算准确率',
    enabled: true,
    handler: async (context) => {
      const { logger, toolRegistry } = context;

      try {
        logger.info('开始收盘信号复盘...');

        // TODO: 查询今日所有信号，对比实际涨跌
        // 临时方案：清空监控列表，准备明日扫描
        const { sessionContext } = context;
        sessionContext?.delete('realtime_watch_list');

        logger.info('已清空监控列表，明日将重新扫描');

        // 发送收盘通知
        const monitorAlertTool = toolRegistry.getTool('monitor_alert');
        await monitorAlertTool.execute('', {
          level: 'info',
          title: '今日收盘，信号监控已停止',
          message: '今日信号复盘待实现\n明日 09:25 将重新扫描市场',
          metadata: {
            type: 'market_close',
          },
        });

        logger.info('收盘信号复盘完成');

      } catch (error) {
        logger.error('收盘复盘任务失败', error);
      }
    },
  },
];
