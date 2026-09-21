/**
 * lossless 工具：保证输出为 DSH 无损 JSON（无 undefined/NaN/Infinity）
 *
 * DSH 校验工具输出时要求 JSON 往返一致（lossless round-trip）：
 * JSON.stringify 会丢弃 undefined 键、把 NaN/Infinity 序列化为 null，
 * 导致往返后对象不等而报 "value is not lossless JSON"。
 * 所有从后端/服务返回、未经显式构造的字段在返回前都应过一遍 sanitizeLossless。
 */

/**
 * 递归把 undefined/NaN/Infinity/-0 归一化，undefined 键直接删除，稀疏数组压实。
 * DSH 的 snapshotJsonValue 拒绝 negative-zero 与稀疏数组（lossless JSON 边界），
 * 2026-08-30 修复：此前 -0 会原样通过、Array.map 保留空洞，导致
 * risk_controller.portfolio_risk 等含脏值的输出被 snapshot 判定为不可序列化。
 */
export function sanitizeLossless<T>(value: T): T {
  if (value === undefined) return null as unknown as T;
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return null as unknown as T;
    if (Object.is(value, -0)) return 0 as unknown as T;
    return value;
  }
  if (Array.isArray(value)) {
    const out: unknown[] = [];
    for (let i = 0; i < value.length; i++) {
      if (i in value) out.push(sanitizeLossless((value as unknown[])[i]));
    }
    return out as unknown as T;
  }
  if (value !== null && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (v !== undefined) out[k] = sanitizeLossless(v);
    }
    return out as unknown as T;
  }
  return value;
}

/** 驼峰 → 蛇形（竞争分析后端返回 camelCase 字段时使用） */
export function toSnake(s: string): string {
  return s.replace(/[A-Z]/g, (c) => '_' + c.toLowerCase());
}
