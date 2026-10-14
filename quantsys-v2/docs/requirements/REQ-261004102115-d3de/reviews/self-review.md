# 自评审报告 · REQ-261004102115-d3de

**日期**：2026-10-04 ｜ **性质**：自评审（agent 自查）。人工验收请以看板验收单为准。
**范围**：新增 1 个模块 + 3 个文件修改 + 3 个测试文件（2 新增 / 1 修改桩点）+ 1 次日历表回填。

---

## 1. 评审查了什么

| # | 对象 | 结论 |
|---|---|---|
| 1 | 口径是否真的唯一（FR-1） | 只有 `trading_day_resolver.last_closed_trading_day` 一处算"应有交易日"；探针与 `freshness_guard` 都是转发，无第二份 `weekday()` 逻辑 |
| 2 | 降级是否**响亮**（FR-2/FR-3） | 三级源各自 try/except 记 warning；`degraded` 一路带到探针 JSON、告警正文与巡检 result；单测双向锁（降级有标注 / 非降级无标注） |
| 3 | 是否改动了不该改的（边界） | 未动 `quant.data_contracts`、未动 launchd plist、未新增依赖、未改 K 线写入逻辑；`_last_trading_day` 签名保持（8 个引用方 import 通过） |
| 4 | 回归锁是否**真能抓**（FR-4） | 反向验证：解析器改成永远回退 → 10 条用例红；恢复后哈希一致、13 条全绿 |
| 5 | 生效路径是否真跑过 | 探针实跑 exit 0（正例）与 exit 2（负例）；回填后解析器四组日期全走 `calendar_table` |

## 2. 评审中发现并纠正的**我自己的**问题（如实列出）

| # | 问题 | 怎么发现的 | 处置 |
|---|---|---|---|
| 1 | **日志断言不稳**：`test_provider_empty_falls_back_and_logs` 用 `capsys` 抓 structlog 输出，单跑该文件能过、与别的测试同批跑就抓不到 | 跑 `pytest -k "freshness or trading_day or health_probe"` 时该条变红，单跑又绿 | 改为**替换 `tr.logger` 记录事件**再断言；两种跑法结果一致 |
| 2 | **打桩点第四次搬家未跟**：`tests/test_freshness_guard.py` 打在 `pipeline._last_trading_day` 上——巡检改调 resolver 后桩"名字还在但不生效"（正是该文件自己记载过三次的坑） | 首次跑 `tests/test_freshness_guard.py`：2 条用例判成 `stale`（应为 fresh / fresh_but_job_failed） | 桩移到 `application.services.trading_day_resolver.last_closed_trading_day`，原三条断言一字未改，另加一条来源断言 |
| 3 | **设计里写的 `expected_source` 是两值枚举（calendar / weekday_fallback）**，而解析器内部是三值来源 | 写探针接入代码时发现契约与实现不一致 | 保持**对外契约**为设计所写两值（表与 provider 都算 calendar），解析器内部三值仅用于日志与排障 |
| 4 | 拆分计划里给的 `requirement_refs` 与台账统计不一致 | 验收前 `reqboard_status` 显示四条 FR 全 `unreceived`、`fr_coverage.total_frs=0`；而 `reqboard_task_refs` 回执 `changed=false`（说明卡上**已**是 `["FR-1"]` 等） | 已如实登记为遗留（见 §3），未强行改数据掩盖 |

## 3. 遗留与已知限制（不假装全覆盖）

1. **RTM 未生成 `rtm-accepting.yml`**（`rtm_health.healthy=false`、`retry_available=true`），
   因此 `fr_coverage` 统计为 `total_frs=0`，与卡上已设置的 `requirementRefs` 不一致；
   `reqboard_task_refs` 的 `rtm_synced` 亦为 false。**属台账/RTM 生成侧问题，不在本需求边界内**，留待重试。
2. **既有 4 条 `_last_trading_day` 边界用例**（`tests/test_daily_jobs_bootstrap.py`）现在会经 DB/provider 取数，
   从纯单测变成偏集成；它们之所以稳定，是因为那四个日期恰好与"周一至周五回退"给出同一答案。
   **本轮不改**（属既有用例，且改动会超出本卡范围），如需彻底隔离，另开卡给该文件注入假日历。
3. **表未覆盖 anchor 时探针每次走 provider**：本次未给刷新脚本加排班（调度层决定，越界即升级重档）；
   已在 `design/data-model.md` 显式登记该代价，并在 provider 失败时打印原因、降级标注。
4. **同一语义的第三个口径仍在**：`tools/check_data_contracts.py:compute_expected_trading_day`
   （它自带 `holiday_slack_weekdays` 冗余，本次无报错）。合并它牵动另一个工具的判定面与测试面，
   已按设计登记为后续收敛项，**不在本次范围**。
5. **休市日 `evening_pipeline` 仍会起 `kline_sync`**（10-02 实测成功 0 只、未覆盖 5271 只）——另案。

## 4. 结论

四条 FR 均有可复核证据且实测通过；改动面未溢出；两处自身问题（不稳断言、桩点漂移）已在交付前纠正。
遗留三项均为**已登记的边界外事项**，不阻塞本次验收。
