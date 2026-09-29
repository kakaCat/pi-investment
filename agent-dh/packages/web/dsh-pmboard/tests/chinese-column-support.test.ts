
import { describe, it, expect } from 'vitest'
import { normalizePlanTasks } from '../src/shared/protocol.js'

describe('中文列名支持 - BUG 修复验证', () => {
  it('应该支持中文"依赖"列名解析依赖关系', () => {
    const tasks = [
      {
        key: 't1',
        title: '第一层任务',
        phase: 'implement',
        side: 'backend',
        依赖: [],
        acceptance: '运行 npx vitest 测试通过',
        implementation: '实施方案内容'
      },
      {
        key: 't2',
        title: '第二层任务',
        phase: 'implement',
        side: 'backend',
        依赖: ['t1'],  // ← 依赖第一层
        acceptance: '运行 npx vitest 测试通过',
        implementation: '实施方案内容'
      },
      {
        key: 't3',
        title: '第三层任务',
        phase: 'implement',
        side: 'backend',
        依赖: ['t1', 't2'],  // ← 依赖第一、二层
        acceptance: 'grep 命令输出包含预期内容',
        implementation: '实施方案内容'
      }
    ]

    const normalized = normalizePlanTasks(tasks)

    // 验证依赖关系被正确解析
    expect(normalized[0].key).toBe('t1')
    expect(normalized[0].dependsOn).toEqual([])
    
    expect(normalized[1].key).toBe('t2')
    expect(normalized[1].dependsOn).toEqual(['t1'])
    
    expect(normalized[2].key).toBe('t3')
    // 2026-09-29（REQ-260929010300-dbf9 用户裁定 B「数据侧」）：dependsOn 落库前做**传递归约**，
    // 只保留直接前置。t3 依赖 t1,t2；而 t2 依赖 t1，故 t1 冗余被折叠（保序）⇒ ['t2']。
    expect(normalized[2].dependsOn).toEqual(['t2'])
  })

  it('应该优先使用 dependsOn，然后 depends_on，最后才是中文"依赖"', () => {
    const tasks = [
      {
        key: 't1',
        title: '使用 depends_on',
        depends_on: [],
        acceptance: '文件 test.ts 存在',
        implementation: '实施'
      },
      {
        key: 't2',
        title: '使用中文依赖',
        依赖: ['t1'],
        acceptance: '文件 test.md 包含内容',
        implementation: '实施'
      }
    ]

    const normalized = normalizePlanTasks(tasks)

    expect(normalized[0].dependsOn).toEqual([])
    expect(normalized[1].dependsOn).toEqual(['t1'])
  })
})
