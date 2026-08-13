// recall-message.ts
import type { RecallFlow, RecallHit, RecallMessage } from './types.js';

function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function formatRecallMessage(flow: RecallFlow, hits: RecallHit[], charBudget: number): RecallMessage {
  const parts: string[] = [];
  let total = 0;
  const used: RecallHit[] = [];
  for (const h of hits) {
    const block = `  <memory id="${h.id}" relevance="${h.score.toFixed(2)}" source="${h.source}">${escapeXml(h.content)}</memory>`;
    if (total + block.length > charBudget) break;
    parts.push(block);
    total += block.length;
    used.push(h);
  }
  const content =
    `<recalled_memory source="auto-prefetch" flow="${flow}" count="${used.length}" gate="passed">\n` +
    parts.join('\n') +
    `\n</recalled_memory>`;
  return {
    customType: 'recalled-memory',
    content,
    display: false,
    details: { flow, count: used.length },
  };
}
