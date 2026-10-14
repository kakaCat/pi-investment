# t-6fd33d 存量清理迁移与一致性校验（含备份与回滚）·研发

> 需求：REQ-261006190953-fc43 业绩归因/风险指标窗口未按交易日取数：剔除周末与节假日的净值点

## 在做什么
存量清理迁移与一致性校验（含备份与回滚）·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-06T12:27:46.837Z，窗口 session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8）

研发段：清理迁移可 dry-run、可幂等、可回滚；谓词按 D-6 改成白名单语义后，生产 dry-run 才真正命中 35 行

### 完成项

- 新建迁移脚本：备份表 + 备份 + 删除 + 逐账户全序列重放 + 账户级重算，dry-run/apply/rollback 三态
- dry-run 走与 apply 同一条路径后 ROLLBACK，保证说的与做的不会分叉
- 删除谓词按裁定 D-6 改为白名单语义（覆盖范围内 + 不在清单里），防误删由覆盖范围承担
- 新增防呆：非 _test 库上 apply/rollback 必须显式 --allow-production，否则拒绝
- 新建 tools/verify_equity_snapshot_consistency.py：逐账户独立复算比对，退出码 0/2/3
- 新建测试 8 例，逐条对应验收 ①~⑧，夹具自造覆盖窗口并在窗口内造缺行
- 生产 dry-run 实测：待删 35 行、重算 65 行、库内零改动（187 行未变、无备份表）

### 改动文件

- `infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py`
- `tools/verify_equity_snapshot_consistency.py`
- `tests/test_migration_purge_nontrading_snapshots.py`

### 下一步

联调段：核对测试库自清、邻域回归、以及生产只读核对（未做任何写操作）。

---
