import type { Skill } from "@mariozechner/pi-coding-agent";

interface RouteRule {
  skillName: string;
  priority: number;
  minScore: number;
  positive: RegExp[];
  negative?: RegExp[];
}

const STOCK_CODE_RE = /\b(?:sh|sz|bj)?\d{6}\b|\b\d{4,5}(?:\.hk)?\b/i;

const ROUTE_RULES: RouteRule[] = [
  {
    skillName: "portfolio-review",
    priority: 100,
    minScore: 1,
    positive: [/持仓复盘/, /复盘.*持仓/, /调仓/, /组合优化/, /持仓健康/, /我的股票怎么样/, /复盘一下/],
    negative: [/查看持仓/, /看下.*持仓/, /当前持仓/, /录入持仓/],
  },
  {
    skillName: "portfolio",
    priority: 90,
    minScore: 1,
    positive: [/查看持仓/, /看下.*持仓/, /我的持仓/, /当前持仓/, /持仓情况/, /我的仓位/, /实时盈亏/, /盈亏/],
    negative: [/复盘/, /调仓/, /优化/, /录入持仓/, /添加持仓/],
  },
  {
    skillName: "market-analysis",
    priority: 85,
    minScore: 1,
    positive: [/大盘怎么样/, /市场怎么样/, /市场行情/, /市场环境/, /经济形势/, /宏观/, /北向资金/, /适合加仓吗/, /行业趋势/],
    negative: [/持仓/, /录入/, /交易/, /k线/, /蜡烛图/],
  },
  {
    skillName: "stock-screener",
    priority: 80,
    minScore: 1,
    positive: [/推荐.*股票/, /选股/, /筛选/, /哪些股票值得买/, /板块推荐/, /找.*股票/, /找.*标的/],
    negative: [/持仓/, /大盘/, /市场/, /宏观/, /k线/],
  },
  {
    skillName: "risk-manager",
    priority: 75,
    minScore: 1,
    positive: [/风险管理/, /仓位控制/, /怎么分配/, /买多少/, /止损/, /资金分配/, /分批建仓/],
    negative: [/持仓复盘/, /查看持仓/, /交易记录/],
  },
  {
    skillName: "candlestick-analysis",
    priority: 70,
    minScore: 1,
    positive: [/k线/, /蜡烛图/, /锤子线/, /吞没/, /十字星/, /趋势线/, /斐波那契/, /缺口/, /跳空/],
  },
  {
    skillName: "add-trade",
    priority: 65,
    minScore: 1,
    positive: [/记录交易/, /录入交易/, /交易记录/, /我卖了/, /卖出/, /买入/, /成交/, /手续费/, /清仓/],
    negative: [/查看持仓/, /持仓复盘/],
  },
  {
    skillName: "add-holding",
    priority: 60,
    minScore: 1,
    positive: [/录入持仓/, /添加持仓/, /更新持仓/, /帮我记录持仓/, /建仓/, /加仓/, /持有.*均价/, /成本价/],
    negative: [/记录交易/, /录入交易/, /手续费/, /卖出/, /清仓/],
  },
  {
    skillName: "deep-analysis",
    priority: 60,  // 提高优先级
    minScore: 1,
    positive: [
      /分析一下/,
      /分析下/,
      /全面分析/,
      /深度分析/,
      /值不值得买/,
      /投资价值/,
      /买不买/,
      /帮我看看/,
      /怎么看这只/,
      /分析一下.*股票/,
      /研究一下/,
      /评估一下/,
      /能涨吗/,
      /还能涨吗/,
      /会涨吗/,
      /上涨概率/,
      /未来走势/,
      /预测/,
      /量化分析/,
      /技术分析/,
      /信号/,
      /买入时机/,
      /卖出时机/,
      STOCK_CODE_RE,
      /股票/,
    ],
    negative: [
      /大盘/,
      /市场/,
      /宏观/,
      /北向资金/,
      /行业趋势/,
      /持仓/,
      /选股/,
      /筛选/,
      /止损/,
      /仓位/,
      /录入/,
      /交易记录/,
    ],
  },
];

let availableSkillNames = new Set<string>();

export function initSkillRouter(skills: Skill[]): void {
  availableSkillNames = new Set(skills.map(skill => skill.name));
}

function isCommandPrompt(message: string): boolean {
  return message.trimStart().startsWith("/");
}

function scoreRule(message: string, rule: RouteRule): number {
  if (rule.negative?.some(pattern => pattern.test(message))) {
    return -1;
  }

  let score = 0;
  for (const pattern of rule.positive) {
    if (pattern.test(message)) score += 1;
  }
  return score;
}

export function detectForcedSkill(userMessage: string): string | null {
  const trimmed = userMessage.trim();
  if (!trimmed || isCommandPrompt(trimmed) || availableSkillNames.size === 0) {
    return null;
  }

  const candidates = ROUTE_RULES
    .filter(rule => availableSkillNames.has(rule.skillName))
    .map(rule => ({ rule, score: scoreRule(trimmed, rule) }))
    .filter(entry => entry.score >= entry.rule.minScore)
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      return b.rule.priority - a.rule.priority;
    });

  if (candidates.length === 0) return null;
  if (candidates.length > 1) {
    const [best, second] = candidates;
    if (best.score === second.score && best.rule.priority === second.rule.priority) {
      return null;
    }
  }

  return candidates[0].rule.skillName;
}

export function rewritePromptWithSkill(userMessage: string): { prompt: string; forcedSkill: string | null } {
  const forcedSkill = detectForcedSkill(userMessage);
  if (!forcedSkill) {
    return { prompt: userMessage, forcedSkill: null };
  }

  return {
    prompt: `/skill:${forcedSkill} ${userMessage}`,
    forcedSkill,
  };
}
