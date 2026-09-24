# t-e5d2e6 下沉产物发现核心并薄壳化 ArtifactSync·测试

> 子卡（父卡 t-9a6bdb · 阶段 test） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
下沉产物发现核心并薄壳化 ArtifactSync·测试

## 解决什么问题
子卡阶段：测试

## 得到什么结果（验收标准）
目标命令输出全绿（贴命令与结果摘要）；并把测试记录在本轮执行内写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-e5d2e6-test.md，在 filesChanged 中列出该文件

## 实施方案
新增 packages/web/dsh-pmboard/src/application/internal/artifact-discovery.ts（discoverArtifactsFrom(docs,req) 纯函数，走 DocRepository 端口）；改 packages/web/dsh-pmboard/src/adapters/ArtifactSync.ts 为薄壳调它 + 落库（行为零变更）；回归 packages/web/dsh-pmboard/tests/sync-artifacts.test.ts。

[子卡阶段·测试] 只做本阶段；验收：目标命令输出全绿（贴命令与结果摘要）

## 执行与完工记录
- workflow run：2026-09-24 23:41:01（stopReason=completed，产出非空=True）
- 改动文件：
  - docs/requirements/REQ-260924213231-b1c4/evidence/t-e5d2e6-test.md
- 完成项：
  - 运行目标命令 npx vitest run tests/sync-artifacts.test.ts：1 file / 11 tests 全绿，exit 0
  - 层边界守护 npx vitest run tests/layer-boundary.test.ts：8 passed / 1 failed，唯一失败为 diag-log.ts 存量基线（HEAD 上即存在），新增 application/internal/artifact-discovery.ts 不在越界清单、零 node:/adapters import
  - 直接消费方回归 npx vitest run tests/sync-artifacts.test.ts tests/fault-injection.test.ts tests/artifact-openable.test.ts：3 files / 25 tests 全绿，exit 0
  - 核验「既有断言逐字不变」：git diff --numstat 对 tests/sync-artifacts.test.ts = 32 0（纯新增 2 例、0 删除/0 修改）；ArtifactSync.ts = 37 88（净减 51 行，薄壳化）
  - 类型基线旁证：npx tsc --noEmit 错误 23 = 基线 23，两个改动文件命中 0 条
  - 把测试记录写入 docs/requirements/REQ-260924213231-b1c4/evidence/t-e5d2e6-test.md（130 行，含命令逐字输出与判定）
  - 本卡未修改任何实现/适配器/测试源码，仅新增本记录文件
- 执行段：1 次（末次 2026-09-24 23:38:32，outcome=succeeded）
