/**
 * 立项三问 · 题目与答案映射（REQ-e3b6a0 t8 / FR-7）——纯逻辑，零 I/O、零端口。
 *
 * 为什么单独一个模块（而不是留在用例里）：
 *  ① 它是**表单契约**（三问题目 + 答案映射 + 缺项默认），与"弹框 + 创建"的编排正交，
 *     独立后可被用例、测试与输出契约扫描各自引用而不互相牵连；
 *  ② 输出契约静态扫描按"工具 → 响应源文件"逐行抓 return 键（tests/output-contract.test.ts），
 *     编排文件里的内部映射对象会被误判成"未声明的响应字段"——分离即让两件事各归其位。
 *
 * 口径事实源：四问 = 需求名称 / 需求类型 / 提示词难度 / 文档位置（与 CreateTool/prompt.ts、
 * capture-section.ts、QueryState.ts 三处注入文案同一份口径）。
 *
 * @module dsh-pmboard/application/internal/capture-mapping
 */
import type { AskAnswer, AskQuestion } from '../ports.js'
import {
  ALL_PROMPT_DIFFICULTIES,
  ALL_REQ_CATEGORIES,
  type PromptDifficulty,
  type RequirementCategory,
} from '../../shared/protocol.js'
import { LIMITS } from '../../domain/limits.js'

/** 四问的稳定 id（答案按 id 回收，不靠顺序）。 */
export const CAPTURE_QUESTION_IDS = {
  name: 'name',
  category: 'category',
  difficulty: 'difficulty',
  doc_location: 'doc_location',
} as const

/** 预定义的文档位置选项 */
export const DOC_LOCATION_OPTIONS = [
  { 
    label: 'docs/requirements/<REQ>/', 
    description: '推荐 - 标准需求目录' 
  },
  { 
    label: 'docs/rfcs/', 
    description: 'RFC 设计提案' 
  },
  { 
    label: 'docs/architecture/', 
    description: '架构文档' 
  },
  { 
    label: 'docs/guides/', 
    description: '操作指南' 
  },
] as const

/** 缺项回落用的既有默认（与 reqboard_create 的 schema 默认一致）。 */
export const CAPTURE_DEFAULTS = {
  category: 'feature' as RequirementCategory,
  difficulty: 'standard' as PromptDifficulty,
  docLocation: 'docs/requirements/<REQ>/',
}

/** 拒绝立项的标记前缀 */
export const REJECT_PREFIX = '✖️'

/** 四问题目（选项顺序即推荐顺序：首个 = 推荐位）。 */
export function buildCaptureQuestions(titleOptions: readonly string[]): AskQuestion[] {
  // 需求名称选项：拒绝选项 + 用户候选
  const nameOptions = [
    // 特殊选项：拒绝立项（放在首位）
    { 
      label: `${REJECT_PREFIX} 不需要立项`, 
      description: '⚠️ 选择此项将取消本次立项' 
    },
    // 用户提供的候选名称
    ...titleOptions
      .map(label => label.trim())
      .filter(label => label.length > 0)
      .slice(0, 3)
      .map((label, i) => ({ label, ...(i === 0 ? { description: '推荐' } : {}) })),
  ]
  
  return [
    {
      id: CAPTURE_QUESTION_IDS.name,
      header: '需求名称',
      question: titleOptions.length > 0 
        ? '需求名称（可选候选、自定义输入，或选择"不需要立项"）' 
        : '需求名称（自定义输入，或选择"不需要立项"）',
      options: nameOptions,
    },
    {
      id: CAPTURE_QUESTION_IDS.category,
      header: '需求类型',
      question: '需求类型',
      options: ALL_REQ_CATEGORIES.map((label, i) => ({ label, ...(i === 0 ? { description: '推荐' } : {}) })),
    },
    {
      id: CAPTURE_QUESTION_IDS.difficulty,
      header: '提示词难度',
      question: '提示词难度',
      options: ALL_PROMPT_DIFFICULTIES.map(label => ({
        label,
        ...(label === CAPTURE_DEFAULTS.difficulty ? { description: '推荐' } : {}),
      })),
    },
    {
      id: CAPTURE_QUESTION_IDS.doc_location,
      header: '需求文档位置',
      question: '需求文档存放位置（选择预设路径或自定义输入）',
      options: DOC_LOCATION_OPTIONS.map((opt, i) => ({
        ...opt,
        ...(i === 0 ? {} : {}), // 首个已有"推荐"标记
      })),
    },
  ]
}

/** 四问作答 → 创建参数的映射结果（defaultsUsed = 走了默认值的问项 id，回执里如实说明）。 */
export interface CaptureMapping {
  title: string
  category: RequirementCategory
  difficulty: PromptDifficulty
  docLocation: string
  rejected: boolean
  answers: { 
    title: string
    category: string
    difficulty: string
    docLocation: string
  }
  defaultsUsed: string[]
}

/** 单问取值：自定义输入优先，否则取首个选项。 */
function pickAnswer(answers: readonly AskAnswer[], id: string): string {
  const answer = answers.find(a => a.id === id)
  const custom = (answer?.custom ?? '').trim()
  if (custom.length > 0) return custom
  return ((answer?.selected ?? [])[0] ?? '').trim()
}

/**
 * 答案映射契约（FR-7 第 4 条）：名称优先 custom；类型/难度取选项，非法或缺失回落既有默认
 * 并记进 defaultsUsed。**不猜名称**——名称为空即由调用方响亮失败（没有可回落的默认）。
 * 新增：检测拒绝立项标记、处理文档位置。
 */
export function mapCaptureAnswers(answers: readonly AskAnswer[]): CaptureMapping {
  const rawTitle = pickAnswer(answers, CAPTURE_QUESTION_IDS.name)
  const title = rawTitle.slice(0, LIMITS.titleMax)
  
  // 检测是否选择拒绝立项
  const rejected = title.startsWith(REJECT_PREFIX)
  
  const rawCategory = pickAnswer(answers, CAPTURE_QUESTION_IDS.category)
  const categoryOk = (ALL_REQ_CATEGORIES as readonly string[]).includes(rawCategory)
  const rawDifficulty = pickAnswer(answers, CAPTURE_QUESTION_IDS.difficulty)
  const difficultyOk = (ALL_PROMPT_DIFFICULTIES as readonly string[]).includes(rawDifficulty)
  
  // 文档位置：自定义输入或选项，缺失时回落默认
  const rawDocLocation = pickAnswer(answers, CAPTURE_QUESTION_IDS.doc_location)
  const docLocation = rawDocLocation.length > 0 ? rawDocLocation : CAPTURE_DEFAULTS.docLocation
  
  const defaultsUsed: string[] = []
  if (!categoryOk) defaultsUsed.push(CAPTURE_QUESTION_IDS.category)
  if (!difficultyOk) defaultsUsed.push(CAPTURE_QUESTION_IDS.difficulty)
  if (rawDocLocation.length === 0) defaultsUsed.push(CAPTURE_QUESTION_IDS.doc_location)
  
  return {
    title,
    category: categoryOk ? (rawCategory as RequirementCategory) : CAPTURE_DEFAULTS.category,
    difficulty: difficultyOk ? (rawDifficulty as PromptDifficulty) : CAPTURE_DEFAULTS.difficulty,
    docLocation,
    rejected,
    answers: {
      title,
      category: categoryOk ? rawCategory : rawCategory.length > 0 ? rawCategory : CAPTURE_DEFAULTS.category,
      difficulty: difficultyOk ? rawDifficulty : rawDifficulty.length > 0 ? rawDifficulty : CAPTURE_DEFAULTS.difficulty,
      docLocation,
    },
    defaultsUsed,
  }
}