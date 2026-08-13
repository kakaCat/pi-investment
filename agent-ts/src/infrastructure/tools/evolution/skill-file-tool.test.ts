/**
 * Skill File Tool Tests
 */

import { beforeEach, describe, expect, jest, test } from "@jest/globals";

// Mock modules before importing the tool
const mockExistsSync = jest.fn();
const mockReadFileSync = jest.fn();
const mockWriteFileSync = jest.fn();
const mockExecSync = jest.fn();

jest.unstable_mockModule("fs", () => ({
  existsSync: mockExistsSync,
  readFileSync: mockReadFileSync,
  writeFileSync: mockWriteFileSync,
}));

jest.unstable_mockModule("child_process", () => ({
  execSync: mockExecSync,
}));

const { skillFileTool } = await import("./skill-file-tool.js");

describe("skill_file tool", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Mock existsSync to handle getProjectRoot() and file checks
    mockExistsSync.mockImplementation((p: any) => {
      const pathStr = String(p);
      // Always allow getProjectRoot to succeed by returning true for agent-ts checks
      if (pathStr.endsWith("agent-ts") || pathStr.includes("/agent-ts")) {
        return true;
      }
      // For file reads, return false by default (tests will override as needed)
      return false;
    });
  });

  describe("read action", () => {
    test("should read file content successfully", async () => {
      const mockContent = "# Test Skill\nSome content here.";

      // Override for this specific test
      mockExistsSync.mockImplementation((p: any) => {
        const pathStr = String(p);
        if (pathStr.endsWith("agent-ts") || pathStr.includes("/agent-ts")) {
          return true;
        }
        if (pathStr.includes("test-skill.md")) {
          return true;
        }
        return false;
      });
      mockReadFileSync.mockReturnValue(mockContent);

      const result: any = await skillFileTool.execute("test-call-1", {
        action: "read",
        path: "test-skill.md",
      });

      expect(result.content).toBeDefined();
      expect(result.content[0].type).toBe("text");
      expect(result.content[0].text).toContain(mockContent);
      expect(result.details.success).toBe(true);
      expect(mockReadFileSync).toHaveBeenCalled();
    });

    test("should return error if file does not exist", async () => {
      // Clear previous mock return values
      mockReadFileSync.mockReset();

      // File doesn't exist - override existsSync to be more specific
      mockExistsSync.mockImplementation((p: any) => {
        const pathStr = String(p);
        // Allow getProjectRoot to succeed
        if (pathStr.endsWith("/agent-ts") && !pathStr.includes("skills")) {
          return true;
        }
        // File in skills directory doesn't exist
        if (pathStr.includes("skills") && pathStr.includes("nonexistent.md")) {
          return false;
        }
        return true;
      });

      const result: any = await skillFileTool.execute("test-call-2", {
        action: "read",
        path: "nonexistent.md",
      });

      expect(result.content[0].text).toContain("File not found");
      expect(result.details.success).toBe(false);
    });

    test("should reject path with .. (directory traversal)", async () => {
      const result: any = await skillFileTool.execute("test-call-3", {
        action: "read",
        path: "../secrets/config.md",
      });

      expect(result.content[0].text).toContain("Invalid path");
      expect(result.content[0].text).toContain("cannot contain '..'");
      expect(result.details.success).toBe(false);
    });

    test("should reject absolute paths", async () => {
      const result: any = await skillFileTool.execute("test-call-4", {
        action: "read",
        path: "/etc/passwd",
      });

      expect(result.content[0].text).toContain("Invalid path");
      expect(result.content[0].text).toContain("must be relative");
      expect(result.details.success).toBe(false);
    });
  });

  describe("write action", () => {
    test("should create worktree, write file, and run check:tool-refs successfully", async () => {
      const mockContent = "# Updated Skill\nNew content.";
      const mockCheckOutput = "✓ All tool references are valid";

      mockExecSync.mockImplementation(((cmd: string) => {
        if (cmd.includes("git worktree add")) {
          return Buffer.from("Preparing worktree...");
        }
        if (cmd.includes("npm run check:tool-refs")) {
          return Buffer.from(mockCheckOutput);
        }
        return Buffer.from("");
      }) as any);
      mockWriteFileSync.mockImplementation(() => {});

      const result: any = await skillFileTool.execute("test-call-5", {
        action: "write",
        path: "test-skill.md",
        content: mockContent,
      });

      expect(result.content[0].text).toContain("written successfully");
      expect(result.content[0].text).toContain(mockCheckOutput);
      expect(result.details.success).toBe(true);
      expect(result.details.worktree).toContain(".claude/worktrees/skill-");
      expect(result.details.branch).toContain("feat/skill-");

      // Verify worktree creation
      expect(mockExecSync).toHaveBeenCalledWith(
        expect.stringContaining("git worktree add"),
        expect.any(Object)
      );

      // Verify file write
      expect(mockWriteFileSync).toHaveBeenCalled();

      // Verify check:tool-refs
      expect(mockExecSync).toHaveBeenCalledWith(
        "npm run check:tool-refs",
        expect.objectContaining({
          cwd: expect.stringContaining("agent-ts"),
        })
      );
    });

    test("should return error if check:tool-refs fails", async () => {
      const mockContent = "# Broken Skill\nInvalid tool reference.";
      const mockCheckError = "Error: tool 'invalid_tool' not found";

      mockExecSync.mockImplementation(((cmd: string) => {
        if (cmd.includes("git worktree add")) {
          return Buffer.from("Preparing worktree...");
        }
        if (cmd.includes("npm run check:tool-refs")) {
          const error: any = new Error("Check failed");
          error.stdout = mockCheckError;
          throw error;
        }
        return Buffer.from("");
      }) as any);
      mockWriteFileSync.mockImplementation(() => {});

      const result: any = await skillFileTool.execute("test-call-6", {
        action: "write",
        path: "broken-skill.md",
        content: mockContent,
      });

      expect(result.content[0].text).toContain("Tool reference validation failed");
      expect(result.content[0].text).toContain(mockCheckError);
      expect(result.content[0].text).toContain("Fix tool references");
      expect(result.details.success).toBe(false);
    });

    test("should return error if worktree creation fails", async () => {
      const mockContent = "# Test Skill";

      mockExecSync.mockImplementation(((cmd: string) => {
        if (cmd.includes("git worktree add")) {
          throw new Error("git worktree add failed: branch already exists");
        }
        return Buffer.from("");
      }) as any);

      const result: any = await skillFileTool.execute("test-call-7", {
        action: "write",
        path: "test-skill.md",
        content: mockContent,
      });

      expect(result.content[0].text).toContain("Failed to create worktree");
      expect(result.content[0].text).toContain("branch already exists");
      expect(result.details.success).toBe(false);
    });

    test("should reject path with .. (directory traversal)", async () => {
      const result: any = await skillFileTool.execute("test-call-8", {
        action: "write",
        path: "../secrets/malicious.md",
        content: "Malicious content",
      });

      expect(result.content[0].text).toContain("Invalid path");
      expect(result.content[0].text).toContain("cannot contain '..'");
      expect(result.details.success).toBe(false);
    });

    test("should require content parameter for write action", async () => {
      const result: any = await skillFileTool.execute("test-call-9", {
        action: "write",
        path: "test-skill.md",
        // Missing content parameter
      });

      expect(result.content[0].text).toContain("Content parameter is required");
      expect(result.details.success).toBe(false);
    });
  });

  describe("invalid action", () => {
    test("should return error for unknown action", async () => {
      const result: any = await skillFileTool.execute("test-call-10", {
        action: "delete",
        path: "test-skill.md",
      });

      expect(result.content[0].text).toContain("Unknown action");
      expect(result.details.success).toBe(false);
    });
  });
});
