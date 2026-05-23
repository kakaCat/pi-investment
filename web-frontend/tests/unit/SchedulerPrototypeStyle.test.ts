import { describe, expect, it } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'

describe('Scheduler prototype style parity', () => {
  it('uses the v2 prototype card grid and history table structure', () => {
    const schedulerPath = path.resolve(process.cwd(), 'src/views/Scheduler/index.vue')
    const content = fs.readFileSync(schedulerPath, 'utf-8')

    expect(content).toContain('class="bg-white rounded-xl shadow-sm border border-slate-200 p-5 mb-4"')
    expect(content).toContain('class="grid grid-cols-2 gap-4 mb-4"')
    expect(content).toContain('class="bg-white rounded-xl shadow-sm border border-slate-200 p-5"')
    expect(content).toContain('class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden"')
    expect(content).toContain('<table class="w-full">')
    expect(content).toContain('<th>任务</th><th>状态</th><th>开始时间</th><th>完成时间</th><th>耗时</th><th>结果</th><th>错误</th>')
    expect(content).not.toContain('<el-card')
    expect(content).not.toContain('<el-table')
    expect(content).not.toContain('label="操作"')
  })
})
