# REQ-b63a7d 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t1 | t-cf63f0 | 新增产物路径归一层（domain 纯函数）+ 单测 | implement | backend | - | npx vitest run tests/domain/artifact-path.test.ts 全绿；用例覆盖 4 形态（agent-dh/ 前缀、绝对路径、quantsys-v2/ 跨仓、{a,b} 伪路径）与合规路径原样不变；npx vitest run tests/layer-boundary.test.ts 仍绿。 |
| t2 | t-0619c1 | 登记侧接入归一（ReportTask 等登记点） | implement | backend | t-cf63f0 | npx vitest run tests/application/report-task-path.test.ts 全绿；用例断言 `agent-dh/docs/x` → 产物 path=`docs/x`、绝对路径 → 相对、`{a,b}` → 不进 artifacts；既有 report-task 用例语义不变。 |
| t3 | t-381464 | /reqboard/file 接口：allowlist 放宽到工作区根 + 越界改 404 | implement | backend | t-cf63f0 | curl 断言三条：?path=agent-dh/docs/architecture/documentation-standard.md → 200；?path=docs/architecture/documentation-standard.md → 200；?path=quantsys-v2/main.py → 404 且 code=outside_workspace。?path=../../etc/passwd 与 ?path=/etc/passwd 仍 403。新增 tests/http/file-route.test.ts 覆盖上述分支。 |
| t4 | t-11b086 | openable 由 host 单点判定并下发；前端只对 openable 预检 | implement | frontend | t-381464 | 单测断言：非 openable 产物的渲染不含 data-doc-path（因而不发预检）；openable 产物行为不变。线上：详情页源码类产物不再显示「缺失」，控制台无 403。 |
| t5 | t-3852f0 | 存量台账清理（归一 + 剔除伪路径 + 备份/报告/幂等） | implement | backend | t-0619c1 | 脚本干跑（--dry-run）输出 diff 清单；实跑后扫描"非工作区相对 + 非伪路径"计数为 0（扫描脚本可复跑）；备份文件存在；报告落 docs/requirements/REQ-b63a7d/cleanup-report.md；重复执行幂等（第二次 0 变更）。 |
| t6 | t-827624 | 回归与故障注入测试 | test | backend | t-0619c1, t-381464, t-11b086 | npx vitest run 全绿（含新增用例）；故障注入用例逐条命名可追溯到形态 A/B/C/D；穿越防护用例仍拒绝。 |
| t7 | t-5ef156 | 构建 client + 重启 + 线上核验 | merge | fullstack | t-827624 | pnpm --filter <dsh-pmboard 包名> build:client 退出码 0 且 verify-client-build.mjs 通过（WRAP_SENTINEL 未命中）；重启后 curl A1/A2/A3 三条符合预期；详情页控制台无 403、源码类产物无「缺失」标；重启前后台账无回退（schemaVersion 仍 6）。 |
