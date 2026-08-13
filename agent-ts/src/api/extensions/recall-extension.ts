/**
 * recallExtension — 记忆召回 SDK 扩展（P2-T1 接线）
 *
 * 通过 before_agent_start 注入独立 CustomMessage（customType='recalled-memory'），
 * 替代 W1.4 在 session-factory 里把召回文本拼进系统提示词的注入方式。
 *
 * 事件流：
 *   input（暂存原文，skill 展开前）→ before_agent_start（判定 flow → RecallService.recall → 返回 message）
 *
 * 全程 try/catch，异常只 console.warn，绝不阻塞对话。
 */

import type { ExtensionFactory, InputSource } from "@mariozechner/pi-coding-agent";
import type { MemorySearchResult } from "../../services/memory/port.js";
import { getMemoryProvider } from "../../services/memory/provider-manager.js";
import { RecallService } from "../../services/recall/recall-service.js";
import type { RecallSearchPort, RecallAuditPort } from "../../services/recall/ports.js";
import { createRecallAuditPort } from "../../infrastructure/recall/audit-v2-client.js";
import type { RecallFlow, RecallHit } from "../../domain/recall/types.js";

/** 与 skill-guard.getExplicitSkillFromPrompt 同源：/skill:name 前缀（name = [a-z0-9-]+） */
const SKILL_PREFIX_RE = /^\/skill:[a-z0-9-]+/i;

/**
 * flow 判定表（P2-T3 接线，实测结论 2026-08-13）：
 * 判定依据 = SDK `input` 事件 source（PromptOptions.source）优先级最高，其次 /skill: 前缀。
 *
 * | source       | flow             | 来源通道                          |
 * |--------------|------------------|-----------------------------------|
 * | rpc          | scheduled-task   | 调度器 promptAgent（index/headless）|
 * | extension    | wake-event       | wake 通道（3002 HTTP 推送）        |
 * | interactive  | skill-invocation | 人工消息且 /skill: 前缀            |
 * | interactive  | interactive-chat | 其余人工消息（TUI/feishu/web）      |
 *
 * 备注：scheduled/wake 消息是自带完整工作流的机器消息，不会带 /skill: 前缀，
 * 所以 source 判定优先于 /skill: 前缀判定。
 */
export function detectFlow(rawText: string, source: InputSource = "interactive"): RecallFlow {
  if (source === "rpc") return "scheduled-task";
  if (source === "extension") return "wake-event";
  return SKILL_PREFIX_RE.test(rawText.trimStart()) ? "skill-invocation" : "interactive-chat";
}

/** 去掉 /skill:name 路由前缀，只保留参数作为检索 query（test ② 契约：query 不含 skill 前缀） */
export function stripSkillPrefix(rawText: string): string {
  return rawText.trimStart().replace(SKILL_PREFIX_RE, "").trimStart();
}

/** MemorySearchResult → RecallHit 字段映射；过滤非数字 id，未知 source 归一为 bm25 */
export function adaptSearchResults(results: MemorySearchResult[]): RecallHit[] {
  const hits: RecallHit[] = [];
  for (const r of results) {
    if (typeof r.id !== "number") continue;
    hits.push({
      id: r.id,
      score: typeof r.score === "number" ? r.score : 0,
      source: normalizeSource(r.source),
      title: r.title,
      content: r.content,
    });
  }
  return hits;
}

function normalizeSource(source?: string): RecallHit["source"] {
  return source === "vector" || source === "both" || source === "bm25" ? source : "bm25";
}

/** 懒构建检索端口：provider 在会话期才初始化，须在 search 内取而非构造时取（未初始化抛错由 RecallService 兜底） */
function buildSearchPort(): RecallSearchPort {
  return {
    async search(query, limit) {
      const provider = getMemoryProvider();
      const results = await provider.search(query, limit);
      return adaptSearchResults(results);
    },
  };
}

/**
 * 可注入端口版本的扩展工厂（测试用）。
 * recallExtension = createRecallExtension(真实端口)。
 */
export function createRecallExtension(
  searchPort: RecallSearchPort,
  auditPort: RecallAuditPort,
): ExtensionFactory {
  return (pi) => {
    let stashedText = "";
    let stashedSource: InputSource = "interactive";
    const service = new RecallService(searchPort, auditPort);

    pi.on("input", (event) => {
      // 暂存原文 + source（skill 展开前）。before_agent_start.prompt 是展开后文本，不能用来判 flow。
      stashedText = event.text ?? "";
      stashedSource = event.source ?? "interactive";
    });

    pi.on("before_agent_start", async () => {
      try {
        const flow = detectFlow(stashedText, stashedSource);
        const rawText = flow === "skill-invocation" ? stripSkillPrefix(stashedText) : stashedText;
        const message = await service.recall({ flow, rawText });
        if (message) {
          return { message };
        }
      } catch (err) {
        console.warn("[recall-extension] recall failed:", err);
      }
    });
  };
}

/** 真实接线：getMemoryProvider() 检索 + createRecallAuditPort() 审计 */
export const recallExtension: ExtensionFactory = (pi) => {
  createRecallExtension(buildSearchPort(), createRecallAuditPort())(pi);
};
