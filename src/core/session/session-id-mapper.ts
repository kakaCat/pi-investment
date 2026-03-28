import { randomBytes } from "crypto";
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { dirname } from "path";

/**
 * 生成友好的 session ID: session_时间_序列号
 * 格式: session_YYYYMMDD_NNN (3位递增序号)
 * 例如: session_20260315_001, session_20260315_002
 */
export function generateFriendlySessionId(existingIds: string[]): string {
  const now = new Date();
  const date = now.toISOString().slice(0, 10).replace(/-/g, ""); // YYYYMMDD

  // 找出当天已有的最大序号
  const todayPrefix = `session_${date}_`;
  const todayIds = existingIds.filter(id => id.startsWith(todayPrefix));

  let maxSeq = 0;
  for (const id of todayIds) {
    const parts = id.split('_');
    if (parts.length >= 3) {
      const seqStr = parts[2];
      const seq = parseInt(seqStr, 10);
      if (!isNaN(seq) && seq > maxSeq) {
        maxSeq = seq;
      }
    }
  }

  // 生成新序号（3位数字，补零）
  const newSeq = (maxSeq + 1).toString().padStart(3, '0');
  return `session_${date}_${newSeq}`;
}

/**
 * Session ID 映射管理
 * 维护 UUID <-> 友好ID 的双向映射
 */
export class SessionIdMapper {
  private mapFile: string;
  private uuidToFriendly: Map<string, string>;
  private friendlyToUuid: Map<string, string>;

  constructor(mapFile: string) {
    this.mapFile = mapFile;
    this.uuidToFriendly = new Map();
    this.friendlyToUuid = new Map();
    this.load();
  }

  private load(): void {
    try {
      if (existsSync(this.mapFile)) {
        const data = JSON.parse(readFileSync(this.mapFile, "utf-8"));
        this.uuidToFriendly = new Map(Object.entries(data.uuidToFriendly || {}));
        this.friendlyToUuid = new Map(Object.entries(data.friendlyToUuid || {}));
      }
    } catch {}
  }

  private save(): void {
    const dir = dirname(this.mapFile);
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }
    writeFileSync(
      this.mapFile,
      JSON.stringify(
        {
          uuidToFriendly: Object.fromEntries(this.uuidToFriendly),
          friendlyToUuid: Object.fromEntries(this.friendlyToUuid),
        },
        null,
        2
      )
    );
  }

  /**
   * 获取或创建友好ID
   */
  getFriendlyId(uuid: string): string {
    if (this.uuidToFriendly.has(uuid)) {
      return this.uuidToFriendly.get(uuid)!;
    }

    // 生成新的友好ID，传入已有的所有友好ID
    const existingIds = Array.from(this.friendlyToUuid.keys());
    const friendlyId = generateFriendlySessionId(existingIds);

    // 保存映射
    this.uuidToFriendly.set(uuid, friendlyId);
    this.friendlyToUuid.set(friendlyId, uuid);
    this.save();

    return friendlyId;
  }

  /**
   * 通过友好ID获取UUID
   */
  getUuid(friendlyId: string): string | undefined {
    return this.friendlyToUuid.get(friendlyId);
  }
}
