import * as lockfile from "proper-lockfile";
import { existsSync } from "fs";

/**
 * 文件锁服务
 * 提供文件级别的互斥锁，防止并发修改导致数据不一致
 */
export class FileLockService {
  /**
   * 在锁保护下执行操作
   * @param filePath 要锁定的文件路径
   * @param operation 要执行的操作（读-修改-写）
   * @returns 操作结果
   */
  static async withLock<T>(
    filePath: string,
    operation: () => T | Promise<T>
  ): Promise<T> {
    // 如果文件不存在，先创建一个空文件以便加锁
    if (!existsSync(filePath)) {
      const fs = await import("fs/promises");
      await fs.writeFile(filePath, "", "utf-8");
    }

    // 获取锁
    const release = await lockfile.lock(filePath, {
      retries: {
        retries: 10,
        minTimeout: 50,
        maxTimeout: 500,
      },
      stale: 10000, // 10秒后认为锁过期
    });

    try {
      // 执行操作
      return await operation();
    } finally {
      // 释放锁
      await release();
    }
  }

  /**
   * 同步版本：在锁保护下执行操作
   * @param filePath 要锁定的文件路径
   * @param operation 要执行的操作（读-修改-写）
   * @returns 操作结果
   */
  static withLockSync<T>(filePath: string, operation: () => T): T {
    // 如果文件不存在，先创建一个空文件以便加锁
    if (!existsSync(filePath)) {
      const fs = require("fs");
      fs.writeFileSync(filePath, "", "utf-8");
    }

    // 获取锁（同步 API 不支持 retries 选项）
    const release = lockfile.lockSync(filePath, {
      stale: 10000, // 10秒后认为锁过期
    });

    try {
      // 执行操作
      return operation();
    } finally {
      // 释放锁
      release();
    }
  }
}
