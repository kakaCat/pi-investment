// REQ-f6307c T3：文件化诊断日志 —— 修复「诊断依赖 stdout，而 stdout 可能进了死管道」的观测面盲区。
//
// 背景（2026-09-21 T2 误诊复盘）：T2 依据「日志里看不到 capture hook registered」判定
// apply() 未执行，实为三重观测错误——①查错路径（~/Library/Logs 非 plist 配置路径）
// ②配置的 launchd.out.log 自 09-19 起停更（进程被外部 shell 手工拉起，未经 launchd）
// ③当前进程 stdout 指向已无读者的管道（start.sh | tail -5），所有 console/logger 输出蒸发。
// 教训：诊断日志必须落文件，禁止只依赖 stdout。
//
// 形状：append-only 文本，超 512KB 轮转为 .1（只保留一代，够用且零依赖）。
// 任何失败静默吞掉——诊断通道绝不能反过来影响主流程（对齐 isolation-trace 的容错设计）。

import * as fs from 'node:fs';
import * as path from 'node:path';

export const CAPTURE_DIAG_REL = 'state/reqboard-capture-diag.log';

const MAX_BYTES = 512 * 1024;

let diagFile: string | undefined;

/** 组合根（index.ts apply）启动时调用一次，传入 dshHome 解析后的绝对路径。 */
export function initCaptureDiag(absPath: string): void {
  diagFile = absPath;
  try {
    fs.mkdirSync(path.dirname(absPath), { recursive: true });
  } catch {
    /* 目录创建失败不致命，写时会再试 */
  }
}

/** 写一条诊断：控制台 + 文件双写。控制台可能进死管道，文件才是可靠观测面。 */
export function captureDiag(message: string): void {
  const line = '[' + new Date().toISOString() + '] ' + message + '\n';
  // 文件优先（可靠面）
  if (diagFile !== undefined) {
    try {
      const st = fs.statSync(diagFile);
      if (st.size > MAX_BYTES) {
        fs.renameSync(diagFile, diagFile + '.1');
      }
    } catch {
      /* 不存在或 stat 失败 → 直接 append */
    }
    try {
      fs.appendFileSync(diagFile, line);
    } catch {
      /* 写失败静默——诊断不挡主流程 */
    }
  }
  // 控制台尽力而为（可能无人读，不判断也不抛）
  try {
    console.log(message);
  } catch {
    /* EPIPE 等静默 */
  }
}
