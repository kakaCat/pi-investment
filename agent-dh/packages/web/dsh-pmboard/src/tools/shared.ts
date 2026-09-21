/**
 * 工具壳共享（REQ-47939a t8）——工具壳的通用渲染助手。
 * @module dsh-pmboard/tools/shared
 */
export const renderJson = (_args: unknown, value: unknown) => [
  { type: 'text', text: JSON.stringify(value, null, 2) },
]

/**
 * 人话首行渲染（REQ-c48f99 t1/t4 / FR-5）：首行 = 中文摘要（≤120 字符单行），
 * 空行后附 JSON 明细。通用卡输出区与 errorSummary 都取首行——未注册定制卡片的
 * 工具也立即获得可读摘要，零框架改动。
 *
 * renderJson 保留兼容（旧调用方零影响）；工具迁移时逐换 renderSmart(summarize)。
 * summarize 契约：输入为工具返回值；输出必须是**单行**（多行会被首行语义截断）。
 */
export const renderSmart =
  (summarize: (value: unknown) => string) =>
  (_args: unknown, value: unknown) => {
    const line = summarize(value).split('\n')[0].slice(0, 120)
    return [{ type: 'text', text: line + '\n\n' + JSON.stringify(value, null, 2) }]
  }
