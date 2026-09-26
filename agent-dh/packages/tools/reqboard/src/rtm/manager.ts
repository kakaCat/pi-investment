import * as fs from 'fs/promises';
import * as path from 'path';
import * as yaml from 'yaml';
import {
  RtmLifecycle,
  RtmBrainstorming,
  RtmDesign,
  RtmDecomposing,
  RtmImplementing,
  RtmAccepting,
  AnyRtm,
  RtmStage,
  RTM_FILENAMES,
  RtmMetadata,
} from '../types/rtm';

/**
 * RTM 管理器
 * 统一管理所有 RTM 文件的读写、版本管理、文件锁
 */
export class RtmManager {
  private requirementDir: string;
  private lockMap: Map<string, boolean> = new Map();

  constructor(requirementDir: string) {
    this.requirementDir = requirementDir;
  }

  /**
   * 获取 RTM 文件路径
   */
  private getRtmPath(stage: RtmStage): string {
    return path.join(this.requirementDir, RTM_FILENAMES[stage]);
  }

  /**
   * 获取文件锁（简单的进程内锁，防止并发写）
   */
  private async acquireLock(stage: RtmStage, timeoutMs = 5000): Promise<void> {
    const lockKey = `${this.requirementDir}:${stage}`;
    const startTime = Date.now();

    while (this.lockMap.get(lockKey)) {
      if (Date.now() - startTime > timeoutMs) {
        throw new Error(`Failed to acquire lock for ${stage} after ${timeoutMs}ms`);
      }
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    this.lockMap.set(lockKey, true);
  }

  /**
   * 释放文件锁
   */
  private releaseLock(stage: RtmStage): void {
    const lockKey = `${this.requirementDir}:${stage}`;
    this.lockMap.delete(lockKey);
  }

  /**
   * 读取 RTM 文件
   */
  async read<T extends AnyRtm>(stage: RtmStage): Promise<T | null> {
    const filePath = this.getRtmPath(stage);

    try {
      const content = await fs.readFile(filePath, 'utf-8');
      return yaml.parse(content) as T;
    } catch (error: any) {
      if (error.code === 'ENOENT') {
        return null;
      }
      throw new Error(`Failed to read RTM file ${filePath}: ${error.message}`);
    }
  }

  /**
   * 写入 RTM 文件（自动加锁、版本管理）
   */
  async write<T extends AnyRtm>(
    stage: RtmStage,
    data: T,
    options: {
      incrementVersion?: boolean;
      backupOld?: boolean;
    } = {}
  ): Promise<void> {
    const { incrementVersion = true, backupOld = false } = options;

    await this.acquireLock(stage);

    try {
      const filePath = this.getRtmPath(stage);

      // 读取旧版本（用于版本号递增和备份）
      let oldData: T | null = null;
      try {
        oldData = await this.read<T>(stage);
      } catch (error) {
        // 文件不存在，忽略
      }

      // 备份旧文件
      if (backupOld && oldData) {
        const backupPath = `${filePath}.backup-${Date.now()}`;
        await fs.writeFile(backupPath, yaml.stringify(oldData), 'utf-8');
      }

      // 版本号递增
      if (incrementVersion && oldData && 'metadata' in oldData && 'metadata' in data) {
        const oldMetadata = (oldData as any).metadata as RtmMetadata;
        const newMetadata = (data as any).metadata as RtmMetadata;
        
        if (oldMetadata.version !== undefined) {
          newMetadata.version = oldMetadata.version + 1;
        } else {
          newMetadata.version = 1;
        }

        newMetadata.last_updated = new Date().toISOString();
      }

      // 写入文件
      const yamlContent = yaml.stringify(data, { indent: 2 });
      await fs.writeFile(filePath, yamlContent, 'utf-8');
    } finally {
      this.releaseLock(stage);
    }
  }

  /**
   * 更新 RTM 文件（部分更新，保留其他字段）
   */
  async update<T extends AnyRtm>(
    stage: RtmStage,
    updater: (current: T) => T
  ): Promise<void> {
    await this.acquireLock(stage);

    try {
      const current = await this.read<T>(stage);
      if (!current) {
        throw new Error(`RTM file for stage ${stage} does not exist`);
      }

      const updated = updater(current);
      await this.write(stage, updated, { incrementVersion: true });
    } finally {
      this.releaseLock(stage);
    }
  }

  /**
   * 读取 rtm-lifecycle.yml
   */
  async getLifecycle(): Promise<RtmLifecycle | null> {
    return this.read<RtmLifecycle>('lifecycle');
  }

  /**
   * 更新当前阶段
   */
  async updateStage(newStage: string): Promise<void> {
    await this.update<RtmLifecycle>('lifecycle', (lifecycle) => {
      lifecycle.lifecycle.current_stage = newStage;

      // 更新阶段状态
      lifecycle.lifecycle.stages = lifecycle.lifecycle.stages.map((stage) => {
        if (stage.stage === newStage) {
          return {
            ...stage,
            status: 'in_progress' as const,
            entered_at: stage.entered_at || new Date().toISOString(),
          };
        }
        return stage;
      });

      return lifecycle;
    });
  }

  /**
   * 完成当前阶段
   */
  async completeStage(stage: string): Promise<void> {
    await this.update<RtmLifecycle>('lifecycle', (lifecycle) => {
      lifecycle.lifecycle.stages = lifecycle.lifecycle.stages.map((s) => {
        if (s.stage === stage) {
          return {
            ...s,
            status: 'completed' as const,
            completed_at: new Date().toISOString(),
          };
        }
        return s;
      });

      return lifecycle;
    });
  }

  /**
   * 读取指定阶段的 RTM
   */
  async getStageRtm<T extends AnyRtm>(stage: RtmStage): Promise<T | null> {
    return this.read<T>(stage);
  }

  /**
   * 更新指定阶段的 RTM
   */
  async updateStageRtm<T extends AnyRtm>(stage: RtmStage, data: T): Promise<void> {
    await this.write(stage, data, { incrementVersion: true });
  }

  /**
   * 检查 RTM 文件是否存在
   */
  async exists(stage: RtmStage): Promise<boolean> {
    const filePath = this.getRtmPath(stage);
    try {
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * 删除 RTM 文件（慎用）
   */
  async delete(stage: RtmStage): Promise<void> {
    const filePath = this.getRtmPath(stage);
    try {
      await fs.unlink(filePath);
    } catch (error: any) {
      if (error.code !== 'ENOENT') {
        throw error;
      }
    }
  }

  /**
   * 列出所有存在的 RTM 文件
   */
  async listExistingRtms(): Promise<RtmStage[]> {
    const stages: RtmStage[] = [
      'lifecycle',
      'brainstorming',
      'design',
      'decomposing',
      'implementing',
      'accepting',
    ];

    const existing: RtmStage[] = [];
    for (const stage of stages) {
      if (await this.exists(stage)) {
        existing.push(stage);
      }
    }

    return existing;
  }
}

/**
 * 创建 RTM 管理器实例
 */
export function createRtmManager(requirementDir: string): RtmManager {
  return new RtmManager(requirementDir);
}
