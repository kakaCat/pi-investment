/**
 * candidates.ts - RFC 008 candidate 登记共享模块（2026-09-03 抽取）
 *
 * 背景：BaseTool 重构(6ec5cd74) 时 PromptEvolverTool 丢失了 candidate 登记调用，
 * 导致 genome_update(stage='candidate') 只写 genome.json history、从不写 candidates.json，
 * ValidationGateTool 读 candidates.json 永远无输入 → 验证门空转（"候选 0"实证坐实）。
 *
 * 本模块统一 candidates.json 的读/写/登记，供 PromptEvolverTool（登记方）与
 * ValidationGateTool（裁决方）共用同一份实现，避免再次出现"两层各写各的"漂移。
 *
 * 观察期候选记录（RFC 008 §3.3）——字段与 ValidationGateTool 读取侧严格对齐
 */
// 2026-09-03 修复：必须顶层 ESM import——tsx 加载时模块作用域无裸 require（ESM），
// 函数内 require('fs') 仅在 CJS/vitest polyfill 下可用，会导致运行时 TypeError 假绿。
import { existsSync, readFileSync, writeFileSync, renameSync } from 'node:fs';
import { execSync } from 'node:child_process';

export interface CandidateRecord {
  id: string;
  section: string;
  section_version: number;
  genome_version: string;
  baseline_version: string;
  created_at: string;
  observe_until: string;
  status: 'watching' | 'promoted' | 'rejected';
  note?: string;
  // 2026-08-25 扩展：支持回测腿 + P4 元学习数据地基
  mutation_type?: 'prompt' | 'rule' | 'strategy_param';  // 变异类型（P4 归因用）
  strategy_id?: number;       // 策略参数类 candidate 关联的策略 ID
  params_override?: any;      // 参数变体（未来用）
  backtest_verdict?: {        // 回测腿裁决结果（P4 元学习用）
    passed: boolean;
    windows: Array<{
      label: string;
      symbol: string;
      start_date: string;
      end_date: string;
      sharpe: number;
      return_pct: number;
      max_drawdown_pct: number;
    }>;
    reason: string;
  };
  // 2026-09-03 扩展：登记期结构复核 + 变异画像（L4-B benchmark 静态腿）。
  // 背景：审计发现 g1→g18 中 38% 版本是验收/测试噪声，且 R-005→R-010 只增不验。
  // genome_update 的 guard 校验在写入时已拦截非法内容；此处为 candidate 登记时的
  // 复核留痕 + 捕获"无实质变更"空更新 + 采集 diff 画像（P4 元学习归因数据地基）。
  health_check?: {
    passed: boolean;          // 结构复核是否通过（braces/size/规则ID 重复）
    checked_at: string;
    issues: HealthIssue[];    // 结构问题清单（空 = 通过）
    size_delta: number;       // candidate vs 基线字符差（+新增 / -删减）
    rule_changes?: { added: string[]; removed: string[] };  // 仅 rules 段：标题定义行增删
    substantive: boolean;     // 相对基线是否有实质内容变更（归一化后完全相同 = false = 空更新）
    note?: string;
  };
}

export interface HealthIssue {
  code: string;       // braces / size / dup_rule_id / empty_update
  message: string;
}

/**
 * 运行候选健康检查（L4-B benchmark 静态腿，纯函数，无 IO 便于单测）
 *
 * 三组检查（与 genome/src/guard.ts 同口径——guard 在 genome_update 写入时 throw 拦截，
 * 此处收集为 issues 供登记期复核留痕与裁决引用，两处规则必须保持一致，改动须同步）：
 * 1. braces   —— 未知 {{var}} 引用（已知变量: genome_version）
 * 2. size     —— 段内容 > 8000 字符（token 膨胀）
 * 3. rules    —— R-\d{3} 标题定义行重复（正文引用不算）
 * 4. 实质变更 —— candidate 与基线归一化（去空白）后完全相同 → substantive=false（空更新）
 */
export function runHealthCheck(opts: {
  section: string;
  candidateContent: string;
  baselineContent: string | null;
}): NonNullable<CandidateRecord['health_check']> {
  const { section, candidateContent, baselineContent } = opts;
  const issues: HealthIssue[] = [];
  const KNOWN_VARS = ['genome_version'];  // 与 guard.ts validateBraces 的已知变量清单一致

  // 1. 花括号未知变量引用
  const bracePattern = /\{\{([^}]+)\}\}/g;
  for (const m of candidateContent.matchAll(bracePattern)) {
    const v = m[1].trim();
    if (!KNOWN_VARS.includes(v)) {
      issues.push({
        code: 'braces',
        message: `含未注册变量 {{${v}}}，renderPrompt 会抛异常（已知变量: ${KNOWN_VARS.join(', ')}）`,
      });
      break;  // 每类问题只报首条，避免刷屏
    }
  }

  // 2. 内容超限
  const MAX_CHARS = 8000;  // 与 guard.ts validateSize 默认一致
  if (candidateContent.length > MAX_CHARS) {
    issues.push({
      code: 'size',
      message: `段内容超限：${candidateContent.length} > ${MAX_CHARS} 字符`,
    });
  }

  // 3. rules 段：标题定义行重复（R-\d{3}；正文引用合法不算定义）
  const sizeDelta = baselineContent !== null
    ? candidateContent.length - baselineContent.length
    : candidateContent.length;
  let ruleChanges: { added: string[]; removed: string[] } | undefined;
  if (section === 'rules') {
    const defPattern = /^#{1,6}\s*(R-\d{3})\b/gm;
    const defs = [...candidateContent.matchAll(defPattern)].map(m => m[1]);
    const dups = [...new Set(defs)].filter(id => defs.filter(d => d === id).length > 1);
    if (dups.length > 0) {
      issues.push({
        code: 'dup_rule_id',
        message: `规则段含重复定义：${dups.join(', ')}（标题行重复；正文引用不算）`,
      });
    }
    // 标题定义行增删画像（与 store.ts computeRuleIdChanges 同口径）
    const oldDefs = baselineContent !== null
      ? new Set([...baselineContent.matchAll(defPattern)].map(m => m[1]))
      : new Set<string>();
    const newDefs = new Set(defs);
    const added = [...newDefs].filter(id => !oldDefs.has(id));
    const removed = [...oldDefs].filter(id => !newDefs.has(id));
    ruleChanges = { added, removed };
  }

  // 4. 实质变更：归一化（去空白）后与基线完全相同 → 空更新（噪声候选特征）
  const strip = (s: string) => s.replace(/\s+/g, '');
  const substantive = baselineContent === null
    ? strip(candidateContent).length > 0          // 无基线（如初始登记）视为有内容
    : strip(candidateContent) !== strip(baselineContent);
  if (!substantive) {
    issues.push({
      code: 'empty_update',
      message: '与基线去空白后完全相同：无实质内容变更（空更新/噪声候选）',
    });
  }

  const note = baselineContent === null
    ? '基线不可得（无前序版本或 git 历史缺失），仅做结构复核与绝对画像'
    : `相对基线 ${sizeDelta >= 0 ? '+' : ''}${sizeDelta} 字符` +
      (ruleChanges
        ? `，规则定义 ${ruleChanges.added.length > 0 ? `新增 ${ruleChanges.added.join(',')}` : '无新增'}` +
          (ruleChanges.removed.length > 0 ? `，移除 ${ruleChanges.removed.join(',')}` : '')
        : '');

  return {
    passed: issues.length === 0,
    checked_at: new Date().toISOString(),
    issues,
    size_delta: sizeDelta,
    rule_changes: ruleChanges,
    substantive,
    note: note || undefined,
  };
}

/**
 * 从 genome.json history 精确定位某段某版本的 git_commit，取该版本段文件内容
 * （与 store.ts getHistoricalSection 的 history 优先路径同口径；无 history 条目 → null，
 * 不做"文件第 N 次提交"兜底——git add -A 全量提交下文件提交序≠版本号，兜底基线不可靠）
 */
export function getSectionBaseline(
  genomeDir: string,
  sectionName: string,
  targetVersion: number
): string | null {
  if (!targetVersion || targetVersion < 1) return null;
  try {
    const genomePath = `${genomeDir}/genome.json`;
    if (!existsSync(genomePath)) return null;
    const data = JSON.parse(readFileSync(genomePath, 'utf-8'));
    const entry = (data.history || []).find(
      (e: any) => e.section === sectionName && e.section_version === targetVersion
    );
    if (!entry?.git_commit) return null;
    return execSync(
      `git show ${entry.git_commit}:sections/${sectionName}.md`,
      { cwd: genomeDir, encoding: 'utf-8' }
    );
  } catch {
    return null;
  }
}

/** 读当前段文件内容（sections/{section}.md；candidate 应用后即当前内容） */
export function readSectionContent(genomeDir: string, sectionName: string): string | null {
  try {
    const p = `${genomeDir}/sections/${sectionName}.md`;
    if (!existsSync(p)) return null;
    return readFileSync(p, 'utf-8');
  } catch {
    return null;
  }
}

/**
 * 取某 genome 版本提交时的段文件快照（git show）
 * 用于候选复核：candidate 内容以登记时 genome 版本的 git 快照为准，
 * 事后复核不因 sections 文件被后续版本覆盖而漂移
 */
export function getSectionContentAtGenome(
  genomeDir: string,
  sectionName: string,
  genomeVersion: string
): string | null {
  if (!genomeVersion) return null;
  try {
    const genomePath = `${genomeDir}/genome.json`;
    if (!existsSync(genomePath)) return null;
    const data = JSON.parse(readFileSync(genomePath, 'utf-8'));
    const entry = (data.history || []).find(
      (e: any) => e.version === genomeVersion && e.section === sectionName
    );
    if (!entry?.git_commit) return null;
    return execSync(
      `git show ${entry.git_commit}:sections/${sectionName}.md`,
      { cwd: genomeDir, encoding: 'utf-8' }
    );
  } catch {
    return null;
  }
}

/**
 * 对一条 candidate 记录执行健康检查并写回 rec.health_check（原地修改，返回 health_check）
 * candidate 内容 = 登记时 genome 版本的 git 快照（无快照时回退当前 sections 文件，
 * 两者在刚登记后等值）；基线 = genome.json history 中 section_version-1 对应的 git_commit。
 * 任何读取异常返回 null（不阻断登记主路径——健康检查是留痕增强，失败显式返回 null 而非静默）
 */
export function attachHealthCheck(
  genomeDir: string,
  rec: CandidateRecord
): NonNullable<CandidateRecord['health_check']> | null {
  try {
    // 登记时快照首选（复核不漂移）；刚登记时快照与当前文件等值
    const candidateContent =
      getSectionContentAtGenome(genomeDir, rec.section, rec.genome_version)
      ?? readSectionContent(genomeDir, rec.section);
    if (candidateContent === null) return null;
    const baselineContent = getSectionBaseline(genomeDir, rec.section, rec.section_version - 1);
    rec.health_check = runHealthCheck({
      section: rec.section,
      candidateContent,
      baselineContent,
    });
    return rec.health_check;
  } catch {
    return null;
  }
}

/** candidates.json 路径（genomeDir 由调用方经 ctx.genome.genomeDir 获取） */
export function candidatesFilePath(genomeDir: string): string {
  return `${genomeDir}/candidates.json`;
}

export function readCandidates(genomeDir: string): CandidateRecord[] {
  try {
    const p = candidatesFilePath(genomeDir);
    if (!existsSync(p)) return [];
    return JSON.parse(readFileSync(p, 'utf-8'));
  } catch {
    return [];
  }
}

export function writeCandidates(genomeDir: string, list: CandidateRecord[]): void {
  const p = candidatesFilePath(genomeDir);
  const tmp = p + '.tmp';
  writeFileSync(tmp, JSON.stringify(list, null, 2));
  renameSync(tmp, p);
}

/**
 * 登记一条新的 candidate（status='watching'），进入观察期
 * observe_until = now + observeDays 自然日（与 ValidationGateTool 过期判断一致）
 */
export function registerCandidate(opts: {
  genomeDir: string;
  section: string;
  sectionVersion: number;
  genomeVersion: string;
  baselineVersion: string;
  observeDays?: number;
  mutationType?: 'prompt' | 'rule' | 'strategy_param';
  strategyId?: number;
  paramsOverride?: any;
}): CandidateRecord {
  const days = opts.observeDays ?? 5;
  const now = new Date();
  const rec: CandidateRecord = {
    // id 带随机后缀：3 路并发注册同毫秒 Date.now() 会撞车，加后缀保证唯一
    id: `cand_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    section: opts.section,
    section_version: opts.sectionVersion,
    genome_version: opts.genomeVersion,
    baseline_version: opts.baselineVersion,
    created_at: now.toISOString(),
    observe_until: new Date(now.getTime() + days * 86400000).toISOString(),
    status: 'watching',
    mutation_type: opts.mutationType ?? 'prompt',
    strategy_id: opts.strategyId,
    params_override: opts.paramsOverride,
  };
  const list = readCandidates(opts.genomeDir);
  list.push(rec);
  writeCandidates(opts.genomeDir, list);

  // L4-B（2026-09-03）：登记即附加健康检查（结构复核 + diff 画像）。
  // candidate 内容 = genome_update 刚写入的 sections/{section}.md；基线取 history 中
  // section_version-1 的 commit。读取异常返回 null（rec.health_check 缺失）不阻断登记——
  // 但验证门裁决时对缺失 health_check 的候选做降级标注，绝不假装已质检。
  attachHealthCheck(opts.genomeDir, rec);
  // attach 原地写回 rec.health_check，需再次落盘
  writeCandidates(opts.genomeDir, list);

  return rec;
}
