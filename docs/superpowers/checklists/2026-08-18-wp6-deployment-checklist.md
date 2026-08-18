# WP-6 生产部署检查清单

**日期**: 2026-08-18  
**任务**: BaseRepository 迁移生产验证  
**目标**: 确认 idle-in-transaction 问题已解决

---

## 预部署检查 ✅

- [x] WP-0: 基线快照完成
- [x] WP-1: db_cursor + validators 基建完成
- [x] WP-2: StockPoolRepository 迁移完成
- [x] WP-3: StrategyPerformanceRepository 迁移完成
- [x] WP-4: 直插用法改写完成
- [x] WP-5: legacy 文件删除完成
- [x] 所有改动已在 main 分支
- [x] 冷启动验证通过（三端点 200 OK）
- [x] 连接健康验证脚本已就绪

---

## 部署步骤

### 1. 备份当前生产环境

```bash
# 记录当前 commit
cd /Users/yunpeng/pi-investment/quantsys-v2
git log -1 --oneline > /tmp/pre-migration-commit.txt

# 备份当前数据库连接状态
psql -d quant_investment -c "
  SELECT state, count(*) 
  FROM pg_stat_activity 
  WHERE datname = 'quant_investment' 
  GROUP BY state
" > /tmp/pre-migration-connections.txt
```

### 2. 部署新代码

```bash
cd /Users/yunpeng/pi-investment/quantsys-v2
git pull origin main

# 确认在正确的 commit
git log -1 --oneline
# 应该显示: 8458017 feat(WP-5): 删除 legacy base_repository.py 并完成全量回归

# 重启服务
sudo launchctl kickstart -k system/com.pi-investment.v2-api

# 等待启动（约 10 秒）
sleep 10
```

### 3. 立即验证

```bash
# 检查服务是否启动
curl -s http://127.0.0.1:5001/api/health/db | jq '.'

# 检查关键端点
curl -s http://127.0.0.1:5001/api/pools | jq '.success'
curl -s http://127.0.0.1:5001/api/agent/logs?page=1&page_size=5 | jq '.success'

# 启动连接健康监控
cd /Users/yunpeng/pi-investment/quantsys-v2
nohup python scripts/verify_connection_health.py --continuous --interval 300 > logs/connection_health.log 2>&1 &

echo "监控进程已启动，日志: logs/connection_health.log"
```

---

## 监控计划（24-48 小时）

### 每 6 小时检查一次

```bash
# 检查监控日志
tail -50 ~/pi-investment/quantsys-v2/logs/connection_health.log

# 手动查询数据库
psql -d quant_investment -c "
SELECT 
  state, 
  count(*) as count,
  max(state_change) as last_change
FROM pg_stat_activity 
WHERE datname = 'quant_investment' 
GROUP BY state;
"
```

**预期结果**：
- ✅ `idle in transaction` = 0
- ✅ `active` + `idle` < 10（正常工作负载）
- ✅ 无长时间连接残留

### 关键时间点

- [x] **T+0 小时**（部署后立即）- 立即验证
- [ ] **T+6 小时** - 第一次定期检查
- [ ] **T+12 小时** - 第二次定期检查
- [ ] **T+24 小时** - 日运行验证
- [ ] **T+48 小时** - 最终验证

---

## 验收标准

### 必须满足（P0）

- [ ] `idle in transaction` 连接数 = 0（持续 24 小时）
- [ ] 所有 API 端点响应正常（< 200ms）
- [ ] 无连接池耗尽告警
- [ ] agent-ts 可正常调用 API

### 应该满足（P1）

- [ ] 连接池利用率 < 50%（checked_out < 10）
- [ ] 无慢查询（> 5秒）
- [ ] 连接数稳定（不持续增长）

---

## 回滚计划（如果失败）

### 触发条件

- `idle in transaction` 连接数 > 5（持续 10 分钟）
- API 响应超时（> 5 秒）
- 连接池耗尽告警
- agent-ts 无法正常工作

### 回滚步骤

```bash
# 1. 停止服务
sudo launchctl stop system/com.pi-investment.v2-api

# 2. 回退代码（回退到 WP-5 之前）
cd /Users/yunpeng/pi-investment/quantsys-v2
git revert 8458017 c2db78c ed316ec 9af088a 02fa120 e22ef63
# 或者直接 reset 到迁移前
git reset --hard 3bf154c

# 3. 重启服务
sudo launchctl start system/com.pi-investment.v2-api

# 4. 验证回滚成功
curl http://127.0.0.1:5001/api/health/db

# 5. 分析失败原因
tail -200 ~/v2-api.log
```

---

## 成功标准

### 阶段 1：立即验证（T+0）

- [x] 服务启动成功
- [x] 三个端点 200 OK
- [x] 监控脚本运行中

### 阶段 2：短期验证（T+6 小时）

- [ ] `idle in transaction` = 0
- [ ] 连接数 < 10
- [ ] 无慢查询

### 阶段 3：中期验证（T+24 小时）

- [ ] `idle in transaction` 持续为 0
- [ ] API 响应时间正常
- [ ] agent-ts 正常工作

### 阶段 4：最终验证（T+48 小时）

- [ ] 所有验收标准满足
- [ ] 无回滚需求
- [ ] 可宣布迁移成功

---

## 完成标准

**满足以下所有条件时，迁移正式完成**：

1. ✅ 运行满 48 小时无故障
2. ✅ `idle in transaction` 持续为 0
3. ✅ 所有 API 功能正常
4. ✅ agent-ts 集成正常
5. ✅ 无需回滚

**完成后操作**：
- 更新 `docs/superpowers/reports/2026-08-18-base-repository-migration-completion.md`
- 添加"生产验证成功"章节
- 归档监控日志
- 删除备份文件
- 通知团队迁移完成

---

## 联系人

**责任人**: yunpeng  
**紧急联系**: 如果出现问题，立即执行回滚计划  
**监控工具**: `scripts/verify_connection_health.py`  
**日志位置**: `~/pi-investment/quantsys-v2/logs/connection_health.log`

---

**检查清单创建时间**: 2026-08-18 14:45  
**预计完成时间**: 2026-08-20 14:45（48 小时后）
