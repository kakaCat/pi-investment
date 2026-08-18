import { defineTool } from '@deepseek-ai/dsh-tools';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';

/**
 * Create evolution status tool
 * 
 * Fetches evolution leaderboard and decision scores from real backend endpoints.
 * Endpoints verified: GET /api/evolution/leaderboard and GET /api/evolution/decision-scores
 */
export function createEvolutionStatusTool(client: AgentDHClient) {
  return defineTool({
    name: 'evolution_status',
    description: '获取Agent进化状态，包括排行榜和决策评分',
    parameters: {},
    output: {
      schema: {
        type: 'object',
        properties: {
          leaderboard: {
            type: 'object',
            description: '进化排行榜',
            properties: {
              windowEnd: { type: 'string' },
              windowDays: { type: 'number' },
              ranking: { type: 'array' },
            },
            additionalProperties: true,
          },
          decision_scores: {
            type: 'object',
            description: '决策评分',
            properties: {
              total: { type: 'number' },
              items: { type: 'array' },
            },
            additionalProperties: true,
          },
          summary: {
            type: 'string',
            description: '中文一句话总结',
          },
        },
        additionalProperties: true,
      },
      render: (args, value) => [
        {
          type: 'text',
          text: JSON.stringify(value, null, 2),
        },
      ],
    },
    timeoutMs: 10000,
    execute: async (args, exec) => {
      try {
        // Parallel fetch both endpoints
        const [leaderboard, decisionScores] = await Promise.all([
          client.quantsysV2.getEvolutionLeaderboard(),
          client.quantsysV2.getEvolutionDecisionScores(),
        ]);

        // Generate summary
        const topAccount = leaderboard.ranking[0];
        const summary = topAccount
          ? `当前排名第1的账户是 ${topAccount.accountName}，适应度 ${topAccount.fitness.toFixed(2)}（上涨捕获 ${topAccount.upCapture.toFixed(2)}，下跌捕获 ${topAccount.downCapture.toFixed(2)}）。共有 ${decisionScores.total} 条决策评分记录。`
          : `暂无排行榜数据。共有 ${decisionScores.total} 条决策评分记录。`;

        return {
          leaderboard,
          decision_scores: decisionScores,
          summary,
        };
      } catch (error) {
        throw new Error(
          `获取进化状态失败: ${error instanceof Error ? error.message : String(error)}`
        );
      }
    },
  });
}
