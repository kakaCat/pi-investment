import { mkdirSync, writeFileSync } from "fs";
import { join } from "path";
import { getSessionDataDir } from "./session-utils.js";

export type LargeToolOutputOptions = {
  label: string;
  filePrefix: string;
  extension?: string;
  maxInlineChars?: number;
  previewChars?: number;
  metadata?: Record<string, unknown>;
};

export type LargeToolOutputResult = {
  text: string;
  filePath?: string;
  originalLength: number;
  stored: boolean;
};

const DEFAULT_MAX_INLINE_CHARS = 80_000;
const DEFAULT_PREVIEW_CHARS = 1_000;

export function formatMaybeLargeToolOutput(
  content: string,
  options: LargeToolOutputOptions,
): LargeToolOutputResult {
  const maxInlineChars = options.maxInlineChars ?? DEFAULT_MAX_INLINE_CHARS;
  const previewChars = options.previewChars ?? DEFAULT_PREVIEW_CHARS;
  if (content.length <= maxInlineChars) {
    return {
      text: content,
      originalLength: content.length,
      stored: false,
    };
  }

  const outputDir = join(getSessionDataDir(), "tool-results");
  mkdirSync(outputDir, { recursive: true });
  const extension = options.extension ?? "txt";
  const filePath = join(outputDir, `${sanitizeFilePart(options.filePrefix)}-${Date.now()}.${extension}`);
  writeFileSync(filePath, content, "utf-8");

  const metadataLines = Object.entries(options.metadata ?? {})
    .map(([key, value]) => `- ${key}: ${String(value)}`);
  const preview = content.slice(0, previewChars);
  const text = [
    `${options.label} 结果过大，完整结果已保存到: ${filePath}`,
    "",
    `- 原始长度: ${content.length.toLocaleString("en-US")} 字符`,
    ...metadataLines,
    "",
    `内容预览 (前${preview.length.toLocaleString("en-US")}字符):`,
    preview,
    "",
    "[完整内容见文件。使用 read 工具查看完整内容]",
  ].join("\n");

  return {
    text,
    filePath,
    originalLength: content.length,
    stored: true,
  };
}

export function formatMaybeLargeJsonToolOutput(
  value: unknown,
  options: Omit<LargeToolOutputOptions, "extension">,
): LargeToolOutputResult {
  return formatMaybeLargeToolOutput(JSON.stringify(value, null, 2), {
    ...options,
    extension: "json",
  });
}

function sanitizeFilePart(value: string): string {
  const cleaned = value
    .trim()
    .replace(/[^a-zA-Z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return cleaned || "tool-output";
}
