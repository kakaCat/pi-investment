/**
 * llm 模块依赖边界守护：
 * 1) 除 adapters/pi-ai.ts 外，模块内任何文件不得 import pi-ai / pi-coding-agent
 * 2) llm 模块不得 import agent loop（core/agent）
 */
import { describe, it, expect } from '@jest/globals';
import { readdirSync, readFileSync, statSync } from 'fs';
import { join, relative } from 'path';
import { fileURLToPath } from 'url';

const LLM_DIR = fileURLToPath(new URL('.', import.meta.url));

function listSourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...listSourceFiles(p));
    else if (name.endsWith('.ts') && !name.endsWith('.test.ts')) out.push(p);
  }
  return out;
}

describe('llm 模块依赖边界', () => {
  it('除 adapters/pi-ai.ts 外不得 import SDK', () => {
    const offenders: string[] = [];
    for (const f of listSourceFiles(LLM_DIR)) {
      if (f.endsWith(join('adapters', 'pi-ai.ts'))) continue;
      const src = readFileSync(f, 'utf8');
      if (src.includes('@mariozechner/pi-ai') || src.includes('@mariozechner/pi-coding-agent')) {
        offenders.push(relative(LLM_DIR, f));
      }
    }
    expect(offenders).toEqual([]);
  });

  it('llm 模块不得 import core/agent（无环）', () => {
    const offenders: string[] = [];
    for (const f of listSourceFiles(LLM_DIR)) {
      const src = readFileSync(f, 'utf8');
      if (/from\s+['"][^'"]*core\/agent/.test(src)) offenders.push(relative(LLM_DIR, f));
    }
    expect(offenders).toEqual([]);
  });
});
