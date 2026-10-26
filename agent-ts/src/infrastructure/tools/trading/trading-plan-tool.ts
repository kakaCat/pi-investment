/**
 * Trading Plan Tool - 交易计划（REQ-261021222905-6dff t12 · IF-17）
 *
 * 与 agent-dh 的 TradingPlanTool 同契约（同一 action 枚举、同一后端、同一错误透传）。
 * 执行归 WatchEngine；本工具只做计划面调用，下单仍走 portfolio_trade（agent 终判）。
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

const ACTIONS = [
  "today", "list", "get", "create", "patch", "apply", "activate", "pause",
  "resume", "close", "preview", "stats", "reflect", "reflections", "blocked_stats",
] as const;

export const tradingPlanTool: ToolDefinition = {
  name: "trading_plan",
  label: "交易计划",
  description:
    "交易计划管理：盘前先用 today 拉今日计划；建计划/改计划（patch 预览→apply 生效）/激活暂停关闭；" +
    "盘后提交反思（五问必填）。计划编译成盯盘规则由 WatchEngine 执行，下单仍由你终判。" +
    "写操作必须带 decision_audit_id。",
  parameters: Type.Object({
    action: Type.String({ description: `操作: ${ACTIONS.join(" | ")}` }),
    plan_id: Type.Optional(Type.Number({ description: "计划 ID（除 today/list/create/blocked_stats 外必填）" })),
    account: Type.Optional(Type.String({ description: "账户（缺省取实例账户）" })),
    status: Type.Optional(Type.String({ description: "list 过滤：active,holding,closing" })),
    name: Type.Optional(Type.String({ description: "计划名（create 必填）" })),
    horizon: Type.Optional(Type.String({ description: "day | swing（create 用）" })),
    spec: Type.Optional(Type.Record(Type.String(), Type.Any(), {
      description: "计划 spec：targets/entry/exit/monitoring/schedule（create 必填；exit 至少 stop_loss 或 reduce_plan）",
    })),
    spec_patch: Type.Optional(Type.Record(Type.String(), Type.Any(), { description: "patch 用：要覆盖的 spec 片段" })),
    expected_version: Type.Optional(Type.Number({ description: "版本 CAS（patch/apply/activate/resume 必填）" })),
    reason: Type.Optional(Type.String({ description: "理由（apply/pause/close 用；反向修改必须写清上次为什么错）" })),
    decision_audit_id: Type.Optional(Type.String({ description: "决策审计号（agent 写操作必填）" })),
    hypothesis: Type.Optional(Type.Record(Type.String(), Type.Any(), { description: "假设卡：change/evidence/expected" })),
    verdict: Type.Optional(Type.String({ description: "反思结论：keep | adjust | close | observe" })),
    answers: Type.Optional(Type.Record(Type.String(), Type.String(), { description: "反思五问：q1..q5" })),
    actions: Type.Optional(Type.Array(Type.Record(Type.String(), Type.Any()), { description: "修改提案（adjust/close 必填）" })),
    close_disposition: Type.Optional(Type.String({ description: "持仓处置方案（有持仓关闭必填）" })),
    period: Type.Optional(Type.String({ description: "反思周期（如 2026-10-21）" })),
  }),
  execute: async (_toolCallId: string, params: any) => {
    const action = String(params.action || "");
    const id = Number(params.plan_id || 0);
    const account = params.account;
    try {
      let result: unknown;
      switch (action) {
        case "today":
          result = await runQuantV2("plan.today", account ? { account } : {});
          break;
        case "list":
          result = await runQuantV2("plan.list", {
            ...(account ? { account } : {}), ...(params.status ? { status: params.status } : {}),
          });
          break;
        case "get":
          result = await runQuantV2("plan.get", { plan_id: id });
          break;
        case "create":
          result = await runQuantV2("plan.create", {
            ...(account ? { account } : {}), name: params.name, horizon: params.horizon || "day",
            spec: params.spec, created_by: "agent", actor: "agent",
          });
          break;
        case "patch":
          result = await runQuantV2("plan.patch", {
            plan_id: id, expected_version: params.expected_version, spec_patch: params.spec_patch,
            reason: params.reason, decision_audit_id: params.decision_audit_id, actor: "agent",
          });
          break;
        case "apply":
          result = await runQuantV2("plan.apply", {
            plan_id: id, expected_version: params.expected_version, reason: params.reason,
            hypothesis: params.hypothesis, decision_audit_id: params.decision_audit_id, actor: "agent",
          });
          break;
        case "activate":
          result = await runQuantV2("plan.activate", {
            plan_id: id, expected_version: params.expected_version, actor: "agent",
          });
          break;
        case "pause":
          result = await runQuantV2("plan.pause", { plan_id: id, reason: params.reason, actor: "agent" });
          break;
        case "resume":
          result = await runQuantV2("plan.resume", {
            plan_id: id, expected_version: params.expected_version, actor: "agent",
          });
          break;
        case "close":
          result = await runQuantV2("plan.close", {
            plan_id: id, reason: params.reason, close_disposition: params.close_disposition, actor: "agent",
          });
          break;
        case "preview":
          result = await runQuantV2("plan.preview", { plan_id: id });
          break;
        case "stats":
          result = await runQuantV2("plan.stats", { plan_id: id });
          break;
        case "reflect":
          result = await runQuantV2("plan.reflect", {
            plan_id: id, answers: params.answers, verdict: params.verdict,
            reasoning: params.reason, actions: params.actions, period: params.period,
          });
          break;
        case "reflections":
          result = await runQuantV2("plan.reflections", { plan_id: id });
          break;
        case "blocked_stats":
          result = await runQuantV2("plan.blocked_stats", {});
          break;
        default:
          return { content: [{ type: "text" as const, text: `未知 action: ${action}` }], details: { success: false, error: `未知 action: ${action}` } };
      }
      return handleToolResponse({
        toolName: "trading_plan",
        data: result,
        formatter: (data) => (typeof data === "string" ? data : JSON.stringify(data, null, 2)),
        metadata: { action, plan_id: id },
      });
    } catch (error: any) {
      return {
        content: [{ type: "text" as const, text: `交易计划调用失败: ${error?.message || String(error)}` }],
        details: { success: false, error: error?.message || String(error) },
      };
    }
  },
};
