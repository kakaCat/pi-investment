// @pi-investment/dashboard-requirement · 需求看板（RFC 014）
// M1 host 半：reqboard JSON+SSE API（/dashboard/api/reqboard/*）+ 两级状态机台账。
// 模块形状与 dashboard-execution 一致（name + apply 具名导出）；路由经
// (ctx as any).inject(['webServer']) 惰性注入 + webCtx.effect 包裹注册。
// client 半（泳道看板 GUI）在 M3 落地。

import { Context } from '@deepseek-ai/cordis';
import * as os from 'node:os';
import * as path from 'node:path';
import { ReqboardStore } from './host/store.js';
import { createReqboardHandler } from './host/routes.js';

export const name = 'dashboard-requirement';

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
      logger.info('routes registered: /dashboard/api/reqboard/* (M1: state/events/req/task CRUD + 闸门); client half lands in M3');
    },
  );
}
