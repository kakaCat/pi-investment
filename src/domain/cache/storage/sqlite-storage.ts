import Database from 'better-sqlite3';
import type { IStorage } from './storage-interface.js';
import { mkdirSync, existsSync } from 'fs';
import { dirname } from 'path';

export class SQLiteStorage implements IStorage {
  private db: Database.Database;
  private namespace: string;

  constructor(dbPath: string, namespace: string) {
    const dir = dirname(dbPath);
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }

    // Open database with write permissions
    this.db = new Database(dbPath, { readonly: false, fileMustExist: false });
    this.namespace = namespace;
    this.initializeSchema();
  }

  private initializeSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS cache_entries (
        key TEXT PRIMARY KEY,
        namespace TEXT NOT NULL,
        value TEXT NOT NULL,
        expires_at INTEGER NOT NULL,
        created_at INTEGER NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_namespace_expires
      ON cache_entries(namespace, expires_at);
    `);
  }

  async get<T>(key: string): Promise<T | null> {
    const row = this.db.prepare(`
      SELECT value, expires_at
      FROM cache_entries
      WHERE key = ? AND namespace = ?
    `).get(key, this.namespace) as { value: string; expires_at: number } | undefined;

    if (!row) return null;

    if (Date.now() > row.expires_at) {
      this.db.prepare('DELETE FROM cache_entries WHERE key = ? AND namespace = ?')
        .run(key, this.namespace);
      return null;
    }

    return JSON.parse(row.value) as T;
  }

  async set<T>(key: string, value: T, expiresAt: number): Promise<void> {
    const valueStr = JSON.stringify(value);
    const createdAt = Date.now();

    this.db.prepare(`
      INSERT OR REPLACE INTO cache_entries (key, namespace, value, expires_at, created_at)
      VALUES (?, ?, ?, ?, ?)
    `).run(key, this.namespace, valueStr, expiresAt, createdAt);
  }

  async delete(key: string): Promise<void> {
    this.db.prepare('DELETE FROM cache_entries WHERE key = ? AND namespace = ?')
      .run(key, this.namespace);
  }

  async clear(): Promise<void> {
    this.db.prepare('DELETE FROM cache_entries WHERE namespace = ?')
      .run(this.namespace);
  }

  async mget<T>(keys: string[]): Promise<Map<string, T>> {
    const results = new Map<string, T>();
    for (const key of keys) {
      const value = await this.get<T>(key);
      if (value !== null) {
        results.set(key, value);
      }
    }
    return results;
  }

  async mset<T>(entries: Map<string, { value: T; expiresAt: number }>): Promise<void> {
    const insert = this.db.prepare(`
      INSERT OR REPLACE INTO cache_entries (key, namespace, value, expires_at, created_at)
      VALUES (?, ?, ?, ?, ?)
    `);

    const transaction = this.db.transaction((entries: Map<string, { value: T; expiresAt: number }>) => {
      const createdAt = Date.now();
      for (const [key, { value, expiresAt }] of entries.entries()) {
        const valueStr = JSON.stringify(value);
        insert.run(key, this.namespace, valueStr, expiresAt, createdAt);
      }
    });

    transaction(entries);
  }

  async keys(pattern?: string): Promise<string[]> {
    const rows = this.db.prepare(`
      SELECT key FROM cache_entries WHERE namespace = ?
    `).all(this.namespace) as Array<{ key: string }>;

    const allKeys = rows.map(row => row.key);

    if (!pattern) return allKeys;

    const regex = new RegExp(pattern.replace(/\*/g, '.*'));
    return allKeys.filter(key => regex.test(key));
  }

  async size(): Promise<number> {
    const row = this.db.prepare(`
      SELECT COUNT(*) as count FROM cache_entries WHERE namespace = ?
    `).get(this.namespace) as { count: number };

    return row.count;
  }

  async cleanup(): Promise<number> {
    const now = Date.now();
    const result = this.db.prepare(`
      DELETE FROM cache_entries WHERE namespace = ? AND expires_at < ?
    `).run(this.namespace, now);

    return result.changes;
  }

  destroy(): void {
    this.db.close();
  }
}
