/**
 * 队列路径约定契约测试（REQ-260927202051-f6df · Lead 裁决「单一事实源」）。
 *
 * 为什么需要这条测试：路径格式曾经有**两份独立实现**——
 * `QueueRepository.relativePathOf()` 一份、`application/use-cases/Decompose.ts` 就地拼字符串一份。
 * 两份拼法的分歧不报错、不崩，只表现为"队列写在这儿、读在那儿"（看板静默空白），
 * 是最难查的一类。本文件把"只有一份"变成**可失败的断言**：
 *
 * 1. 字面量口径：`queueRelativePath('REQ-x')` 恰为 `docs/requirements/REQ-x/queue.json`；
 * 2. **恒等**：任何实现（`JsonQueueRepository` / `InMemoryQueueRepository`）的
 *    `relativePathOf()` 必须与 domain 那个函数**逐字符相等**——将来谁再写一份就红；
 * 3. `pathOf()` 必须以该相对路径结尾（绝对路径与相对路径不会各说各话）；
 * 4. domain 那份必须**零 import**（`tests/layer-boundary.test.ts` 的 domain 规则：
 *    不许碰 node:/框架包/上层模块），否则 application 根本 import 不了它，两份拼法会复活。
 */

import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  QUEUE_FILENAME,
  REQUIREMENTS_DIR,
  queueRelativePath,
} from '../../src/domain/queue/queuePath.js'
import { QUEUE_FILENAME as REPO_QUEUE_FILENAME, JsonQueueRepository, queueRelativePath as repoQueueRelativePath } from '../../src/repositories/QueueRepository.js'
import { InMemoryQueueRepository } from '../application/harness.js'

const REQ = 'REQ-260927202051-f6df'

describe('queueRelativePath · 单一事实源', () => {
  it('字面量口径：docs/requirements/<REQ>/queue.json', () => {
    expect(REQUIREMENTS_DIR).toBe('docs/requirements')
    expect(QUEUE_FILENAME).toBe('queue.json')
    expect(queueRelativePath(REQ)).toBe(`docs/requirements/${REQ}/queue.json`)
  })

  it('repositories 层只是再导出，不是第二份实现（同一个函数引用 + 同一常量）', () => {
    expect(repoQueueRelativePath).toBe(queueRelativePath)
    expect(REPO_QUEUE_FILENAME).toBe(QUEUE_FILENAME)
  })

  it('JsonQueueRepository.relativePathOf 与 domain 函数**恒等**', () => {
    const repo = new JsonQueueRepository({ workspaceRoot: '/tmp/whatever' })
    expect(repo.relativePathOf(REQ)).toBe(queueRelativePath(REQ))
    expect(repo.relativePathOf('REQ-abc')).toBe(queueRelativePath('REQ-abc'))
  })

  it('InMemoryQueueRepository（用例层夹具）与 domain 函数**恒等**', () => {
    const repo = new InMemoryQueueRepository()
    expect(repo.relativePathOf(REQ)).toBe(queueRelativePath(REQ))
  })

  it('pathOf 以该相对路径结尾（绝对/相对不会各说各话）', () => {
    const json = new JsonQueueRepository({ workspaceRoot: '/tmp/ws' })
    const mem = new InMemoryQueueRepository('/tmp/ws')

    for (const repo of [json, mem]) {
      const abs = repo.pathOf(REQ)
      expect(abs.endsWith(queueRelativePath(REQ))).toBe(true)
      expect(abs.endsWith(`/${QUEUE_FILENAME}`)).toBe(true)
    }
    expect(json.pathOf(REQ)).toBe(`/tmp/ws/${queueRelativePath(REQ)}`)
  })

  it('注入 requirementDirOf 时 relativePathOf 仍是规范路径（不随落点漂移）', () => {
    const repo = new JsonQueueRepository({ workspaceRoot: '/tmp/ws', requirementDirOf: () => '/elsewhere/queue-dir' })
    expect(repo.relativePathOf(REQ)).toBe(queueRelativePath(REQ))
    expect(repo.pathOf(REQ)).toBe('/elsewhere/queue-dir/queue.json')
  })

  it('domain 实现零 import（否则 application 无法 import 它，两份拼法会复活）', () => {
    const source = readFileSync(new URL('../../src/domain/queue/queuePath.ts', import.meta.url), 'utf8')
    const code = source
      .split('\n')
      .filter((line) => {
        const t = line.trim()
        return !t.startsWith('*') && !t.startsWith('//') && !t.startsWith('/*')
      })
      .join('\n')

    expect(code).not.toMatch(/^\s*import\s/m)
    expect(code).not.toContain("from 'node:")
    expect(code).not.toContain('require(')
  })
})
