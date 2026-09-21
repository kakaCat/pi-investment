/**
 * 验收文档完整性检查（REQ-308b9a FR-7 / AC-7.4~7.5）。
 *
 * 纯规则：输入"需求目录下的文件集合 + 已登记任务 id"，输出缺失清单。零 I/O。
 *
 * **9 类文档口径**（NFR-3：必须与本仓实际文档标准对齐，不另造清单）——
 * 即本仓 feature 流水线的既有产物（`docs/architecture/documentation-standard.md` +
 * `category-doc-sets.ts` 的 requiredDesignDocs），R-7 示例里的
 * technical-design / frontend-spec / backend-spec / ui-design 在本仓统一收敛为 `design/*.md`：
 *

 *   3 design/architecture.md   4 design/data-model.md
 *   5 design/interfaces.md     6 design/test-cases.md
 *   7 decomposition.md    8 tasks/<taskId>.md（每任务一份）
 *   9 reviews/ 与 tests/ 非空（评审与测试证据）
 *
 * @module dsh-pmboard/domain/workflow/DocCompleteness
 */

import { fmt } from '../text/fmt.js'

/** 单类文档的判定：命中集为空 → 该类缺失。 */
export interface DocClass {
  /** 稳定键（缺失清单与测试断言用） */
  key: string
  /** 人读名称（提示补哪一份） */
  label: string
  /** 文件相对路径谓词（相对 docs/requirements/<REQ>/） */
  hit: (path: string) => boolean
}

/** 第 8 类需要逐任务判定，故单独表达。 */
export const TASK_CARD_CLASS_KEY = 'task_cards'

export const VERIFICATION_DOC_CLASSES: readonly DocClass[] = [
  { key: 'requirement', label: 'requirement.md（需求文档）', hit: p => p === 'requirement.md' },

  { key: 'design_architecture', label: 'design/architecture.md（架构）', hit: p => p === 'design/architecture.md' },
  { key: 'design_data_model', label: 'design/data-model.md（数据模型）', hit: p => p === 'design/data-model.md' },
  { key: 'design_interfaces', label: 'design/interfaces.md（接口）', hit: p => p === 'design/interfaces.md' },
  { key: 'design_test_cases', label: 'design/test-cases.md（测试用例）', hit: p => p === 'design/test-cases.md' },
  { key: 'decomposition', label: 'decomposition.md（拆分计划）', hit: p => p === 'decomposition.md' },
  { key: 'reviews', label: 'reviews/（评审报告，非空）', hit: p => p.startsWith('reviews/') && p.endsWith('.md') },
  { key: 'tests', label: 'tests/（测试证据，非空）', hit: p => p.startsWith('tests/') },
]

export interface DocCheckResult {
  passed: boolean
  /** 缺失文档的人读清单（空 = 齐） */
  missing: string[]
}

export interface DocCheckInput {
  /** 需求目录下的相对路径集合（见 VERIFICATION_DOC_CLASSES 的口径） */
  files: ReadonlySet<string>
  /** 本需求已登记任务 id（校验"每任务一份卡"） */
  taskIds: readonly string[]
}

/** 逐类检查 9 类文档，返回缺失清单。 */
export function checkDocCompleteness(input: DocCheckInput): DocCheckResult {
  const missing: string[] = []
  for (const cls of VERIFICATION_DOC_CLASSES) {
    if (![...input.files].some(p => cls.hit(p))) missing.push(cls.label)
  }
  // 第 8 类：每个已登记任务一份 tasks/<taskId>.md
  for (const id of input.taskIds) {
    if (!input.files.has('tasks/' + id + '.md')) missing.push(fmt('tasks/{id}.md（任务卡）', { id }))
  }
  return { passed: missing.length === 0, missing }
}
