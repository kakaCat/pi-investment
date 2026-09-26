/**
 * StatusTool 工具壳（REQ-47939a t8）——三段式薄壳：prompt（prompt.ts）+ 元数据/入参/输出（本文件）
 * + execute 委托 application 用例。**不含任何领域判定**（状态判断只在 domain）。
 *
 * 返回体与拒绝条件与搬迁前的 host/agent-tools.ts 逐一对应（零行为变更）。
 *
 * @module dsh-pmboard/tools/StatusTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { queryState } from '../../application/query/QueryState.js'
import { STATUS_PROMPT } from './prompt.js'
import { renderSmart } from '../shared.js'
import { statusSummary } from '../render-summaries.js'

export function defineStatusTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_status',
    description:
      '查询本窗口 reqboard 绑定状态：是否已绑定进行中需求。识别到新工作想立项前先自查：已绑定时不要重复立项。',
    parameters: {},
    output: {
      schema: {
        type: 'object',
        additionalProperties: true,
        properties: {
          window_key: { type: 'string', description: '本窗口标识' },
          open_count: { type: 'number', description: '本窗口进行中需求数' },
          bound: { type: 'boolean', description: '本窗口是否已绑定进行中需求（bound 时不再立项）' },
          open_requirements: {
            type: 'array',
            description: '本窗口进行中需求简要列表',
            items: {
              type: 'object',
              additionalProperties: true,
              properties: {
                id: { type: 'string' },
                title: { type: 'string' },
                status: { type: 'string' },
                category: { type: 'string' },
              },
            },
          },
          next_actions: {
            type: 'array',
            description: '本窗口可自行推进的目标状态（agent 合法转移；取消/归档为人工闸门不在此列）',
            items: { type: 'string' },
          },
          clause_receive_status: {
            type: 'array',
            description:
              '本条需求每条功能点的接收状态（FR-3）：done=已完成+证据 / received=已被任务接收 / skipped=本轮裁剪 / **unreceived=未被接收（红）**',
            items: {
              type: 'object',
              additionalProperties: true,
              properties: {
                clause: { type: 'string' },
                state: { type: 'string' },
                by: { type: 'array', items: { type: 'string' } },
              },
            },
          },
          unreceived_clauses: {
            type: 'array',
            description: '未被任何任务接收、也未裁剪的条款（**红**）——存在即为 R9 那类缺口',
            items: { type: 'string' },
          },
          design_docs: {
            type: 'array',
            description:
              '本条需求设计文档逐份登记态（FR-1）：未登记=on_disk&&!registered / 待确认=registered&&!confirmed / 已落章=confirmed',
            items: {
              type: 'object',
              additionalProperties: true,
            },
          },
          fr_coverage: {
            type: 'object',
            description: 'FR 覆盖度统计（REQ-260925172227-2d61）',
            additionalProperties: true,
            properties: {
              total_frs: { type: 'number', description: 'FR 总数' },
              covered_frs: { type: 'number', description: '已覆盖 FR 数' },
              unreceived_clauses: {
                type: 'array',
                description: '未被任务接收的 FR',
                items: { type: 'string' },
              },
              coverage_rate: { type: 'number', description: '覆盖率（%）' },
            },
          },
          fr_acceptance_progress: {
            type: 'object',
            description: 'FR 验收进度统计（REQ-260925172227-2d61，仅验收阶段有）',
            additionalProperties: false,
            properties: {
              total: { type: 'number', description: '验收项总数' },
              passed: { type: 'number', description: '通过数' },
              failed: { type: 'number', description: '失败数' },
              pending: { type: 'number', description: '待验数' },
              pass_rate: { type: 'number', description: '通过率（%）' },
              gate_status: { type: 'string', description: '门禁状态：passed/blocked/pending' },
            },
          },
          rtm_health: {
            type: 'object',
            description: 'RTM 文件健康状态（修复：yaml 生成失败时提醒）',
            additionalProperties: true,
            properties: {
              healthy: { type: 'boolean', description: '是否健康（所有应有的 RTM 文件都存在）' },
              missing_files: {
                type: 'array',
                description: '缺失的 RTM 文件列表',
                items: { type: 'string' },
              },
              last_failure: {
                type: 'object',
                description: '最近一次生成失败记录',
                additionalProperties: true,
                properties: {
                  trigger: { type: 'string', description: '触发点（create/submit:requirement等）' },
                  error: { type: 'string', description: '错误信息' },
                  timestamp: { type: 'number', description: '失败时间戳（ms）' },
                  attempts: { type: 'number', description: '连续失败次数' },
                },
              },
              retry_available: { type: 'boolean', description: '是否可以重试修复（失败次数<3）' },
            },
          },
          traceability_chain: {
            type: 'object',
            description: '三级追溯链统计（2026-09-26 追溯性改进）',
            additionalProperties: true,
            properties: {
              design_coverage: {
                type: 'object',
                description: 'Level 1: 需求 ← 设计',
                additionalProperties: true,
                properties: {
                  total: { type: 'number', description: 'FR 总数' },
                  covered: { type: 'number', description: '有设计的 FR 数' },
                  coverage_rate: { type: 'number', description: '覆盖率（%）' },
                  gaps: { type: 'array', description: '未被设计覆盖的 FR', items: { type: 'string' } },
                  status: { type: 'string', description: 'complete/incomplete' },
                },
              },
              implementation_coverage: {
                type: 'object',
                description: 'Level 2: 设计 ← 任务',
                additionalProperties: true,
                properties: {
                  total: { type: 'number', description: '设计章节总数' },
                  covered: { type: 'number', description: '有任务实现的章节数' },
                  coverage_rate: { type: 'number', description: '覆盖率（%）' },
                  gaps: { type: 'array', description: '未被任务实现的设计章节', items: { type: 'string' } },
                  status: { type: 'string', description: 'complete/incomplete' },
                },
              },
              test_coverage: {
                type: 'object',
                description: 'Level 3: 任务 ← 测试',
                additionalProperties: true,
                properties: {
                  total: { type: 'number', description: '任务总数' },
                  tested: { type: 'number', description: '有测试的任务数' },
                  coverage_rate: { type: 'number', description: '覆盖率（%）' },
                  gaps: { type: 'array', description: '未被测试覆盖的任务', items: { type: 'string' } },
                  status: { type: 'string', description: 'complete/incomplete' },
                },
              },
              overall_status: { type: 'string', description: '整体状态：complete/incomplete' },
            },
          },
          note: { type: 'string', description: '下一步指引' },
          board_link: { type: 'string', description: '项目看板链接（可在会话中点击跳转）' },
        },
      },
      render: renderSmart(statusSummary),
    },
    timeoutMs: LIMITS.timeoutReadMs,
    execute: async (args: unknown, exec: ToolRunContext) => queryState(deps, args, exec),
  } as any)
}