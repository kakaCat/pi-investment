/**
 * runtime-lock 单元测试
 */
import { mkdtempSync, rmSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import {
  acquireAutomationLock,
  readLiveAutomationLock,
  releaseAutomationLock,
  resetAutomationLockForTests,
} from "./runtime-lock.js";

describe("automation runtime lock", () => {
  let dir: string;
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "pi-lock-test-"));
  });
  afterEach(() => {
    rmSync(dir, { recursive: true, force: true });
  });

  test("空目录无锁", () => {
    expect(readLiveAutomationLock(dir)).toBeNull();
  });

  test("本进程获取后可读且幂等", () => {
    expect(acquireAutomationLock(dir, "headless")).toBe(true);
    const lock = readLiveAutomationLock(dir);
    expect(lock).not.toBeNull();
    expect(lock!.pid).toBe(process.pid);
    expect(lock!.role).toBe("headless");
    // 同进程再获取 = 幂等
    expect(acquireAutomationLock(dir, "headless")).toBe(true);
  });

  test("持有者释放后锁消失", () => {
    acquireAutomationLock(dir, "tui");
    releaseAutomationLock(dir);
    expect(readLiveAutomationLock(dir)).toBeNull();
  });

  test("陈旧锁（死 PID）被自动回收", () => {
    acquireAutomationLock(dir, "headless");
    // 手工把锁改成死 PID（99999999 几乎不可能存活）
    const lockFile = join(dir, "automation.lock");
    writeFileSync(
      lockFile,
      JSON.stringify({ pid: 99999999, role: "headless", startedAt: "x" }),
    );
    // 读锁时应识别死亡并清理
    expect(readLiveAutomationLock(dir)).toBeNull();
    // 新进程（同进程模拟）可直接获取
    expect(acquireAutomationLock(dir, "headless")).toBe(true);
  });

  test("活体他进程持锁时获取失败", () => {
    // 用一个存活的他进程 PID：init/launchd (pid 1) 必然存活且不是我们
    const lockFile = join(dir, "automation.lock");
    writeFileSync(
      lockFile,
      JSON.stringify({ pid: 1, role: "headless", startedAt: "x" }),
    );
    expect(readLiveAutomationLock(dir)).not.toBeNull();
    expect(acquireAutomationLock(dir, "tui")).toBe(false);
  });

  test("resetAutomationLockForTests 强制清理", () => {
    acquireAutomationLock(dir, "headless");
    resetAutomationLockForTests(dir);
    expect(readLiveAutomationLock(dir)).toBeNull();
  });
});
