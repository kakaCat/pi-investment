/**
 * Genome Plugin - Prompt Genome Management
 * 管理 prompt 基因组的读取、更新、验证和版本控制
 */
import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { renderPrompt } from '@deepseek-ai/dsh-system-prompt';
import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';

// P0-2 imports
import {
  GenomeLock,
} from './guard';

// BaseTool 重构后的工具类
import {
  GenomeListTool,
  GenomeReadTool,
  GenomeUpdateTool,
  GenomeRollbackTool,
  GenomePromoteTool,
  GenomeHistoryTool,
} from './tools';
import type { GenomeWriteHost } from './tools/host';

export default class GenomePlugin extends Service {
  static inject = ['tools', 'systemPrompt'];  // 添加 systemPrompt 依赖
  static Config = z.object({
    genomeDir: z.string().default('~/.dsh-agent-dh/genome'),
  }).default({} as any);

  private genomeDir: string;
  private disposers: Map<string, () => void> = new Map();
  private genomeData: any = null;
  private lock!: GenomeLock;
  private lockGuard: any;

  constructor(ctx: Context, config: any) {
    super(ctx, 'genome');

    // 展开 ~ 路径
    this.genomeDir = config.genomeDir.replace(/^~/, process.env.HOME || '');

    // 直接在构造函数中初始化（cordis 加载器场景下 ctx.on('ready') 不会触发，
    // 导致段/工具永远不注册——2026-08-20 验收发现的阻断性 bug）
    let useFallback = false;
    let sectionsRegistered = false;

    try {
      this.initialize();
      // 初始化成功，注册段和工具
      this.registerSections();
      this.registerVariables();
      sectionsRegistered = true;
      this.registerTools();
      console.log(`[genome] loaded: ${this.genomeData.genome_version}, 4 sections + 6 tools registered`);
    } catch (e: any) {
      // RFC 006 风险对策：初始化失败也不能让宪法缺席——回退注册内置模板段
      console.error('[genome] init failed, falling back to builtin templates:', e?.message);
      useFallback = true;

      // 只有在 section 还没注册时才注册 fallback section
      if (!sectionsRegistered) {
        try {
          this.registerFallbackSections();
          this.registerVariablesFallback();
        } catch (fallbackError: any) {
          console.error('[genome] fallback registration also failed:', fallbackError?.message);
        }
      }
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

    // 初始化锁和版本管理器
    this.lock = new GenomeLock(this.genomeDir);

    // lockGuard: 包装 GenomeLock 为异步接口
    this.lockGuard = {
      acquire: async () => {
        this.lock.acquire();
        return () => this.lock.release();
      }
    };
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

  /** GenomeWriteHost：热替换段注册（dispose 旧段 → 注册新段） */
  hotSwapSection(section: string, genomeVersion: string, sectionVersion: number, order: number, content: string): void {
    if (this.disposers.has(section)) {
      this.disposers.get(section)!();
    }
    const header = `[genome:${genomeVersion} | ${section} v${sectionVersion}]\n\n`;
    const fullText = header + content;
    const dispose = this.ctx.systemPrompt.section({
      name: `genome:${section}`,
      order,
      text: fullText,
    });
    this.disposers.set(section, dispose);
    this.ctx.logger('genome').info(`Hot-swapped section genome:${section} (v${sectionVersion}, ${genomeVersion})`);
  }

  /** GenomeWriteHost：渲染金丝雀（真实试渲染；失败抛错由工具自动还原） */
  async canaryRender(): Promise<void> {
    const assembly = await this.ctx.systemPrompt.assemble();
    renderPrompt(assembly);
  }

  private registerTools(): void {
    const { ctx } = this;

    ctx.tools.register(new GenomeListTool(
      this.genomeDir,
      this.genomeData
    ).toDSHToolDefinition() as any);

    ctx.tools.register(new GenomeReadTool(
      this.genomeDir,
      this.genomeData
    ).toDSHToolDefinition() as any);

    ctx.tools.register(new GenomeUpdateTool(
      this.genomeDir,
      this.genomeData,
      this.lockGuard,
      this as GenomeWriteHost
    ).toDSHToolDefinition() as any);

    ctx.tools.register(new GenomeRollbackTool(
      this.genomeDir,
      this.genomeData,
      this.lockGuard,
      this as GenomeWriteHost
    ).toDSHToolDefinition() as any);

    ctx.tools.register(new GenomePromoteTool(
      this.genomeDir,
      this.genomeData,
      this.lockGuard,
      this as GenomeWriteHost
    ).toDSHToolDefinition() as any);

    ctx.tools.register(new GenomeHistoryTool(
      this.genomeDir,
      this.genomeData
    ).toDSHToolDefinition() as any);
  }
}
