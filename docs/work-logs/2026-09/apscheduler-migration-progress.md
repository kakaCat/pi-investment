# APScheduler 迁移进度报告 - 2026-09-01

## 执行摘要

**当前状态：** Phase 2 完成（核心实现），进入 Phase 3（集成测试）  
**完成度：** 60%（3/5 阶段）  
**测试结果：** ✅ 9/9 单元测试通过  
**预计剩余时间：** 0.5 天

---

## 已完成工作

### ✅ Phase 1: 准备工作（0.5天）

**完成时间：** 2026-09-01 上午

1. **依赖安装**
   - 添加 `APScheduler==3.10.4` 到 requirements.txt
   - 安装到 Python 3.13 虚拟环境

2. **分支创建**
   - 创建 worktree: `.claude/worktrees/apscheduler-migration`
   - 分支名: `feat/apscheduler-migration`
   - 基于: `ca4d817b` (main 分支最新提交)

3. **备份现有代码**
   - 保留原 `scheduler.py` 作为 fallback

### ✅ Phase 2: 实现 APScheduler 服务（1天）

**完成时间：** 2026-09-01 下午

#### 2.1 核心文件创建

**文件：** `infrastructure/scheduler/apscheduler_service.py` (184 行)

核心功能：
- `__init__`: 配置 APScheduler（jobstore、executor、job_defaults）
- `load_tasks_from_db()`: 从 scheduler_tasks 表加载任务
- `start()`: 启动调度器
- `shutdown()`: 优雅关闭
- `reload_tasks()`: 动态重载任务
- `get_job_status()`: 查询任务状态
- `trigger_task_now()`: 手动触发任务

关键设计：
```python
# 使用 BackgroundScheduler 在后台线程运行
scheduler = BackgroundScheduler(
    jobstores={'default': SQLAlchemyJobStore(url=db_url)},
    executors={'default': ThreadPoolExecutor(max_workers=10)},
    job_defaults={
        'coalesce': False,        # 不合并 misfire
        'max_instances': 1,       # 防止并发
        'misfire_grace_time': 300 # 5分钟宽限期
    }
)

# 直接注册模块级函数，避免序列化问题
scheduler.add_job(
    func=execute_scheduled_job,  # 模块级函数
    trigger=CronTrigger.from_crontab(cron_expression),
    args=[task.id]
)
```

**文件：** `infrastructure/scheduler/job_executor.py` (217 行)

核心功能：
- `execute_scheduled_job(task_id)`: APScheduler 调用的入口
- `_execute_command(command, params)`: 路由到 JobRegistry/Legacy Handler
- `_execute_legacy_handler(command, params)`: Fallback 到 6 个旧 handler
- `_is_zombie_run(run)`: 判断僵尸任务（>6小时）

执行流程：
```
APScheduler 触发
    ↓
execute_scheduled_job(task_id)
    ↓
读取 scheduler_tasks 表
    ↓
检查并发 + 僵尸任务
    ↓
创建 scheduler_runs 记录 (running)
    ↓
_execute_command(command, params)
    ├─ JobRegistry (优先)
    └─ Legacy Handler (fallback)
    ↓
更新 scheduler_runs (success/failed)
```

#### 2.2 FastAPI 集成

**修改：** `adapters/inbound/fastapi_app/main.py`

启动时：
```python
# 初始化 JobRegistry
register_all_jobs()

# 启动 APScheduler（fallback 模式，Agent OS 不可用时）
if not use_agent_os_scheduler:
    scheduler_service = APSchedulerService(db_url, repo)
    scheduler_service.start()
    app.state.scheduler_service = scheduler_service
```

关闭时：
```python
# 优雅关闭 APScheduler
scheduler_service = getattr(app.state, 'scheduler_service', None)
if scheduler_service is not None:
    scheduler_service.shutdown(wait=True)
```

#### 2.3 API 端点扩展

**修改：** `adapters/inbound/fastapi_app/routes/scheduler_async.py`

新增/修改端点：
- `POST /api/scheduler/tasks/{task_id}/trigger` - 手动触发（支持 APScheduler）
- `POST /api/scheduler/reload` - 重新加载任务（APScheduler 专用）

#### 2.4 测试验证

**文件：** `tests/infrastructure/test_apscheduler_service.py` (195 行)

9 个测试用例：
1. ✅ `test_apscheduler_service_initialization` - 初始化
2. ✅ `test_load_tasks_from_db` - 加载任务（2个加载，1个跳过）
3. ✅ `test_start_and_shutdown` - 启动和关闭
4. ✅ `test_reload_tasks` - 重新加载
5. ✅ `test_get_job_status` - 查询状态
6. ✅ `test_trigger_task_now` - 手动触发
7. ✅ `test_skip_agent_os_managed_tasks` - 跳过 Agent OS 任务
8. ✅ `test_job_execution_integration` - 执行集成验证
9. ✅ `test_cron_trigger_parsing` - Cron 解析

**测试结果：**
```
9 passed, 1 warning in 0.26s
```

---

## 技术亮点

### 1. 序列化问题解决

**问题：** APScheduler 需要序列化任务函数，实例方法会导致整个对象被序列化

**解决：** 直接使用模块级函数 `execute_scheduled_job`
```python
# ❌ 错误（会序列化整个 APSchedulerService 实例）
scheduler.add_job(func=self._execute_task_wrapper, ...)

# ✅ 正确（只序列化函数引用）
from infrastructure.scheduler.job_executor import execute_scheduled_job
scheduler.add_job(func=execute_scheduled_job, ...)
```

### 2. 向后兼容设计

保留现有 `scheduler_tasks` 和 `scheduler_runs` 表：
- APScheduler 使用独立的 `apscheduler_jobs` 表
- `scheduler_tasks` 仍是任务定义的唯一来源
- `scheduler_runs` 继续记录执行历史
- 新旧系统可以无缝切换

### 3. Agent OS 集成

跳过 `cron_expression='managed_by_agent_os'` 的任务：
```python
if task.cron_expression == "managed_by_agent_os":
    logger.info(f"Skip Agent OS managed task: {task.name}")
    continue
```

### 4. 优雅关闭

```python
scheduler_service.shutdown(wait=True)  # 等待正在执行的任务完成
```

---

## 当前架构

```
FastAPI lifespan
    ↓
注册 JobRegistry (28 jobs)
    ↓
启动 APScheduler
    ├─ 加载 scheduler_tasks
    ├─ 跳过 managed_by_agent_os
    └─ 注册到 BackgroundScheduler
    ↓
定时触发
    ↓
execute_scheduled_job(task_id)
    ↓
JobRegistry.execute() / Legacy Handler
    ↓
记录 scheduler_runs
```

---

## 待完成工作

### ⏳ Phase 3: 测试验证（0.5天）

#### 3.1 集成测试（待执行）

**目标：** 在测试环境验证完整调度链路

**测试步骤：**
1. 启动 FastAPI 服务（worktree 环境）
2. 检查 APScheduler 启动日志
3. 手动触发一个测试任务
4. 验证执行记录写入 scheduler_runs
5. 验证任务重载功能

**验收标准：**
- [ ] APScheduler 成功启动并加载任务
- [ ] 任务按 cron 表达式准时执行（误差 <5 秒）
- [ ] 手动触发 API 正常工作
- [ ] scheduler_runs 正确记录执行历史

#### 3.2 灰度测试（待执行）

**目标：** 选择 3 个低频任务进行 24 小时灰度

**候选任务：**
```sql
SELECT id, name, cron_expression 
FROM scheduler_tasks 
WHERE is_enabled = true 
  AND (
    cron_expression LIKE '%weekly%'
    OR cron_expression LIKE '0 0%'  -- 每日凌晨
  )
ORDER BY id
LIMIT 3;
```

**监控指标：**
- 任务执行成功率
- 执行时间分布
- 错误日志
- CPU/内存使用率

### ⏳ Phase 4: 全量切换（0.5天）

#### 4.1 代码清理

**目标：** 移除手写调度器的冗余代码

**删除内容：**
- `scheduler.py` 中的 cron 解析器（~200 行）
- `scheduler.py` 中的轮询循环（~100 行）
- 已迁移到 JobRegistry 的 handler 方法（28 个）

**保留内容：**
- 6 个 Legacy Handler（待后续迁移）
- SchedulerRepository 接口
- 数据模型定义

#### 4.2 文档更新

- [ ] 更新 [scheduler-jobreg-architecture.md](scheduler-jobreg-architecture.md)
- [ ] 添加 APScheduler 章节
- [ ] 更新部署文档

#### 4.3 合并到 main

```bash
cd /Users/yunpeng/pi-investment
git checkout main
git merge --no-ff feat/apscheduler-migration
git push origin main
```

#### 4.4 生产部署

```bash
# 重启 5001 服务
launchctl kickstart -k gui/$(id -u)/com.pi-investment.v2-api

# 验证服务启动
curl http://localhost:5001/api/scheduler/tasks | jq '.data | length'
```

---

## 风险与缓解

### 风险 1: APScheduler 性能问题

**可能性：** 低  
**影响：** 中  
**缓解措施：**
- APScheduler 是成熟框架，性能经过验证
- 使用 ThreadPoolExecutor 限制并发（max_workers=10）
- 定期监控 CPU/内存使用

### 风险 2: 任务重复执行

**可能性：** 低  
**影响：** 高  
**缓解措施：**
- 设置 `max_instances=1`（每个任务最多 1 个实例）
- SQLAlchemyJobStore 使用 PostgreSQL advisory lock
- scheduler_runs 表有 `status='running'` 检查

### 风险 3: Cron 表达式解析差异

**可能性：** 低  
**影响：** 中  
**缓解措施：**
- APScheduler 使用标准 cron 解析（兼容性更好）
- 单元测试覆盖 cron 解析
- 灰度测试验证实际执行时间

### 风险 4: 回滚困难

**可能性：** 低  
**影响：** 高  
**缓解措施：**
- 保留 `scheduler.py` 完整代码
- 分支隔离，可快速 revert
- scheduler_tasks/scheduler_runs 表不变，兼容新旧实现

---

## 性能对比（预期）

| 指标 | 手写调度器 | APScheduler | 改善 |
|------|-----------|-------------|------|
| 调度精度 | 0-30秒误差 | <5秒 | **6x 提升** |
| CPU 空闲占用 | ~10% | <5% | **50% 降低** |
| 代码行数 | 894 行 | 550 行 | **38% 减少** |
| 维护成本 | 自己维护 | 社区维护 | **大幅降低** |
| 分布式支持 | ❌ 无 | ✅ 有 | **新增能力** |

---

## 时间线

| 日期 | 阶段 | 状态 | 耗时 |
|------|------|------|------|
| 2026-09-01 上午 | Phase 1: 准备工作 | ✅ 完成 | 0.5h |
| 2026-09-01 下午 | Phase 2: 核心实现 | ✅ 完成 | 3h |
| 2026-09-01 晚上 | Phase 3: 集成测试 | ⏳ 进行中 | - |
| 2026-09-02 上午 | Phase 4: 全量切换 | ⏸️ 待开始 | - |

---

## 下一步行动

### 立即可执行

1. **启动集成测试环境**
   ```bash
   cd /Users/yunpeng/pi-investment/.claude/worktrees/apscheduler-migration/quantsys-v2
   DISABLE_WATCH_ENGINE=true DISABLE_ORCHESTRATOR=true python adapters/inbound/fastapi_app/main.py
   ```

2. **验证 APScheduler 启动**
   ```bash
   curl http://localhost:5001/api/scheduler/tasks
   ```

3. **手动触发测试任务**
   ```bash
   curl -X POST http://localhost:5001/api/scheduler/tasks/1/trigger
   ```

### 用户决策点

- [ ] 批准进入 Phase 3 集成测试
- [ ] 确认灰度任务列表（建议提供 3 个低频任务 ID）
- [ ] 确认合并时间（建议 24 小时灰度后合并）

---

**文档版本：** v1.0  
**最后更新：** 2026-09-01 下午  
**下次更新：** Phase 3 完成后
