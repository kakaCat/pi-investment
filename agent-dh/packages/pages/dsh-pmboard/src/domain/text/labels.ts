/**
 * 用户可见**文案单点**（REQ-47939a 返工：专门解决"魔法字符串"）。
 *
 * 为什么必须单点：弹框选项文案此前在 **host 与 client 各写一份**——`application/use-cases/AcceptSheet.ts`
 * 的 `OPT_PASS = '✅ 通过'` 与 `client/stage-panel.ts` 的徽章表 `{ passed: '✅ 通过' }`。
 * 两处靠人肉保持一致，一旦改文案而漏改另一侧，就会出现"用户点的是'✅ 通过'、前端显示成别的"这种
 * **静默不一致**（用户验收意见点到的就是这个：`options: [{ label: OPT_PASS, ... }]`）。
 * 单点之后：改文案只改这里，host 判定与 client 渲染引用同一个常量。
 *
 * 边界：只放**会被比较/会影响控制流**的文案（选项 label 必须与用户点击值精确相等，
 * 徽章要与人看到的一致）。纯叙述性长句不必进本文件——过度集中会把消息变得难读。
 *
 * @module dsh-pmboard/domain/text/labels
 */

/** 验收单项弹框选项（**判定用**：用户点击值需与本常量精确相等）。
 * 
 * 当前实现：二态判定（passed / failed），"部分通过"/"推迟验收"等场景通过 opinion 字段补充说明。
 * 未来扩展：若需要多态判定（partial/deferred 等中间态），需配套修改状态机与归档逻辑。
 */
export const ACCEPT_ITEM_OPTIONS = {
  pass: '✅ 通过',
  clarify: '💬 需要澄清（仍计为"改进"，请在意见中说明）',
  fix: '🛠 改进（需修改）',
  other: '❓ 其他',
} as const

/** 全部通过后的终确认弹框：肯定项文案（判定用）。 */
export const FINAL_PASS_LABEL = '✅ 验收通过并归档'

/** 终确认弹框：否定项文案（判定用；与 FINAL_PASS_LABEL 成对）。 */
export const FINAL_DECLINE_LABEL = '暂不归档'

/** 验收单项状态徽章（client 渲染用；与 ACCEPT_ITEM_OPTIONS 同源，避免两处漂移）。 */
export const ITEM_STATUS_BADGE = {
  pending: '⬜ 待验',
  passed: ACCEPT_ITEM_OPTIONS.pass,
  failed: '❌ 不通过',
} as const

/** 确认弹框（reqboard_ask_confirm）缺省选项。理解差异 ≠ 需要修改；新增内容 ≠ 修改现有内容。 */
export const DEFAULT_CONFIRM_OPTIONS = [
  '确认，推进到下一阶段 (Recommended)',
  '需要澄清（有疑问，但不一定要改）',
  '需要补充内容（现有内容对，但不够完整）',
  '需要修改',
  '暂停',
] as const
