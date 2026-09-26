/**
 * RTM 生成器门面（REQ-260926140539-457b FR-2 / FR-9）。
 *
 * two 层 API：
 *  - RTMGenerator：按节点粒度调用（测试与 StageOverview 用）；
 *  - runRTMTrigger：按**触发点**调用，把"某个业务动作后该更新哪几个 RTM 文件"
 *    收敛到一处，并保证**失败不打断主流程**（FR-9：记录错误、返回结构化结果）。
 *
 * @module @pi-investment/reqboard/rtm/generator
 */
import { RTMContext, type RTMGeneratorConfig } from './context.js'
import { generateAcceptingRTM } from './accepting-generator.js'
import { generateBrainstormingRTM } from './brainstorming-generator.js'
import { generateDecomposingRTM } from './decomposing-generator.js'
import { generateDesignRTM } from './design-generator.js'
import { generateImplementingRTM, updateTaskDetail, type TaskDetailUpdate } from './implementing-generator.js'
import { generateLifecycleRTM } from './lifecycle-generator.js'
import type { Coverage } from './types.js'

/** RTM 生成器：7 个节点的读写入口。 */
export class RTMGenerator {
  readonly ctx: RTMContext

  constructor(config: RTMGeneratorConfig) {
    this.ctx = new RTMContext(config)
  }

  /** 触发点 1：立项 → rtm-lifecycle.yml 骨架。 */
  generateLifecycle(reqId: string) {
    return generateLifecycleRTM(this.ctx, reqId)
  }

  /** 触发点 2：提交需求文档 → rtm-brainstorming.yml。 */
  generateBrainstorming(reqId: string) {
    return generateBrainstormingRTM(this.ctx, reqId)
  }

  /** 触发点 4：提交设计文档 → rtm-design.yml。 */
  generateDesign(reqId: string) {
    return generateDesignRTM(this.ctx, reqId)
  }

  /** 触发点 5：批准拆分计划 → rtm-decomposing.yml。 */
  generateDecomposing(reqId: string) {
    return generateDecomposingRTM(this.ctx, reqId)
  }

  /** 触发点 5/6：生成 rtm-implementing.yml + 任务详情目录。 */
  generateImplementing(reqId: string) {
    return generateImplementingRTM(this.ctx, reqId)
  }

  /** 触发点 6：任务状态/子阶段变更 → 增量更新任务详情 + 汇总。 */
  updateTaskStatus(reqId: string, taskId: string, updates: TaskDetailUpdate) {
    return updateTaskDetail(this.ctx, reqId, taskId, updates)
  }

  /** 触发点 7：提交验收材料 → rtm-accepting.yml。 */
  generateAccepting(reqId: string) {
    return generateAcceptingRTM(this.ctx, reqId)
  }
}

/** 业务触发点（与需求流水线动作一一对应）。 */
export type RTMTrigger =
  | 'create'
  | 'submit:requirement'
  | 'confirm:artifact'
  | 'submit:design'
  | 'confirm:plan'
  | 'task:status'
  | 'task:report'
  | 'submit:verification'

/** 触发结果（失败也必须结构化返回，禁止静默）。 */
export interface RTMTriggerResult {
  ok: boolean
  trigger: RTMTrigger
  requirement_id: string
  /** 本次更新/生成的文件名。 */
  files: string[]
  /** 本次生成节点的覆盖度（供调用方过门禁；无覆盖度的触发点为空）。 */
  coverage?: Coverage
  error?: string
}

/** 触发点 → 更新的文件集合。 */
function filesForTrigger(trigger: RTMTrigger): string[] {
  switch (trigger) {
    case 'create':
      return ['rtm-lifecycle.yml']
    case 'submit:requirement':
      return ['rtm-brainstorming.yml', 'rtm-lifecycle.yml']
    case 'confirm:artifact':
      return ['rtm-brainstorming.yml', 'rtm-design.yml', 'rtm-lifecycle.yml']
    case 'submit:design':
      return ['rtm-design.yml', 'rtm-lifecycle.yml']
    case 'confirm:plan':
      return ['rtm-decomposing.yml', 'rtm-implementing.yml', 'rtm-lifecycle.yml']
    case 'task:status':
    case 'task:report':
      return ['rtm-implementing.yml', 'rtm-implementing/<task>.yml']
    case 'submit:verification':
      return ['rtm-accepting.yml', 'rtm-lifecycle.yml']
    default:
      return []
  }
}

/**
 * 按触发点生成/更新 RTM。**任何异常都被吞掉并结构化返回**——
 * RTM 是增强层，不能让它的失败打断需求创建/提交/确认（FR-9）。
 */
export function runRTMTrigger(
  generator: RTMGenerator,
  trigger: RTMTrigger,
  reqId: string,
  payload?: { taskId?: string; updates?: TaskDetailUpdate },
): RTMTriggerResult {
  const files = filesForTrigger(trigger)
  let coverage: Coverage | undefined
  try {
    switch (trigger) {
      case 'create':
        generator.generateLifecycle(reqId)
        break
      case 'submit:requirement':
        generator.generateBrainstorming(reqId)
        generator.generateLifecycle(reqId)
        break
      case 'confirm:artifact': {
        generator.generateBrainstorming(reqId)
        const design = generator.generateDesign(reqId)
        generator.generateLifecycle(reqId)
        coverage = design?.coverage?.design
        break
      }
      case 'submit:design': {
        const design = generator.generateDesign(reqId)
        generator.generateLifecycle(reqId)
        coverage = design?.coverage?.design
        break
      }
      case 'confirm:plan': {
        const decomposing = generator.generateDecomposing(reqId)
        generator.generateImplementing(reqId)
        generator.generateLifecycle(reqId)
        coverage = decomposing?.coverage?.implementation
        break
      }
      case 'task:status':
      case 'task:report': {
        const taskId = payload?.taskId
        if (taskId === undefined || taskId.length === 0) {
          return { ok: false, trigger, requirement_id: reqId, files, error: '缺少 taskId' }
        }
        const supplied = payload?.updates ?? {}
        // FR-3：状态以台账为唯一事实源——调用方没显式给 status 时从台账取。
        const ledgerStatus = generator.ctx.tasks(reqId).find(t => t.id === taskId)?.status
        const updates = supplied.status === undefined && ledgerStatus !== undefined
          ? { ...supplied, status: ledgerStatus }
          : supplied
        generator.updateTaskStatus(reqId, taskId, updates)
        break
      }
      case 'submit:verification': {
        const accepting = generator.generateAccepting(reqId)
        generator.generateLifecycle(reqId)
        coverage = accepting?.coverage?.testing
        break
      }
      default:
        break
    }
    return { ok: true, trigger, requirement_id: reqId, files, ...(coverage !== undefined ? { coverage } : {}) }
  } catch (err) {
    return {
      ok: false,
      trigger,
      requirement_id: reqId,
      files,
      error: err instanceof Error ? err.message : String(err),
    }
  }
}
