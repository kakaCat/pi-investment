/**
 * Skill File Tool - 技能文件读写工具
 *
 * 供进化 Agent 读取和修改 skills/*.md 文件。
 * write 操作自动创建 worktree 隔离，修改后运行 check:tool-refs 验证。
 */

import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import * as fs from "fs";
import * as path from "path";
import { execSync } from "child_process";
import { fileURLToPath } from "url";

// ES module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 获取项目根目录（agent-ts 的父目录）
const getProjectRoot = (): string => {
  // 从当前文件路径向上查找，直到找到包含 agent-ts 的目录
  let current = __dirname;
  while (current !== "/" && !fs.existsSync(path.join(current, "agent-ts"))) {
    current = path.dirname(current);
  }
  if (!fs.existsSync(path.join(current, "agent-ts"))) {
    throw new Error("Cannot find project root (no agent-ts directory found)");
  }
  return current;
};

const SKILLS_DIR = "skills";

export const skillFileTool: ToolDefinition = {
  name: "skill_file",
  label: "技能文件操作",
  description:
    "Read or write skill files (skills/*.md). " +
    "Write operations automatically create a git worktree for isolation and run 'npm run check:tool-refs' to validate tool references.",
  promptSnippet: "需要查看或修改 skill 文件时",
  promptGuidelines: [
    "用于读取 skills/*.md 的内容",
    "修改 skill 文件前自动创建 worktree 隔离",
    "修改后自动验证工具引用（check:tool-refs）",
  ],
  parameters: Type.Object({
    action: Type.Union([Type.Literal("read"), Type.Literal("write")], {
      description: "Action to perform: 'read' (read file content) or 'write' (modify file with worktree isolation).",
    }),
    path: Type.String({
      description: "Relative path to skill file (e.g., 'pool-management.md'). Must be within skills/ directory.",
    }),
    content: Type.Optional(
      Type.String({
        description: "File content to write. Required for 'write' action.",
      })
    ),
  }),
  execute: async (_toolCallId: string, params: any) => {
    try {
      const { action, path: relativePath, content } = params;

      // 验证路径安全性（防止目录穿越）
      if (relativePath.includes("..") || path.isAbsolute(relativePath)) {
        return {
          content: [
            {
              type: "text" as const,
              text: "Invalid path: path must be relative and cannot contain '..'",
            },
          ],
          details: { success: false, error: "Invalid path" },
        };
      }

      const projectRoot = getProjectRoot();
      const skillsDir = path.join(projectRoot, SKILLS_DIR);
      const fullPath = path.join(skillsDir, relativePath);

      // 确保路径在 skills/ 目录内
      if (!fullPath.startsWith(skillsDir)) {
        return {
          content: [
            {
              type: "text" as const,
              text: "Invalid path: file must be within skills/ directory",
            },
          ],
          details: { success: false, error: "Path outside skills directory" },
        };
      }

      if (action === "read") {
        return await handleRead(fullPath);
      } else if (action === "write") {
        if (!content) {
          return {
            content: [
              {
                type: "text" as const,
                text: "Content parameter is required for write action",
              },
            ],
            details: { success: false, error: "Missing content parameter" },
          };
        }
        return await handleWrite(projectRoot, fullPath, relativePath, content);
      } else {
        return {
          content: [
            {
              type: "text" as const,
              text: `Unknown action: ${action}`,
            },
          ],
          details: { success: false, error: "Unknown action" },
        };
      }
    } catch (err: any) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Error: ${err.message || String(err)}`,
          },
        ],
        details: { success: false, error: err.message },
      };
    }
  },
};

async function handleRead(fullPath: string): Promise<any> {
  if (!fs.existsSync(fullPath)) {
    return {
      content: [
        {
          type: "text" as const,
          text: `File not found: ${fullPath}`,
        },
      ],
      details: { success: false, error: "File not found" },
    };
  }

  const content = fs.readFileSync(fullPath, "utf-8");
  return {
    content: [
      {
        type: "text" as const,
        text: `File: ${fullPath}\n\n${content}`,
      },
    ],
    details: { success: true, path: fullPath, content },
  };
}

async function handleWrite(
  projectRoot: string,
  fullPath: string,
  relativePath: string,
  content: string
): Promise<any> {
  // 生成 worktree 名称（基于文件名）
  const fileName = path.basename(relativePath, ".md");
  const timestamp = Date.now();
  const worktreeName = `skill-${fileName}-${timestamp}`;
  const worktreePath = path.join(projectRoot, ".claude/worktrees", worktreeName);
  const branchName = `feat/skill-${fileName}-${timestamp}`;

  try {
    // 1. 创建 worktree
    execSync(`git worktree add "${worktreePath}" -b "${branchName}"`, {
      cwd: projectRoot,
      encoding: "utf-8",
    });

    // 2. 写入文件
    const targetPath = path.join(worktreePath, SKILLS_DIR, relativePath);
    fs.writeFileSync(targetPath, content, "utf-8");

    // 3. 运行 check:tool-refs
    let checkResult: string;
    try {
      const result = execSync("npm run check:tool-refs", {
        cwd: path.join(worktreePath, "agent-ts"),
        encoding: "utf-8",
        stdio: ["pipe", "pipe", "pipe"],
      });
      checkResult = typeof result === "string" ? result : String(result);
    } catch (err: any) {
      // check:tool-refs 失败，返回错误信息
      const errorOutput = err.stdout || err.message;
      return {
        content: [
          {
            type: "text" as const,
            text: `Tool reference validation failed:\n\n${errorOutput}\n\nWorktree: ${worktreePath}\nBranch: ${branchName}\n\nFix tool references before merging this worktree.`,
          },
        ],
        details: {
          success: false,
          error: "Tool reference validation failed",
          worktree: worktreePath,
          branch: branchName,
          checkOutput: errorOutput,
        },
      };
    }

    return {
      content: [
        {
          type: "text" as const,
          text: `File written successfully in worktree.\n\nWorktree: ${worktreePath}\nBranch: ${branchName}\n\nTool reference check:\n${checkResult.trim()}\n\nRun tests and merge if everything looks good.`,
        },
      ],
      details: {
        success: true,
        path: fullPath,
        worktree: worktreePath,
        branch: branchName,
        checkOutput: checkResult.trim(),
      },
    };
  } catch (err: any) {
    // Worktree 创建失败或其他错误
    return {
      content: [
        {
          type: "text" as const,
          text: `Failed to create worktree or write file: ${err.message}`,
        },
      ],
      details: {
        success: false,
        error: `Failed to create worktree or write file: ${err.message}`,
        worktree: worktreePath,
        branch: branchName,
      },
    };
  }
}
