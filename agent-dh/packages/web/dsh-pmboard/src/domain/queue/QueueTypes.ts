/**
 * 队列文件类型契约（REQ-260927202051-f6df · S-1 / FR-1 / FR-5）。
 *
 * 任务数据从台账 `dsh-reqboard.json` 的 `tasks[]` 迁到按需求分片的
 * `docs/requirements/<REQ>/queue.json`。本文件是该文件的**唯一类型定义处**。
 *
 * ⚠️ 两条硬约束（改动前务必先读）：
 *
 * 1. **QueueTask 必须完整包含 TaskRecord 的全部字段**——本文件用 `extends TaskRecord`
 *    而非重新罗列字段，就是为了让"少一个字段"在**编译期**就不可能发生。
 *    理由（architecture.md 决策 1）：读方改造要把 36 处**台账任务通道**的读点换成队列，
 *    若队列只存裁剪投影，每个读方都得回别处补齐 20+ 个字段（acceptance / implementation /
 *    lastRun / revisions / executions …），回归面反而放大。少迁一个字段的后果不是报错而是
 *    **静默失效**：例如缺 `lastRun` 会让子卡完工凭证门永远判不通过、缺 `lastReport`
 *    会让 done 凭证门永远拦人。
 *
 * 2. **队列只比 TaskRecord 多一个字段：`layer`**。任何新增的"队列专有字段"都会
 *    打破这条不变量，也就打破了 tests/queue-types.test.ts 的类型级断言。
 *
 * 本文件是纯类型：不 import node:/@deepseek-ai/，不碰时间与随机数（与 domain/task/* 同构）。
 */

import type { TaskRecord } from '../../shared/protocol.js'

/**
 * 队列**格式**版本（管 QueueFile 自身结构的演进：增删字段或改变字段语义时 +1）。
 *
 * 与 `QueueFile.schemaVersion` 分工不同，别混：
 * - `version`（本常量）→ 队列文件格式，管解析方能否读懂这个文件
 * - `schemaVersion`   → 该文件写入时对应的**台账时代**（迁移后为 9），管迁移判定
 */
export const QUEUE_VERSION = 1

/**
 * 队列中的任务 = 完整 TaskRecord + DAG 层级。
 *
 * `layer` 是派生的（由 topology.computeLayers 计算），不是源数据；
 * 它落在队列文件里是为了让文件本身可读（打开就能看出执行批次），而非权威事实。
 */
export interface QueueTask extends TaskRecord {
  /** DAG 层级：0 = 无依赖，n = 依赖方最大 layer + 1。派生字段，写回时整份重算 */
  layer: number
}

/** 依赖边：`from` 是 `to` 的前置任务（由 tasks[].dependsOn 展开得到） */
export interface QueueEdge {
  from: string
  to: string
}

/** 层级分组：同层任务互不依赖，可并行 */
export interface QueueLayer {
  layer: number
  tasks: string[]
}

/**
 * 校验规则编号（单一事实源在 design/data-model.md「数据约束」）。
 *
 * 四份文档共用同一套编号，改任一规则必须同步：
 * data-model.md（定义）/ interfaces.md（接口）/ test-cases.md（用例）/ use-cases.md（场景）。
 */
export type ValidationRule = 'V-1' | 'V-2' | 'V-3' | 'V-4' | 'V-5' | 'V-6'

/**
 * 单条校验问题。
 *
 * `path` 用 JSON 路径风格定位（如 `tasks[2].dependsOn[0]`），便于人直接跳去改；
 * 缺失字段类问题 path 就是字段名（如 `ready`）。
 */
export interface ValidationIssue {
  rule: ValidationRule
  message: string
  path?: string
}

/**
 * 校验结果。
 *
 * `validateQueueFile` **不抛错**：失败也返回对象、只填 issues。
 * 由调用方按场景决定处置（写入前拒绝落盘 / 读取后降级返回空 / 更新前保持旧内容）——
 * 三种处置的差异见 design/interfaces.md「数据校验接口」。
 */
export interface ValidationResult {
  passed: boolean
  issues: ValidationIssue[]
}

/**
 * 队列文件：某需求的**任务唯一存储**（含派生 DAG 视图）。
 *
 * 文件位置：`docs/requirements/<REQ>/queue.json`
 *
 * 注意 `tasks` / `edges` / `layers` / `ready` 四者的关系：
 * - `tasks` 是**源数据**（完整任务卡）
 * - `edges` / `layers` / `ready` 都是**派生的**，写回时整份重算，不允许手工编辑
 */
export interface QueueFile {
  /** 队列格式版本（见 QUEUE_VERSION） */
  version: number
  /** 所属需求 ID；其每个 task.requirementId 必须与之相等（V-3 防跨需求串档） */
  requirement_id: string
  /** 该文件写入时对应的台账 schema 版本（迁移后为 9）；用于判定文件出处 */
  schemaVersion: number
  /** 生成时间（ISO 8601） */
  generated_at: string
  /** 最后一次写回时间（ISO 8601）；从未更新过则缺省 */
  updated_at?: string
  /** 任务卡（完整 TaskRecord + layer） */
  tasks: QueueTask[]
  /** 依赖边（由 dependsOn 展开） */
  edges: QueueEdge[]
  /** 层级分组（拓扑排序结果） */
  layers: QueueLayer[]
  /** 当前可执行任务 id（依赖已全部 done 且自身 todo） */
  ready: string[]
}
