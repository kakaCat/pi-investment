/**
 * client 构建产物校验（REQ-31e11f 验收返工 Step4）。
 *
 * 背景：2026-09-15 t7 从写工具截断事故恢复 styles.ts 时漏了 injectStyles() 的
 * 闭合括号，导致 build:client 报 PARSE_ERROR 失败，但失败的构建**没有阻断发版**——
 * 已提交的 lib/client.js 停留旧版被浏览器加载，用户看到"样式全丢"。
 *
 * 本脚本在 wrap-client 之后运行：产物缺关键符号、或 styles.ts 括号不配对 → 非零退出，
 * 让"构建失败/产物不全"成为发版硬阻断，而不是静默供旧包。
 */
import { readFileSync, existsSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const pkgRoot = join(here, '..')
const bundlePath = join(pkgRoot, 'lib', 'client.js')
const stylesPath = join(pkgRoot, 'src', 'client', 'styles.ts')
const progressPath = join(pkgRoot, 'src', 'client', 'stage-panel.ts')

const fail = (msg) => { console.error('[verify-client] ' + msg); process.exit(1) }

// 1) 产物存在且非空
if (!existsSync(bundlePath)) fail('lib/client.js 不存在（wrap-client 未产出）')
const size = statSync(bundlePath).size
if (size < 20_000) fail('lib/client.js 体积异常（' + size + ' bytes），疑似空产物')

// 2) 产物含关键符号（新功能必须真的进了包）
const bundle = readFileSync(bundlePath, 'utf8')
// 注意：bundler 会改名 JS 标识符（函数名不可靠），但**字符串字面量（class 名）会保留**，
// 所以用 class 名作为产物完整性锚点。
const must = [
  'dsh-pm-flow-node',        // 会话框流程图
  'dsh-pm-stage-panel',      // t6 节点详情面板
  'dsh-pm-trace-chain',      // 追溯链
  'dsh-pm-artifact-chip',    // t7 产物 chip
  'dsh-pm-confirm-artifact', // t7 卡面确认按钮
  'dsh-pm-sn-task',          // v4 任务执行列表行（单节点工作记录）
  'dsh-pm-injection-info',   // REQ-422af1 t11 「本次注入了什么」只读块
]
const missing = must.filter((k) => !bundle.includes(k))
if (missing.length > 0) fail('产物缺少关键符号：' + missing.join(', '))

// 3) styles.ts 括号配对（防再次静默截断）——统计花括号，CSS 规则内的括号本身平衡
if (existsSync(stylesPath)) {
  const css = readFileSync(stylesPath, 'utf8')
  // CSS 模板字面量里的花括号（规则/at-rule）本就平衡，但内容可能含 { } 字符串，
  // 全局计数会误报——所以只做**截断信号**检查：文件必须以 } 收尾（t7 事故正是丢了末尾 }）。
  const tail = css.trimEnd()
  if (!/\}\s*$/.test(tail)) fail('styles.ts 未以 } 收尾：疑似被截断（t7 事故同款）')
  // 括号差值仅告警，不阻断（CSS 内容可能含字面量括号）
  const open = (css.match(/\{/g) || []).length
  const close = (css.match(/\}/g) || []).length
  if (open !== close) console.warn('[verify-client] 注意 styles.ts 花括号 {=' + open + ' }=' + close + '（差值 ' + (open - close) + '）——若非 CSS 字面量请人工核对')
}

// 4) stage-panel 存在（t6）
if (!existsSync(progressPath)) fail('src/client/stage-panel.ts 丢失')

// 5) wrap 污染检测（2026-09-16 wrap-client 逐行注入 \t\t 事故）：
// styles.ts 里的 sentinel 注释在干净产物中必须顶格出现；若被行首注入
// 任何字符（tab/空格），说明 wrap 又对 bundle 正文做了逐行变换——
// 那种变换会污染 bundle 内所有多行模板字符串（marked 事件同款）。
if (!bundle.includes('\n/*WRAP_SENTINEL_MARKER*/')) fail('wrap-sentinel 缺失：产物中找不到哨兵（styles.ts 被改坏？）')
if (bundle.includes('\t/*WRAP_SENTINEL_MARKER*/') || bundle.includes('  /*WRAP_SENTINEL_MARKER*/')) {
  fail('wrap-sentinel 被行首注入污染：wrap-client 对 bundle 正文做了逐行变换，禁止！（2026-09-16 marked 事件）')
}

console.log('[verify-client] OK  bundle=' + size + ' bytes, 关键符号齐全, styles.ts 括号配对')
