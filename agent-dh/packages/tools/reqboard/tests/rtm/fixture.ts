/**
 * 测试夹具：在系统临时目录搭一个"假需求"（requirement.md + design/ + decomposition.md
 * + 可变台账），让 RTM 生成器可以脱离 DSH 运行实例被测。
 *
 * @module tests/rtm/fixture
 */
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import type { LedgerReader, LedgerRequirementLike } from '../../src/rtm/context.js'
import type { RTMTaskLike } from '../../src/rtm/types.js'

export interface Fixture {
  root: string
  reqId: string
  reqDir: string
  ledger: LedgerReader
  writeDoc: (rel: string, content: string) => void
  setTasks: (tasks: RTMTaskLike[]) => void
  patchRequirement: (patch: Partial<LedgerRequirementLike>) => void
  task: (id: string) => RTMTaskLike | undefined
}

/** 建一个临时需求夹具。 */
export function makeFixture(reqId = 'REQ-test-0001'): Fixture {
  const root = mkdtempSync(join(tmpdir(), 'rtm-fixture-'))
  const reqDir = join(root, 'docs', 'requirements', reqId)
  mkdirSync(reqDir, { recursive: true })

  let requirement: LedgerRequirementLike = {
    id: reqId,
    title: 'RTM 测试需求',
    category: 'feature',
    status: 'draft',
    createdAt: Date.parse('2026-01-01T00:00:00Z'),
    updatedAt: Date.parse('2026-01-01T00:00:00Z'),
    // 绑定窗口（台账 sourceSessionId）——rtm-lifecycle.yml 要把它投影进 source_session。
    sourceSessionId: 'session-fixture-1',
    artifacts: [],
  }
  let tasks: RTMTaskLike[] = []

  const writeDoc = (rel: string, content: string): void => {
    const p = join(reqDir, rel)
    mkdirSync(dirname(p), { recursive: true })
    writeFileSync(p, content, 'utf-8')
  }

  const ledger: LedgerReader = {
    requirement: () => requirement,
    tasksOf: () => tasks,
  }

  return {
    root,
    reqId,
    reqDir,
    ledger,
    writeDoc,
    setTasks: next => {
      tasks = next
    },
    patchRequirement: patch => {
      requirement = { ...requirement, ...patch }
    },
    task: id => tasks.find(t => t.id === id),
  }
}

/** 三个 FR 的需求文档。 */
export const REQUIREMENT_MD = `---
requirement_id: REQ-test-0001
---

# REQ-test-0001: RTM 测试需求

## 功能点

### FR-1: 文件结构
实现 RTM 文件结构

### FR-2: 生成逻辑
实现 RTM 生成逻辑

### FR-3: 数据同步
实现数据同步机制
`;

/** 只覆盖 FR-1 / FR-2 的设计文档。 */
export const DESIGN_MD = `# 架构设计

## 1.1 文件结构 serves: FR-1
描述文件结构。

## 1.2 生成逻辑 serves: FR-2
描述生成逻辑。
`;

/** 两个测试用例，覆盖 t-0001 / t-0002。 */
export const TEST_CASES_MD = `# 测试用例

## TC-1 文件结构测试
covers: t-0001
validates: FR-1

## TC-2 生成逻辑测试
covers: t-0002
validates: FR-2
`;

/** 五个任务：t-0001/t-0004 服务 FR-1，t-0002/t-0005 服务 FR-2，t-0003 服务 FR-3。 */
export function fiveTasks(): RTMTaskLike[] {
  const mk = (id: string, serves: string[], phase: string, side = 'backend'): RTMTaskLike => ({
    id,
    title: `任务 ${id}`,
    status: 'todo',
    phase,
    side,
    depends_on: [],
    serves,
  })
  return [
    mk('t-0001', ['FR-1'], 'implement'),
    mk('t-0002', ['FR-2'], 'doc'),
    mk('t-0003', ['FR-3'], 'test'),
    mk('t-0004', ['FR-1'], 'ui', 'frontend'),
    mk('t-0005', ['FR-2'], 'implement'),
  ]
}
