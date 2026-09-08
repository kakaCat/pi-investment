// dsh-pmboard · 项目看板（RFC 014）
// M1 host 半：reqboard JSON+SSE API（/dashboard/api/reqboard/*）+ 两级状态机台账。
// 模块形状与 dashboard-execution 一致（name + apply 具名导出）；路由经
// (ctx as any).inject(['webServer']) 惰性注入 + webCtx.effect 包裹注册。
// client 半（泳道看板 GUI）在 M3 落地。

import { Context } from '@deepseek-ai/cordis';
import * as os from 'node:os';
import * as path from 'node:path';
import { ReqboardStore } from './host/store.js';
import { createReqboardHandler } from './host/routes.js';
import { SessionSyncService } from './host/session-sync.js';

export const name = 'dsh-pmboard';

/** 台账文件名（DSH 主目录，卸载插件不删除）。 */
export const LEDGER_FILE = 'dsh-reqboard.json';

interface PluginConfig {
  /** DSH 主目录（默认 ~/.dsh） */
  dshHome?: string;
}

export function dshHomePath(config: PluginConfig | undefined, file: string): string {
  const home = config?.dshHome || process.env.DSH_HOME || path.join(os.homedir(), '.dsh');
  return path.join(home, file);
}

export function apply(ctx: Context, config?: PluginConfig): void {
  const logger = ctx.logger(name);
  const store = new ReqboardStore({ file: dshHomePath(config, LEDGER_FILE) });
  // 急加载：fresh boot 时让首个 GET /state 见到台账而非空板（load 永不抛——损坏即隔离）
  void store.load();
  const now = () => Date.now();

  // 会话同步服务（M2）：监听 session/event，自动捕获新会话进待归类区
  let sessionSync: SessionSyncService | undefined
  try {
    sessionSync = new SessionSyncService(
      { store, now },
      { on: (event, handler) => ctx.on(event as never, handler as never) },
    )
    logger.info('session sync service started (M2: turn/start + user/message → triage)')
  } catch (err) {
    logger.warn('session sync service failed to start:', err)
  }

  (ctx as unknown as { inject?: (services: string[], cb: (webCtx: any) => void) => void }).inject?.(
    ['webServer'],
    (webCtx: { effect?: (fn: () => void, label?: string) => void; webServer?: any }) => {
      webCtx.effect?.(() => {
        webCtx.webServer.register({
          kind: 'prefix',
          path: '/dashboard/api/reqboard',
          handler: createReqboardHandler({ store, now }),
        });
      }, name + ': api');
      logger.info('routes registered: /dashboard/api/reqboard/* (M1+M2: state/events/req/task/triage CRUD + 闸门 + 会话捕获); client half lands in M3');
    },
  );

  // teardown
  ctx.on('dispose', () => {
    sessionSync?.dispose()
  })
}
