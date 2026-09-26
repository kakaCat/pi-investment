/**
 * 写集类型定义与冲突检测
 * 
 * 用于实施链并行调度：声明子卡要改动的文件路径集合，
 * 按写集冲突分批（批内并发、批间串行）
 */

/**
 * 写集：一组待改动的文件路径
 */
export type WriteSet = string[];

/**
 * 检测两个写集是否冲突
 * 
 * 冲突定义：
 * - 路径完全相同
 * - 一方是另一方的目录前缀（如 "src/" 与 "src/app.ts"）
 * - 共享目录前缀（如 "src/a.ts" 与 "src/b.ts" 共享 "src/"）
 * 
 * @param ws1 写集1
 * @param ws2 写集2
 * @returns true=冲突（不可并行），false=不冲突（可并行）
 */
export function detectConflict(ws1: WriteSet, ws2: WriteSet): boolean {
  if (ws1.length === 0 || ws2.length === 0) {
    return false; // 空集不冲突
  }

  // 规范化路径：去除前后空白、统一分隔符
  const normalize = (path: string): string => {
    return path.trim().replace(/\\/g, '/');
  };

  const paths1 = ws1.map(normalize);
  const paths2 = ws2.map(normalize);

  // 检查每对路径
  for (const p1 of paths1) {
    for (const p2 of paths2) {
      // 1. 完全相同
      if (p1 === p2) {
        return true;
      }

      // 2. 一方是另一方的目录前缀
      // "src/" 是 "src/app.ts" 的前缀
      if (isDirectoryPrefix(p1, p2) || isDirectoryPrefix(p2, p1)) {
        return true;
      }

      // 3. 共享目录前缀（保守策略：同目录视为冲突）
      if (shareDirectoryPrefix(p1, p2)) {
        return true;
      }
    }
  }

  return false;
}

/**
 * 判断 dirPath 是否是 filePath 的目录前缀
 * 如 "src/" 是 "src/app.ts" 的前缀
 */
function isDirectoryPrefix(dirPath: string, filePath: string): boolean {
  // 确保目录路径以 / 结尾
  const dir = dirPath.endsWith('/') ? dirPath : dirPath + '/';
  return filePath.startsWith(dir);
}

/**
 * 判断两个路径是否共享目录前缀（保守策略）
 * 如 "src/a.ts" 与 "src/b.ts" 共享 "src/"
 */
function shareDirectoryPrefix(path1: string, path2: string): boolean {
  const dir1 = getParentDir(path1);
  const dir2 = getParentDir(path2);

  // 至少一个在根目录，不视为共享
  if (dir1 === '' || dir2 === '') {
    return false;
  }

  return dir1 === dir2;
}

/**
 * 获取路径的父目录
 * "src/app.ts" -> "src"
 * "app.ts" -> ""
 */
function getParentDir(path: string): string {
  const lastSlash = path.lastIndexOf('/');
  if (lastSlash === -1) {
    return ''; // 根目录
  }
  return path.substring(0, lastSlash);
}

/**
 * 验证写集有效性
 * - 限制单链子卡数 ≤ 50（防止调度器过载）
 * - 路径不能为空
 */
export function validateWriteSet(ws: WriteSet): { valid: boolean; error?: string } {
  if (ws.length > 50) {
    return { valid: false, error: '写集路径数超过上限50（单链子卡数过多）' };
  }

  for (const path of ws) {
    if (!path || path.trim() === '') {
      return { valid: false, error: '写集包含空路径' };
    }
  }

  return { valid: true };
}
