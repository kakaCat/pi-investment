/**
 * 段落内容归一化 —— Evolver 写基因组前的最后一道闸（2026-09-12，w-c8cae280）
 *
 * 实证故障链（两个真实事故，均由本模块堵住）：
 *  ① 2026-09-12 周度变异：daily_distill 输出的 proposal.content 是「整段全文」
 *     （rules 段 3489 字 + 新增 R-016），下游把它当"建议"再次喂回 prompt_evolver；
 *     LLM 把 current 与 suggestion 里各自包含的一整段规则合并 → R-001…R-015 标题重复定义
 *     → genome guard 拒绝（"规则段含重复定义"），变异 0/1 应用。
 *  ② 2026-09-11 每日蒸馏：llmRewriteSection 的 append_fallback 分支裸拼接
 *     `current + suggestion.content`，把上游未序列化的对象（字符串化为 `[object Object]`）
 *     原样写进候选内容。
 *
 * 归一化保证（口径与 genome/src/guard.ts 完全一致）：
 *  - 规则段内 R-xxx 标题定义唯一；
 *  - 候选重复定义/删改既有规则时，以「当前段」为准做确定性增量合并（可归因：只新增，不覆盖）；
 *  - 无新增即 noop，避免生成"空更新"噪声候选；
 *  - 损坏标记 fail-closed，绝不写入基因组。
 */

/** 与 genome/src/guard.ts:67 extractRuleDefinitions 同口径：只有标题行里的 R-xxx 算"定义" */
export const RULE_DEF_SOURCE = '^#{1,6}\\s*(R-\\d{3})\\b';

/** 上游序列化失败留下的损坏标记（JS 把对象直接参与字符串拼接的产物） */
export const DAMAGE_MARKERS = ['[object Object]'];

export interface RuleBlock {
  id: string;
  /** 从该标题行到下一个标题行（或段尾）的完整文本 */
  text: string;
}

export interface NormalizeResult {
  content: string;
  /** 新增并追加生效的规则 ID */
  addedIds: string[];
  /** 候选改写了既有规则正文、但被保留为当前版本（不落盘）的 ID */
  droppedRewriteIds: string[];
  /** 候选内部对同一 ID 重复定义、仅保留首个而被丢弃的 ID */
  dedupedIds: string[];
  /** 追加块文本（仅新增部分），供下游按"增量"而非"整段"沉淀 */
  deltaText: string;
  /** 归一化结果与当前段无差异 */
  noop: boolean;
  /** replace=候选整段合法可直接替换；delta=确定性增量合并 */
  semantics: 'replace' | 'delta';
  /** 结构歧义标题行（前一行非空）——非空时调用方必须 fail-closed，避免静默截断 */
  ambiguousHeadings: string[];
  /** 新增 ID 中是"空壳"（标题后无正文）的规则——非空时调用方必须拒绝 */
  emptyShellIds: string[];
  /** delta 模式下未落盘的非空白字符数（既有规则改写 + prelude 改动），供可见化与告警 */
  droppedChars: number;
}

/** 提取规则定义（标题行）ID，按出现顺序 */
export function extractRuleDefs(content: string): string[] {
  if (!content) return [];
  return [...content.matchAll(new RegExp(RULE_DEF_SOURCE, 'gm'))].map((m) => m[1]);
}

/** 找出重复定义的规则 ID（正文引用不算定义） */
export function findDuplicateRuleDefs(content: string): string[] {
  const defs = extractRuleDefs(content);
  const seen = new Set<string>();
  const dups = new Set<string>();
  for (const d of defs) {
    if (seen.has(d)) dups.add(d);
    seen.add(d);
  }
  return [...dups];
}

/**
 * 找出**歧义标题行**（2026-09-13 修复，独立审阅发现）：
 * 形如 `^#{1,6}\s*R-\d{3}\b` 但**前一行非空**的标题行。
 *
 * 背景：该正则会命中正文里被 LLM 升格为小标题的行内回指，例如
 *   `要点：\n## R-001 的执行前提必须已满足\n其余说明。`
 * 此时 splitRuleBlocks 会在正文中途切断，后半段被并进一个"既有 ID 的候选块"，
 * 而 delta 合并只追加新 ID 的块 → **后半段被静默丢弃**（实证复现）。
 * 正常 markdown 的规则块之间必有空行（线上 rules.md 16 个定义行 100% 有空行），
 * 故"前一行非空"足以判为结构歧义；判为歧义后由调用方 fail-closed，绝不静默截断。
 */
export function findAmbiguousHeadings(content: string): string[] {
  const text = content ?? '';
  const lines = text.split('\n');
  const re = new RegExp(RULE_DEF_SOURCE);
  const out: string[] = [];
  for (let i = 0; i < lines.length; i++) {
    if (!re.test(lines[i])) continue;
    // 文件开头或前一行是空行 → 正常；否则结构可疑
    if (i === 0 || lines[i - 1].trim() === '') continue;
    out.push(lines[i].trim().slice(0, 60));
  }
  return out;
}

/** 空壳规则检测：块的标题行之后必须有正文（非空白 ≥ 10 字符） */
export function findEmptyShellDefs(content: string): string[] {
  const { blocks } = splitRuleBlocks(content);
  const out: string[] = [];
  for (const b of blocks) {
    const body = b.text.split('\n').slice(1).join('\n').replace(/\s+/g, '');
    if (body.length < 10) out.push(b.id);
  }
  return out;
}

/** 按规则定义标题切块 */
export function splitRuleBlocks(content: string): { prelude: string; blocks: RuleBlock[] } {
  const text = content ?? '';
  const marks: Array<{ id: string; index: number }> = [];
  const re = new RegExp(RULE_DEF_SOURCE, 'gm');
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) marks.push({ id: m[1], index: m.index });
  if (marks.length === 0) return { prelude: text, blocks: [] };
  const prelude = text.slice(0, marks[0].index);
  const blocks = marks.map((mk, i) => ({
    id: mk.id,
    text: text.slice(mk.index, i + 1 < marks.length ? marks[i + 1].index : text.length),
  }));
  return { prelude, blocks };
}

/** 损坏标记 fail-closed：宁可拒绝写入，也不把 `[object Object]` 送进基因组 */
export function assertNoDamage(content: string, label: string): void {
  const text = content ?? '';
  for (const marker of DAMAGE_MARKERS) {
    if (text.includes(marker)) {
      throw new Error(`${label}含损坏标记 "${marker}"（上游对象未序列化即被字符串拼接），拒绝写入基因组`);
    }
  }
}

const stripWs = (s: string) => (s ?? '').replace(/\s+/g, '');

/**
 * 归一化规则段内容。
 *
 * - 候选整段**合法**（无重复定义、未删除既有 ID、且与当前段有实质差异）→ 采用 replace 语义
 *   （保留 LLM 对既有规则正文的合理强化）；
 * - 否则 → 确定性增量合并：既有 ID 一律沿用当前段定义，只追加候选里的新 ID；
 * - 无新增 → noop=true（调用方应拒绝应用，避免空更新候选）。
 */
export function normalizeRulesContent(currentContent: string, candidateContent: string): NormalizeResult {
  const current = currentContent ?? '';
  const candidate = candidateContent ?? '';
  const ambiguousHeadings = findAmbiguousHeadings(candidate);
  const cur = splitRuleBlocks(current);
  const cand = splitRuleBlocks(candidate);
  const curIds = new Set(cur.blocks.map((b) => b.id));

  // 候选内部去重（首个定义生效，后续重复丢弃）
  const candFirst = new Map<string, string>();
  const dedupedIds: string[] = [];
  for (const b of cand.blocks) {
    if (candFirst.has(b.id)) {
      if (!dedupedIds.includes(b.id)) dedupedIds.push(b.id);
      continue;
    }
    candFirst.set(b.id, b.text);
  }
  const candIds = [...candFirst.keys()];
  const removedIds = [...curIds].filter((id) => !candFirst.has(id));
  const addedIds = curIds.size === 0 ? candIds : candIds.filter((id) => !curIds.has(id));
  const droppedRewriteIds = candIds.filter((id) => curIds.has(id));

  const hasDup = findDuplicateRuleDefs(candidate).length > 0;
  const substantive = curIds.size === 0 ? stripWs(candidate).length > 0 : stripWs(candidate) !== stripWs(current);

  const emptyShellIds = addedIds.filter((id) => {
    const block = candFirst.get(id) ?? '';
    const body = block.split('\n').slice(1).join('\n').replace(/\s+/g, '');
    return body.length < 10;
  });

  if (!hasDup && removedIds.length === 0 && candIds.length > 0 && substantive) {
    return {
      content: candidate.endsWith('\n') ? candidate : `${candidate}\n`,
      addedIds,
      droppedRewriteIds: [],
      dedupedIds,
      deltaText: addedIds.map((id) => (candFirst.get(id) ?? '').trim()).join('\n\n'),
      noop: false,
      semantics: 'replace',
      ambiguousHeadings,
      emptyShellIds,
      droppedChars: 0,
    };
  }

  // 确定性增量合并：当前段为准，只追加新 ID
  let content = current;
  let deltaText = '';
  if (addedIds.length > 0) {
    const base = current.replace(/\s*$/, '');
    deltaText = addedIds.map((id) => (candFirst.get(id) ?? '').trim()).join('\n\n');
    content = `${base}\n\n${deltaText}\n`;
  }
  const noop = addedIds.length === 0 || stripWs(content) === stripWs(current);

  // 丢弃量可见化：delta 保留"当前段 + 新 ID 块"，其余候选内容（既有规则改写 + prelude 改动）不落盘。
  const keptFromCandidate = stripWs(deltaText).length;
  const droppedChars = Math.max(0, stripWs(candidate).length - keptFromCandidate);

  return {
    content, addedIds, droppedRewriteIds, dedupedIds, deltaText, noop, semantics: 'delta',
    ambiguousHeadings, emptyShellIds, droppedChars,
  };
}
