/**
 * 启动恢复扫描接线（REQ-4842fe t7 / design/observability §4）：崩溃不丢链。
 *
 * 为什么抽出来：apply() 已经踩着 400 行尺寸门禁，接线细节下沉到 application 内部模块，
 * index.ts 只留一行调用。
 *
 * @module dsh-pmboard/application/internal/startup-scan
 */
import { fmt } from '../../domain/text/fmt.js'
import type { UseCaseDeps } from '../ports.js'
import { scanAndResume } from '../use-cases/AdvanceChain.js'

export interface StartupScanWiring {
  /** 台账装载（确保读到的是最新状态）。 */
  load: () => Promise<unknown>
  deps: UseCaseDeps
  info: (message: string) => void
  warn: (message: string, err: unknown) => void
}

/** 后台执行一次恢复扫描；无法推进时安静返回（不打扰）。 */
export function scheduleStartupScan(wire: StartupScanWiring): void {
  void wire
    .load()
    .then(() => scanAndResume(wire.deps))
    .then((outcomes) => {
      const moved = outcomes.filter((o) => o.steps.length > 0)
      if (moved.length > 0) {
        wire.info(fmt('reqboard 自动链恢复扫描：{list}', {
          list: moved.map((o) => fmt('{req}({stop})', { req: o.requirementId, stop: o.stopped })).join(', '),
        }))
      }
    })
    .catch((err) => wire.warn('reqboard 自动链恢复扫描失败（不影响服务）:', err))
}
