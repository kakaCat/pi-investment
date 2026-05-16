/**
 * 存储层接口定义
 */

export interface IStorage {
  // 基础操作
  get<T>(key: string): Promise<T | null>;
  set<T>(key: string, value: T, expiresAt: number): Promise<void>;
  delete(key: string): Promise<void>;
  clear(): Promise<void>;

  // 批量操作
  mget<T>(keys: string[]): Promise<Map<string, T>>;
  mset<T>(entries: Map<string, { value: T; expiresAt: number }>): Promise<void>;

  // 查询操作
  keys(pattern?: string): Promise<string[]>;
  size(): Promise<number>;

  // 清理操作
  cleanup(): Promise<number>;
}
