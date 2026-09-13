# REQ-24e15d 进度：非 ORM SQL 收敛 t1/t2 完成、t3 进行中（2026-09-13，w-32314d00）

## 1. 基线与工具

新增可复跑扫描器 `tools/non_orm_sql_scan.py`（`--gate` 可接发版体检）。
**指标本身修了两轮**，否则数字不可信：

1. 第一版把注释里的反例写法也算进去 → 修完代码计数反而 +1；
2. 第二版按三引号粗暴跳过 → 把 `cursor.execute("""...""")` 的多行 SQL 字面量一起跳过，
   `cursor_execute` 从 154 漏计到 87（漏 43%）；
3. 最终改为 **AST 精确识别 docstring**（只认模块/类/函数体的首个字符串常量），SQL 字面量照常计入。

## 2. t1（P0 值位置注入）：完成

- `infrastructure/adapters/industry_data_adapter.py`：原 f-string 把 `factor_name` 与 `symbol_list` 直接拼进 SQL
  （列名 + 取值双重注入面）→ 列名过白名单 + `symbol = ANY(%s)` 绑定参数；
- `infrastructure/jobs/financial_data_update_job.py`：SET 子句列名加白名单守卫（未知列显式报错）；
- 新增 `tests/test_non_orm_sql_t1_parameterization.py`（10 passed）；活体取数验证通过。

## 3. t2（P0 裸连接）：完成

- 新增 `PooledConnection`（`infrastructure/persistence/database/engine.py`）：把池化连接包装成 psycopg2 风格
  `cursor()/commit()/rollback()/close()/closed`，调用点**零改动**即可从"裸连接长期持有"切到"借完即还"，
  `close()` 前对未提交事务显式 rollback（防 idle-in-transaction 残影）；
- 转换：`attribution_service` / `weekly_report_service` / `signal_test_log` / `signal_tracking_repository`；
- 期间发现两处**真 bug**：
  ① `attribution_service.analyze_rule_performance` 在真实数据上崩（`float += decimal.Decimal`）——已修；
  ② `utils/symbol_classifier.is_index_symbol` 走 ORM 仓储查 stocks，在 ThreadPoolExecutor 线程上开
     thread-local session 且不关闭 → 22:08 那条 `session_leak_detected`——改用池化游标，语义不变（已验）。

## 4. t3（分层下沉）：进行中

目标文件 `application/services/smart_scheduler.py`（起点 7 处裸 SQL → 现 1 处）：

- 前置核查发现**真 bug**：`AutomationRun` 模型把列映射成不存在的 `run_metadata`（真实库列名是 `metadata`），
  整个 `AutomationRunRepository` 在真实库上不可用 → 已修 + 新增契约测试
  `tests/test_automation_run_mapping_contract.py`（2 passed）；
- 新增 `find_running_run_id_by_job_id`（`metadata->>'job_id'` 查最新 running）；
- 已上收：`_update_run_status`（SELECT+UPDATE）、`_execute_task` 的 INSERT、成功/失败路径两条 UPDATE runs
  与 `automation_tasks.last_run_at`；
- 活体验证：`create_run` 探针 insert→读回→删除（无残留）、`find_running_run_id_by_job_id` 可查到刚写行；
  **注意**：第一次探针失败是"我的测试数据错"（`task_id=-1` 违反外键），不是代码错——两者结论相反，先查数据再下结论。
- **`smart_scheduler.py` 已清零（7 → 0）**：`trigger_task` 的 INSERT 也已上收；并删掉上收后残留的
  `conn = get_db_connection()`（无人使用却仍开连接）。该文件仅剩一个未使用的 import 待顺手清理。
- 下一步：`signals_async` → `session_service`（需新建 agent_session 仓储，13 处）。

## 5. 当前闸门状态

```
P0 fstring_value_interp  本轮范围 0   ✅
P0 raw_connect           本轮范围 0   ✅
P1 cursor_execute        本轮范围 116（t3 已从 122 降至 116）
P1 core_text_sql         本轮范围 35
P2 read_sql              本轮范围 5
```

服务重启后：ERROR 0 / session_leak_detected 0 / idle in transaction 0。
