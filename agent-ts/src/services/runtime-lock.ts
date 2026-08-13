/**
 * Automation Runtime Lock - 自动化运行时锁
 *
 * 背景（2026-08-13）：agent 拆两种运行形态——
 *   - headless（start-headless.ts）：调度器 + wake gateway + 飞书 bot，常驻后台
 *   - TUI（index.ts）：人工交互会话
 * 两形态同跑会 triple 冲突：调度任务双跑、3002 端口抢占、飞书 bot 双连。
 * 锁持有者独占「自动化三件套」（scheduler/gateway/feishu），后到者降级为纯交互模式。
 *
 * 机制：pidfile（.pi-invest/automation.lock）+ PID 存活探测（process.kill(pid, 0)）。
 * 进程死亡锁自动失效（陈旧锁下次启动时被回收）。
 */

import { existsSync, readFileSync, writeFileSync, unlinkSync } from "fs";
import { join } from "path";

export interface AutomationLockInfo {
  pid: number;
  role: "headless" | "tui";
  startedAt: string;
}

function lockPath(piDir: string): string {
  return join(piDir, "automation.lock");
}

function isPidAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    // EPERM = 进程存在但无权发信号（如 root 进程）→ 活体；ESRCH = 不存在
    if ((err as NodeJS.ErrnoException).code === "EPERM") return true;
    return false;
  }
}

/** 读取当前有效锁（陈旧锁返回 null 并顺手清理） */
export function readLiveAutomationLock(piDir: string): AutomationLockInfo | null {
  const p = lockPath(piDir);
  if (!existsSync(p)) return null;
  try {
    const info = JSON.parse(readFileSync(p, "utf-8")) as AutomationLockInfo;
    if (typeof info.pid === "number" && isPidAlive(info.pid)) return info;
    // 陈旧锁：进程已死
    unlinkSync(p);
    return null;
  } catch {
    return null;
  }
}

/**
 * 尝试获取自动化锁。成功返回 true；已被活体持有返回 false（调用方应降级）。
 * 本进程已持有时幂等返回 true。
 */
export function acquireAutomationLock(piDir: string, role: "headless" | "tui"): boolean {
  const existing = readLiveAutomationLock(piDir);
  if (existing) {
    return existing.pid === process.pid;
  }
  const info: AutomationLockInfo = {
    pid: process.pid,
    role,
    startedAt: new Date().toISOString(),
  };
  writeFileSync(lockPath(piDir), JSON.stringify(info, null, 2));
  return true;
}

/** 释放锁（仅持有者可释放） */
export function releaseAutomationLock(piDir: string): void {
  const existing = readLiveAutomationLock(piDir);
  if (existing && existing.pid === process.pid) {
    try {
      unlinkSync(lockPath(piDir));
    } catch {
      // 已不存在，忽略
    }
  }
}

/** 测试专用：强制清理锁文件 */
export function resetAutomationLockForTests(piDir: string): void {
  const p = lockPath(piDir);
  if (existsSync(p)) unlinkSync(p);
}
