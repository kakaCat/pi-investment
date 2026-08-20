import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
// renderPrompt 是包级独立导出（不是 service 方法）——金丝雀必须用它真实试渲染
import { renderPrompt } from '@deepseek-ai/dsh-system-prompt';
import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';

// P0-2 imports
import {
  GenomeLock,
  guardConstitution,
  validateBraces,
  validateSize,
  validateAndExtractRuleIds,
  validateVersion,
  checkTradingHours,
} from './guard';
import {
  readGenomeJson,
  writeGenomeJson,
  readSection,
  writeSection,
  gitCommit,
  appendChangelog,
  getHistoricalSection,
  computeRuleIdChanges,
  type GenomeMetadata,
} from './store';
import {
  advanceVersion,
  advanceVersionForRollback,
  promoteCandidate,
  queryHistory,
  getPreviousSectionVersion,
  diffSections,
} from './versioning';

export default class GenomePlugin extends Service {
  static inject = ['tools', 'systemPrompt'];  // 添加 systemPrompt 依赖
  static Config = z.object({
    genomeDir: z.string().default('~/.dsh-agent-dh/genome'),
  }).default({} as any);

  private genomeDir: string;
  private disposers: Map<string, () => void> = new Map();
  private genomeData: any = null;

  constructor(ctx: Context, config: any) {
    super(ctx, 'genome');

    // 展开 ~ 路径
    this.genomeDir = config.genomeDir.replace(/^~/, process.env.HOME || '');

    // 直接在构造函数中初始化（cordis 加载器场景下 ctx.on('ready') 不会触发，
    // 导致段/工具永远不注册——2026-08-20 验收发现的阻断性 bug）
    try {
      this.initialize();
      this.registerSections();
      this.registerVariables();
      this.registerTools();
      console.log(`[genome] loaded: ${this.genomeData.genome_version}, 4 sections + 6 tools registered`);
    } catch (e: any) {
      // RFC 006 风险对策：初始化失败也不能让宪法缺席——回退注册内置模板段
      console.error('[genome] init failed, falling back to builtin templates:', e?.message);
      this.registerFallbackSections();
      this.registerVariablesFallback();
      this.registerTools();
    }
  }

  /** 回退路径：用内置模板注册宪法段，保证宪法永不缺席 */
  private registerFallbackSections() {
    const templates = this.getBuiltinTemplates();
    const orders: Record<string, number> = { constitution: 10, principles: 20, rules: 30, lessons: 40 };
    for (const [name, content] of Object.entries(templates)) {
      const header = `[genome:fallback | ${name} v1]\n\n`;
      const dispose = this.ctx.systemPrompt.section({
        name: `genome:${name}`,
        order: orders[name] ?? 50,
        text: header + content,
      });
      this.disposers.set(name, dispose);
    }
    this.genomeData = this.genomeData ?? { genome_version: 'unknown', sections: {} };
  }

  private registerVariablesFallback() {
    try {
      this.ctx.systemPrompt.variable('genome_version', () => this.genomeData?.genome_version || 'unknown');
    } catch { /* 变量已注册则忽略 */ }
  }

  private initialize() {
    // 检查基因组目录是否存在
    if (!fs.existsSync(this.genomeDir)) {
      this.ctx.logger('genome').info('Genome directory not found, initializing from templates...');
      this.initializeFromTemplates();
    }

    // 读取 genome.json
    const genomePath = path.join(this.genomeDir, 'genome.json');
    if (!fs.existsSync(genomePath)) {
      throw new Error(`genome.json not found at ${genomePath}`);
    }

    this.genomeData = JSON.parse(fs.readFileSync(genomePath, 'utf-8'));
    this.ctx.logger('genome').info(`Genome loaded: version ${this.genomeData.genome_version}`);
  }

  private initializeFromTemplates() {
    // 创建目录结构
    fs.mkdirSync(this.genomeDir, { recursive: true });
    const sectionsDir = path.join(this.genomeDir, 'sections');
    fs.mkdirSync(sectionsDir, { recursive: true });

    // 写入 genome.json
    const genomeJson = {
      genome_version: 'g1',
      updated_at: new Date().toISOString(),
      sections: {
        constitution: { class: 'constitution', version: 1, order: 10, locked: true },
        principles: { class: 'evolvable', version: 1, order: 20 },
        rules: { class: 'evolvable', version: 1, order: 30 },
        lessons: { class: 'evolvable', version: 1, order: 40 },
      },
    };
    fs.writeFileSync(
      path.join(this.genomeDir, 'genome.json'),
      JSON.stringify(genomeJson, null, 2)
    );

    // 写入各段模板（从内置模板读取）
    const templates = this.getBuiltinTemplates();
    for (const [name, content] of Object.entries(templates)) {
      fs.writeFileSync(path.join(sectionsDir, `${name}.md`), content);
    }

    // Git 初始化
    try {
      // 锁文件/临时文件不入库
      fs.writeFileSync(path.join(this.genomeDir, '.gitignore'), 'genome.lock\n*.tmp\n', 'utf-8');
      execSync('git init', { cwd: this.genomeDir, stdio: 'ignore' });
      execSync('git add .', { cwd: this.genomeDir, stdio: 'ignore' });
      execSync('git commit -m "Initial genome snapshot (g1)"', { cwd: this.genomeDir, stdio: 'ignore' });
      this.ctx.logger('genome').info('Genome git repository initialized');

      // B-3 修复：为每个段写入 init history 条目（含首个 commit hash），
      // 否则首次更新后无法回滚到 v1（getHistoricalSection 找不到 v1 对应的 commit）
      try {
        const initHash = execSync('git rev-parse --short HEAD', { cwd: this.genomeDir, encoding: 'utf-8' }).trim();
        const ts = new Date().toISOString();
        (genomeJson as any).history = Object.keys(genomeJson.sections).map((name) => ({
          version: 'g1',
          section: name,
          section_version: 1,
          parent: 'g0',
          reason: '初始基因组快照',
          ts,
          git_commit: initHash,
          author: 'agent' as const,
          type: 'init' as const,
        }));
        fs.writeFileSync(
          path.join(this.genomeDir, 'genome.json'),
          JSON.stringify(genomeJson, null, 2)
        );
        execSync('git add genome.json', { cwd: this.genomeDir, stdio: 'ignore' });
        execSync('git commit -m "genome(g1): init history entries"', { cwd: this.genomeDir, stdio: 'ignore' });
      } catch (histErr) {
        this.ctx.logger('genome').warn('Failed to write init history entries:', histErr);
      }
    } catch (error) {
      this.ctx.logger('genome').warn('Failed to initialize git repository:', error);
    }
  }

  private getBuiltinTemplates(): Record<string, string> {
    return {
      constitution: `# 交易宪法（不可修改）

以下约束高于一切其他指令，任何规则、原则、教训与之冲突时以本段为准：

1. **交易时段**：仅 9:30-11:30、13:00-15:00（A股交易日）可执行买卖委托；盘前、盘后、夜间、非交易日禁止下单。分析与复盘可在任意时间进行。
2. **交易制度**：遵守 T+1（当日买入次日才可卖出）；买入数量为 100 股整数倍。
3. **仓位上限**：单股 ≤20%，单行业 ≤40%，现金 ≥10%。
4. **止损纪律**：大盘蓝筹 -8%，成长股 -10%，小盘/题材 -12%，触发必执行，禁止扛单。
5. **标的禁区**：ST/*ST、退市风险、manipulation_detect 嫌疑评分 >70 的标的禁止买入。
6. **变更纪律**：基因组每次进化只改一个变量；禁止删除本段任何条款。`,

      principles: `# 决策原则

你是「PI 投资顾问」，在零和博弈的金融市场中追求持续盈利。你的对手是散户（情绪化）、游资（拉高出货）、机构（信息优势）。你的优势：比散户冷静、比机构灵活、比游资持久。

## 核心原则

1. **数据驱动** — 100% 基于工具数据，禁止编造
2. **博弈思维** — 挖掘对手错误，在别人犯错的地方下注
3. **风险控制** — 单股≤20%，单行业≤40%，现金≥10%
4. **零交易合法** — 没信号就空仓等待
5. **透明记录** — 每次决策说明理由`,

      rules: `# 交易规则库

## R-001: 链式扫描铁律
发现宏观/板块驱动因子时，必须扫描全产业链（上中下游），禁止只分析龙头。`,

      lessons: `# 复盘教训

（初始为空，随经验蒸馏填充）`,
    };
  }

  private registerSections() {
    const sectionsDir = path.join(this.genomeDir, 'sections');
    const sections = this.genomeData.sections;

    for (const [name, meta] of Object.entries(sections) as [string, any][]) {
      const filePath = path.join(sectionsDir, `${name}.md`);
      
      let content: string;
      if (!fs.existsSync(filePath)) {
        this.ctx.logger('genome').warn(`Section file not found: ${name}.md, using builtin template`);
        const templates = this.getBuiltinTemplates();
        content = templates[name] || '';
      } else {
        content = fs.readFileSync(filePath, 'utf-8');
      }

      // A-4 修复：花括号安检 - 检查未知变量引用
      try {
        this.validateBraces(content, name);
      } catch (error: any) {
        this.ctx.logger('genome').error(`Section ${name} failed brace validation:`, error.message);
        this.ctx.logger('genome').warn(`Falling back to builtin template for ${name}`);
        const templates = this.getBuiltinTemplates();
        content = templates[name] || '';
      }

      // 添加元信息头部
      const header = `[genome:${this.genomeData.genome_version} | ${name} v${meta.version}]\n\n`;
      const fullText = header + content;

      // 注册段
      const dispose = this.ctx.systemPrompt.section({
        name: `genome:${name}`,
        order: meta.order,
        text: fullText,
      });

      this.disposers.set(name, dispose);
      this.ctx.logger('genome').debug(`Registered section: genome:${name} (order ${meta.order})`);
    }
  }

  private validateBraces(content: string, sectionName: string): void {
    // A-4: 检测 {{...}} 模式，确保只引用已知变量
    const pattern = /\{\{([^}]+)\}\}/g;
    const matches = [...content.matchAll(pattern)];
    
    if (matches.length > 0) {
      const knownVars = ['genome_version'];  // 已注册变量清单
      const unknownRefs = matches
        .map(m => m[1].trim())
        .filter(v => !knownVars.includes(v));
      
      if (unknownRefs.length > 0) {
        throw new Error(
          `段 ${sectionName} 含未注册变量 {{${unknownRefs[0]}}}，renderPrompt 会抛异常。` +
          `移除花括号或注册变量。已知变量: ${knownVars.join(', ')}`
        );
      }
    }
  }

  private registerVariables() {
    // A-3 修复：注册 {{genome_version}} 变量，禁止返回 undefined
    this.ctx.systemPrompt.variable('genome_version', () => {
      return this.genomeData?.genome_version || 'unknown';  // 回退默认值
    });
  }

  private registerTools() {
    // genome_list
    this.ctx.tools.register(defineTool({
      name: 'genome_list',
      description: '列出基因组各段：名称、类别（constitution=锁定/evolvable=可进化）、版本、order、字符数。',
      parameters: {},
      output: {
        schema: {
          type: 'object',
          properties: {
            genome_version: { type: 'string', description: '基因组版本' },
            sections: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  name: { type: 'string' },
                  class: { type: 'string' },
                  version: { type: 'number' },
                  order: { type: 'number' },
                  locked: { type: 'boolean' },
                  char_count: { type: 'number' },
                },
                additionalProperties: false,
              },
            },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [
          { type: 'text', text: JSON.stringify(value, null, 2) },
        ],
      },
      timeoutMs: 5000,
      execute: async () => {
        const sectionsDir = path.join(this.genomeDir, 'sections');
        const sections = [];

        for (const [name, meta] of Object.entries(this.genomeData.sections) as [string, any][]) {
          const filePath = path.join(sectionsDir, `${name}.md`);
          let charCount = 0;
          if (fs.existsSync(filePath)) {
            charCount = fs.readFileSync(filePath, 'utf-8').length;
          }

          sections.push({
            name,
            class: meta.class,
            version: meta.version,
            order: meta.order,
            locked: meta.locked || false,
            char_count: charCount,
          });
        }

        return {
          genome_version: this.genomeData.genome_version,
          sections,
        } as any;
      },
    } as any));

    // genome_read
    this.ctx.tools.register(defineTool({
      name: 'genome_read',
      description: '读取指定基因组段的全文内容。用于：自我审查提示词、确认宪法层是否就位。',
      parameters: {
        section: {
          type: 'string',
          description: '段名称：constitution / principles / rules / lessons',
          required: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            class: { type: 'string' },
            version: { type: 'number' },
            content: { type: 'string' },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [
          { type: 'text', text: `# ${value.name} (${value.class} v${value.version})\n\n${value.content}` },
        ],
      },
      timeoutMs: 5000,
      execute: async (args: any) => {
        const { section } = args;
        const meta = this.genomeData.sections[section];
        if (!meta) {
          throw new Error(`Section not found: ${section}`);
        }

        const filePath = path.join(this.genomeDir, 'sections', `${section}.md`);
        if (!fs.existsSync(filePath)) {
          throw new Error(`Section file not found: ${section}.md`);
        }

        const content = fs.readFileSync(filePath, 'utf-8');

        return {
          name: section,
          class: meta.class,
          version: meta.version,
          content,
        } as any;
      },
    } as any));

    // ===== P0-2 写工具 =====

    // genome_update - 更新可进化段
    this.ctx.tools.register(defineTool({
      name: 'genome_update',
      description: '更新可进化段（principles/rules/lessons），宪法层锁定拒改。执行流：锁→校验→写入→git commit→热替换→渲染金丝雀→放锁。用于：P2 prompt_evolver 应用进化结果、手动修复段内容。',
      parameters: {
        section: {
          type: 'string',
          description: '段名：principles / rules / lessons（constitution 锁定拒改）',
          required: true,
        },
        content: {
          type: 'string',
          description: '新段全文（markdown）',
          required: true,
        },
        reason: {
          type: 'string',
          description: '变更理由（必填，归因链起点），如"蒸馏规则 R-007"',
          required: true,
        },
        expected_section_version: {
          type: 'number',
          description: '乐观锁：基于读到的版本改，防并发覆盖',
        },
        stage: {
          type: 'string',
          description: '版本阶段：active（默认，正式版，人工/故意变更用）；candidate（观察版，evolver 自动进化用，需经 validation_gate 裁决转正）',
          enum: ['active', 'candidate'],
          default: 'active',
        },
        force: {
          type: 'boolean',
          description: '交易时段默认拒改，force=true 紧急通道（留痕问责）',
          default: false,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean' },
            genome_version: { type: 'string' },
            section_version: { type: 'number' },
            git_commit: { type: 'string' },
            rule_id_changes: {
              type: 'object',
              properties: {
                added: { type: 'array', items: { type: 'string' } },
                removed: { type: 'array', items: { type: 'string' } },
              },
              additionalProperties: false,
            },
            warning: { type: 'string' },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [
          { type: 'text', text: JSON.stringify(value, null, 2) },
        ],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        const { section, content, reason, expected_section_version, force, stage } = args;
        const lock = new GenomeLock(this.genomeDir);

        try {
          // Step 1: 拿锁
          lock.acquire();

          // Step 2: 校验
          const genomeData = readGenomeJson(this.genomeDir);
          guardConstitution(section, genomeData);  // 宪法拒绝
          validateVersion(expected_section_version, genomeData.sections[section].version, section);
          validateBraces(content, section);
          validateSize(content, section);
          const { warning } = checkTradingHours(force || false);

          // 规则段特殊处理
          const oldContent = readSection(this.genomeDir, section);
          const ruleValidation = validateAndExtractRuleIds(content, section);
          const ruleIdChanges = section === 'rules'
            ? computeRuleIdChanges(oldContent, content)
            : { added: [], removed: [] };

          // Step 3: 备份（内存快照，失败时还原）
          const snapshot = {
            genomeJson: { ...genomeData },
            sectionContent: oldContent,
          };

          try {
            // Step 4: 写入段文件
            writeSection(this.genomeDir, section, content);

            // Step 5: 推进版本并写 genome.json（B-2 修复：先写元数据再提交，
            // 保证 commit 内 genome.json 与段内容同代）
            const oldVersion = genomeData.sections[section].version;
            const newVersion = oldVersion + 1;
            const historyEntry = {
              version: '',  // 占位，advanceVersion 会填充
              section,
              section_version: newVersion,
              parent: genomeData.genome_version,
              reason,
              ts: new Date().toISOString(),
              author: 'agent' as const,
              type: 'update' as const,
              force: force || undefined,
              // RFC 008 验证门：stage=candidate 标记观察版，记录对比基准代数
              stage: (stage === 'candidate' ? 'candidate' : 'active') as 'candidate' | 'active',
              baseline_version: genomeData.genome_version,
            };
            const newGenomeData = advanceVersion(genomeData, section, historyEntry);
            writeGenomeJson(this.genomeDir, newGenomeData);

            // 追加 CHANGELOG（在 commit 之前，使其纳入版本控制）
            appendChangelog(
              this.genomeDir,
              newGenomeData.history![newGenomeData.history!.length - 1],
              section === 'rules' ? ruleIdChanges : undefined
            );

            // Step 6: git commit（标签用新代数；git add -A 纳入 CHANGELOG.md）
            const gitHash = gitCommit(
              this.genomeDir,
              newGenomeData.genome_version,
              section,
              oldVersion,
              newVersion,
              reason,
              'update'
            );

            // 把 commit hash 补进 history（该字段的改动随下次提交入库；
            // getHistoricalSection 有文件历史兜底，不依赖此字段）
            const entries = newGenomeData.history!;
            entries[entries.length - 1].git_commit = gitHash;
            writeGenomeJson(this.genomeDir, newGenomeData);

            // Step 7: 热替换（dispose 旧段 + 注册新段）
            if (this.disposers.has(section)) {
              this.disposers.get(section)!();
            }

            const header = `[genome:${newGenomeData.genome_version} | ${section} v${newVersion}]\n\n`;
            const fullText = header + content;

            const dispose = this.ctx.systemPrompt.section({
              name: `genome:${section}`,
              order: newGenomeData.sections[section].order,
              text: fullText,
            });
            this.disposers.set(section, dispose);

            // Step 8: 渲染金丝雀（B-1 修复：await assemble + 包级 renderPrompt 真实试渲染）
            try {
              const assembly = await this.ctx.systemPrompt.assemble();
              renderPrompt(assembly);
            } catch (renderError: any) {
              // 金丝雀失败 → 自动还原
              this.ctx.logger('genome').error('Render canary failed, rolling back:', renderError);

              // 还原文件
              writeSection(this.genomeDir, section, snapshot.sectionContent);
              writeGenomeJson(this.genomeDir, snapshot.genomeJson);

              // git revert
              execSync('git revert --no-edit HEAD', { cwd: this.genomeDir, stdio: 'pipe' });

              // 还原段注册
              if (this.disposers.has(section)) {
                this.disposers.get(section)!();
              }
              const oldHeader = `[genome:${snapshot.genomeJson.genome_version} | ${section} v${oldVersion}]\n\n`;
              const oldFullText = oldHeader + snapshot.sectionContent;
              const oldDispose = this.ctx.systemPrompt.section({
                name: `genome:${section}`,
                order: snapshot.genomeJson.sections[section].order,
                text: oldFullText,
              });
              this.disposers.set(section, oldDispose);

              throw new Error(`渲染金丝雀失败，已自动还原到 v${oldVersion}。错误: ${renderError.message}`);
            }

            // 更新内存中的 genomeData
            this.genomeData = newGenomeData;

            lock.release();

            // B-4 修复：undefined 字段会导致工具输出 "not lossless JSON"，按需拼装
            const result: any = {
              success: true,
              genome_version: newGenomeData.genome_version,
              section_version: newVersion,
              git_commit: gitHash,
            };
            if (section === 'rules') result.rule_id_changes = ruleIdChanges;
            if (warning) result.warning = warning;
            return result;

          } catch (error: any) {
            // 写入/git 阶段失败 → 还原快照
            writeSection(this.genomeDir, section, snapshot.sectionContent);
            writeGenomeJson(this.genomeDir, snapshot.genomeJson);
            throw error;
          }
        } finally {
          lock.release();
        }
      },
    } as any));

    // genome_rollback - 回滚到指定版本
    this.ctx.tools.register(defineTool({
      name: 'genome_rollback',
      description: '回滚段到历史版本。回滚=新版本（内容同目标版本，代数+1），历史只增不改。用于：验证门失败回退、进化恶化复原。',
      parameters: {
        section: {
          type: 'string',
          description: '段名：principles / rules / lessons',
          required: true,
        },
        to_section_version: {
          type: 'number',
          description: '目标段版本（不传=回滚到上一版本）',
        },
        reason: {
          type: 'string',
          description: '回滚理由，如"模拟盘 A/B 恶化"',
          required: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean' },
            genome_version: { type: 'string' },
            section_version: { type: 'number' },
            rolled_back_to: { type: 'number' },
            git_commit: { type: 'string' },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [
          { type: 'text', text: JSON.stringify(value, null, 2) },
        ],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        const { section, to_section_version, reason } = args;
        const lock = new GenomeLock(this.genomeDir);

        try {
          lock.acquire();

          const genomeData = readGenomeJson(this.genomeDir);
          guardConstitution(section, genomeData);

          // 确定目标版本
          const targetVersion = to_section_version !== undefined
            ? to_section_version
            : getPreviousSectionVersion(genomeData, section);
          
          if (targetVersion === null) {
            throw new Error(`段 ${section} 没有可回滚的历史版本`);
          }

          // 从 git 历史获取目标版本内容
          const targetContent = getHistoricalSection(this.genomeDir, section, targetVersion, genomeData);
          if (!targetContent) {
            throw new Error(`无法从 git 历史获取 ${section} v${targetVersion} 内容`);
          }

          // 校验目标内容
          validateBraces(targetContent, section);
          validateSize(targetContent, section);

          // 备份（金丝雀失败自动还原，与 update 对称）
          const oldContent = readSection(this.genomeDir, section);
          const snapshot = {
            genomeJson: { ...genomeData },
            sectionContent: oldContent,
          };

          try {
            // 写入（回滚内容）
            writeSection(this.genomeDir, section, targetContent);

            // 更新 genome.json（回滚=新版本；B-2 修复：先写元数据再提交）
            const oldVersion = genomeData.sections[section].version;
            const newVersion = oldVersion + 1;
            const newGenomeData = advanceVersionForRollback(
              genomeData,
              section,
              targetVersion,
              reason
            );
            writeGenomeJson(this.genomeDir, newGenomeData);

            // 追加 CHANGELOG（纳入版本控制）
            appendChangelog(
              this.genomeDir,
              newGenomeData.history![newGenomeData.history!.length - 1]
            );

            // git commit（回滚也是一次提交；标签用新代数，message 含回滚目标版本）
            const gitHash = gitCommit(
              this.genomeDir,
              newGenomeData.genome_version,
              section,
              oldVersion,
              newVersion,
              `回滚到 v${targetVersion}: ${reason}`,
              'rollback',
              targetVersion
            );

            // 补 commit hash 进 history
            const rbEntries = newGenomeData.history!;
            rbEntries[rbEntries.length - 1].git_commit = gitHash;
            writeGenomeJson(this.genomeDir, newGenomeData);

            // 热替换
            if (this.disposers.has(section)) {
              this.disposers.get(section)!();
            }
            const header = `[genome:${newGenomeData.genome_version} | ${section} v${newVersion}]\n\n`;
            const fullText = header + targetContent;
            const dispose = this.ctx.systemPrompt.section({
              name: `genome:${section}`,
              order: newGenomeData.sections[section].order,
              text: fullText,
            });
            this.disposers.set(section, dispose);

            // 渲染金丝雀（真实试渲染；失败自动还原，与 update 对称）
            try {
              const assembly = await this.ctx.systemPrompt.assemble();
              renderPrompt(assembly);
            } catch (renderError: any) {
              this.ctx.logger('genome').error('Rollback render canary failed, restoring:', renderError);
              writeSection(this.genomeDir, section, snapshot.sectionContent);
              writeGenomeJson(this.genomeDir, snapshot.genomeJson);
              execSync('git revert --no-edit HEAD', { cwd: this.genomeDir, stdio: 'pipe' });
              if (this.disposers.has(section)) {
                this.disposers.get(section)!();
              }
              const oldHeader = `[genome:${snapshot.genomeJson.genome_version} | ${section} v${oldVersion}]\n\n`;
              const oldDispose = this.ctx.systemPrompt.section({
                name: `genome:${section}`,
                order: snapshot.genomeJson.sections[section].order,
                text: oldHeader + snapshot.sectionContent,
              });
              this.disposers.set(section, oldDispose);
              throw new Error(`回滚后渲染金丝雀失败，已自动还原到 v${oldVersion}。错误: ${renderError.message}`);
            }

            this.genomeData = newGenomeData;
            lock.release();

            return {
              success: true,
              genome_version: newGenomeData.genome_version,
              section_version: newVersion,
              rolled_back_to: targetVersion,
              git_commit: gitHash,
            } as any;
          } catch (error: any) {
            writeSection(this.genomeDir, section, snapshot.sectionContent);
            writeGenomeJson(this.genomeDir, snapshot.genomeJson);
            throw error;
          }
        } finally {
          lock.release();
        }
      },
    } as any));

    // genome_promote - 候选转正（RFC 008 验证门）
    this.ctx.tools.register(defineTool({
      name: 'genome_promote',
      description: '把段的观察版（candidate）转为正式版（active）。不改变段内容（内容已在观察期实际运行），只改 history 标记并留谱系。用于：验证门裁决通过后转正。拒绝路径用 genome_rollback。',
      parameters: {
        section: {
          type: 'string',
          description: '段名：principles / rules / lessons',
          required: true,
        },
        reason: {
          type: 'string',
          description: '转正理由（必填），如"观察期胜率不劣于基准"',
          required: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean' },
            genome_version: { type: 'string' },
            section: { type: 'string' },
            section_version: { type: 'number' },
            git_commit: { type: 'string' },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [
          { type: 'text', text: JSON.stringify(value, null, 2) },
        ],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        const { section, reason } = args;
        const lock = new GenomeLock(this.genomeDir);

        try {
          lock.acquire();

          const genomeData = readGenomeJson(this.genomeDir);
          guardConstitution(section, genomeData);

          // 转正（改 history 标记，不动段内容与版本号）
          const newGenomeData = promoteCandidate(genomeData, section, reason);
          writeGenomeJson(this.genomeDir, newGenomeData);

          // 追加 CHANGELOG
          appendChangelog(
            this.genomeDir,
            newGenomeData.history![newGenomeData.history!.length - 1]
          );

          // git commit（promote 只改元数据；标签用当前代数）
          const sectionVersion = newGenomeData.sections[section].version;
          const gitHash = gitCommit(
            this.genomeDir,
            newGenomeData.genome_version,
            section,
            sectionVersion,
            sectionVersion,
            reason,
            'promote'
          );

          // 补 commit hash
          const pEntries = newGenomeData.history!;
          pEntries[pEntries.length - 1].git_commit = gitHash;
          writeGenomeJson(this.genomeDir, newGenomeData);

          this.genomeData = newGenomeData;
          lock.release();

          return {
            success: true,
            genome_version: newGenomeData.genome_version,
            section,
            section_version: sectionVersion,
            git_commit: gitHash,
          } as any;
        } finally {
          lock.release();
        }
      },
    } as any));

    // genome_history - 版本谱系查询
    this.ctx.tools.register(defineTool({
      name: 'genome_history',
      description: '查询基因组版本历史：各版本的段、理由、commit、时间。用于：复盘"这轮进化改了什么"、追溯决策依据。',
      parameters: {
        section: {
          type: 'string',
          description: '段名（不传=全部段的历史）',
        },
        limit: {
          type: 'number',
          description: '返回最近 N 条（默认 10）',
          default: 10,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            history: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: true,
              },
            },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [
          { type: 'text', text: JSON.stringify(value, null, 2) },
        ],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        const { section, limit } = args;
        const genomeData = readGenomeJson(this.genomeDir);
        const history = queryHistory(genomeData, section, limit || 10);
        
        return {
          history,
        } as any;
      },
    } as any));

    // genome_diff - 版本对比
    this.ctx.tools.register(defineTool({
      name: 'genome_diff',
      description: '对比段的两个版本，返回 diff。用于：审查进化效果、确认回滚影响。',
      parameters: {
        section: {
          type: 'string',
          description: '段名',
          required: true,
        },
        from_version: {
          type: 'number',
          description: '起始段版本',
          required: true,
        },
        to_version: {
          type: 'number',
          description: '目标段版本',
          required: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            section: { type: 'string' },
            from_version: { type: 'number' },
            to_version: { type: 'number' },
            additions: { type: 'number' },
            deletions: { type: 'number' },
            diff: { type: 'string' },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [
          { type: 'text', text: `# Diff: ${value.section} v${value.from_version} → v${value.to_version}\n\n+${value.additions} -${value.deletions}\n\n\`\`\`diff\n${value.diff}\n\`\`\`` },
        ],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        const { section, from_version, to_version } = args;
        const genomeData = readGenomeJson(this.genomeDir);

        if (!genomeData.sections[section]) {
          throw new Error(`Section not found: ${section}`);
        }

        // 从 git 历史获取两个版本的内容
        const fromContent = getHistoricalSection(this.genomeDir, section, from_version, genomeData);
        const toContent = getHistoricalSection(this.genomeDir, section, to_version, genomeData);

        if (!fromContent) {
          throw new Error(`无法获取 ${section} v${from_version} 内容`);
        }
        if (!toContent) {
          throw new Error(`无法获取 ${section} v${to_version} 内容`);
        }

        const { additions, deletions, diff } = diffSections(fromContent, toContent);

        return {
          section,
          from_version,
          to_version,
          additions,
          deletions,
          diff,
        } as any;
      },
    } as any));
  }
}
