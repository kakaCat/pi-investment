/**
 * Python 路径智能解析器
 *
 * 解决 macOS 系统 `python3` → Python 3.8（不支持 `list[str]` 语法）的问题。
 * 按优先级查找项目可用的 Python 3.9+ 解释器。
 *
 * 优先级：
 *   1. PI_PYTHON_PATH 环境变量（手动指定，终极兜底）
 *   2. 项目 venv: .venv-py313/bin/python
 *   3. 项目 venv: .venv/bin/python3
 *   4. Conda/Miniconda: /opt/miniconda3/bin/python
 *   5. 系统 python3（版本 ≥ 3.9 才接受）
 */

import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

export interface ResolvedPython {
  /** Python 解释器的绝对路径 */
  path: string;
  /** 版本字符串，如 "3.12.8" */
  version: string;
  /** 来源标识 */
  source: "env" | "venv-py313" | "venv" | "conda" | "system";
}

/** 项目根目录（src/infrastructure/adapters/python/ → 上四级） */
function getProjectRoot(): string {
  // ES module: use import.meta.url
  // We resolve relative to this file's location
  const __filename = new URL(import.meta.url).pathname;
  // src/infrastructure/adapters/python/resolver.ts → go up 4 levels
  const pythonDir = __filename.substring(0, __filename.lastIndexOf("/"));
  const adaptersDir = pythonDir.substring(0, pythonDir.lastIndexOf("/"));
  const infraDir = adaptersDir.substring(0, adaptersDir.lastIndexOf("/"));
  const srcDir = infraDir.substring(0, infraDir.lastIndexOf("/"));
  return srcDir.substring(0, srcDir.lastIndexOf("/"));
}

/**
 * 获取 Python 解释器的版本号（如 "3.12.8"）
 * 同步执行，超时 5 秒
 */
function getPythonVersion(pythonPath: string): string | null {
  try {
    const output = execSync(`"${pythonPath}" --version`, {
      encoding: "utf-8",
      timeout: 5000,
    }).trim();
    // "Python 3.12.8" → "3.12.8"
    const match = output.match(/Python\s+(\d+\.\d+\.\d+)/);
    return match ? match[1] : null;
  } catch {
    return null;
  }
}

/**
 * 检查版本号是否 ≥ 3.9（即支持 `list[str]` 语法）
 */
function isVersionAtLeast39(version: string): boolean {
  const parts = version.split(".").map(Number);
  if (parts.length < 2) return false;
  // major >= 3 and minor >= 9
  return parts[0] > 3 || (parts[0] === 3 && parts[1] >= 9);
}

/**
 * 解析 Python 解释器路径
 *
 * @returns ResolvedPython 对象，包含路径、版本和来源
 * @throws Error 如果找不到 Python 3.9+
 */
export function resolvePythonPath(): ResolvedPython {
  const projectRoot = getProjectRoot();

  // 1. 环境变量（最高优先级）
  const envPython = process.env.PI_PYTHON_PATH;
  if (envPython) {
    const version = getPythonVersion(envPython);
    if (version && isVersionAtLeast39(version)) {
      return { path: envPython, version, source: "env" };
    }
    throw new Error(
      `PI_PYTHON_PATH=${envPython} 不是有效的 Python 3.9+ 解释器 ` +
      `(${version || "无法获取版本"})。请检查环境变量设置。`
    );
  }

  // 候选列表：[路径, 来源标识]
  const candidates: Array<[string, ResolvedPython["source"]]> = [
    [join(projectRoot, ".venv-py313", "bin", "python"), "venv-py313"],
    [join(projectRoot, ".venv", "bin", "python3"), "venv"],
    ["/opt/miniconda3/bin/python", "conda"],
  ];

  // 2. 检查候选路径
  for (const [candidatePath, source] of candidates) {
    if (!existsSync(candidatePath)) continue;
    const version = getPythonVersion(candidatePath);
    if (version && isVersionAtLeast39(version)) {
      return { path: candidatePath, version, source };
    }
  }

  // 3. 检查系统 python3（仅在 ≥ 3.9 时接受）
  const systemPython = "python3";
  const sysVersion = getPythonVersion(systemPython);
  if (sysVersion && isVersionAtLeast39(sysVersion)) {
    return { path: systemPython, version: sysVersion, source: "system" };
  }

  // 4. 所有方案都失败
  const tried = candidates
    .filter(([p]) => existsSync(p))
    .map(([p, s]) => `${p} (${s})${getPythonVersion(p) ? ` v${getPythonVersion(p)}` : ""}`)
    .join("\n    ");

  throw new Error(
    `找不到 Python 3.9+ 解释器。项目需要 Python ≥ 3.9（推荐 3.12+）来支持 \`list[str]\` 等现代语法。\n\n` +
    `尝试过的路径:\n    ${tried || "(无候选路径存在)"}\n` +
    `系统 python3: ${sysVersion || "不可用"}\n\n` +
    `解决方法:\n` +
    `  1. 设置环境变量: export PI_PYTHON_PATH=/path/to/python3.12\n` +
    `  2. 安装 Python 3.12+: brew install python@3.12\n` +
    `  3. 使用 Conda: conda create -n py312 python=3.12`
  );
}

/**
 * 获取 Python 路径（简化版，直接返回路径字符串）
 * 适合不需要版本信息的场景
 */
export function getPythonPath(): string {
  return resolvePythonPath().path;
}
