/**
 * 队列文件路径约定（REQ-260927202051-f6df）——**路径格式的单一事实源**。
 *
 * ## 为什么放在 domain 层
 *
 * `queue.json` 落在 `docs/requirements/<REQ>/queue.json` 这条事实，被两侧同时需要：
 * - **application 层**（`Decompose` 要把 `queue_file` 返回给调用方）——不能 import repositories/adapters
 *   （`tests/layer-boundary.test.ts` 明令 application 不得依赖基础设施）；
 * - **infrastructure 层**（`QueueRepository` 真正决定往哪落盘）。
 *
 * 曾经两份各写一遍：`QueueRepository.relativePathOf` 一份、`Decompose` 就地拼字符串一份。
 * 这正是本需求要消灭的那类**静默分歧**——哪天格式一改（换目录、加子目录、改文件名），
 * 一份改了另一份没改，症状是"队列写在这儿、读在那儿"，表现为看板静默空白。
 *
 * domain 是最内层，application 与 infrastructure 都可 import，因此是唯一能同时被两侧引用的位置。
 *
 * ## 约束
 *
 * 本文件是**纯数据 + 纯函数**：不 import 任何模块（domain 不许碰 `node:`、框架包、`shared/`
 * 与上层模块，见 `tests/layer-boundary.test.ts` 的 `domain` 规则）——因此这里也**不能**用
 * `node:path` 去 join，路径分隔符一律用 `/`（本仓所有工作区相对路径都是这个口径）。
 */

/** 需求目录前缀（与 `docs/requirements/<REQ>/` 的仓内约定一致）。 */
export const REQUIREMENTS_DIR = 'docs/requirements'

/** 队列文件名（需求目录内）。 */
export const QUEUE_FILENAME = 'queue.json'

/**
 * `docs/requirements/<REQ>/queue.json`（**工作区相对路径**，分隔符恒为 `/`）。
 *
 * 用途：`QueueRepository.pathOf/relativePathOf` 的路径拼接、`Decompose` 返回体的 `queue_file`、
 * 日志与错误信息。**不得**用它反推绝对路径——绝对路径由 `QueueRepository` 按 workspaceRoot 拼。
 */
export function queueRelativePath(requirementId: string): string {
  return `${REQUIREMENTS_DIR}/${requirementId}/${QUEUE_FILENAME}`
}
