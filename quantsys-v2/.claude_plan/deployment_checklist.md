# SQLAlchemy 2.0 统一迁移 - 部署 Checklist

**部署日期:** ___________  
**执行人:** ___________  
**审批人:** ___________

---

## 上线前准备(Pre-deployment)

### 环境检查
- [ ] **确认 PostgreSQL max_connections 配置**
  ```bash
  # 连接到 PostgreSQL
  psql -U postgres -d quant_investment -c "SHOW max_connections;"
  # 建议值: >= 200 (当前默认 100)
  # 调整方法: postgresql.conf 修改 max_connections=200, 然后 sudo systemctl restart postgresql
  ```

- [ ] **容量规划计算**
  ```
  公式: N_api_instances × 30 + N_scheduler × 30 + N_workers × 10 < max_connections × 0.8
  
  示例(单机部署):
  - 1 个 API 实例 × 30 = 30
  - 1 个 scheduler × 30 = 30
  - 预留(训练脚本等) = 40
  总计: 100 < 200 × 0.8 (160) ✓ 通过
  
  实际计算:
  - API 实例数: _____ × 30 = _____
  - Scheduler: _____ × 30 = _____
  - 其他: _____
  - 总计: _____ < _____ (max_connections × 0.8) ? [ ]通过 [ ]不通过
  ```

- [ ] **备份当前版本**
  ```bash
  cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
  git tag backup-before-sqlalchemy-$(date +%Y%m%d-%H%M%S)
  git push origin --tags
  ```

- [ ] **测试环境验证(24 小时)**
  ```bash
  # 重启测试环境服务
  cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
  pkill -f "python.*server.py"
  python adapters/inbound/api/server.py &
  
  # 监控连接数(每小时检查)
  watch -n 3600 'lsof -nP -iTCP:5432 | grep ESTABLISHED | grep -vi postgres | wc -l'
  
  # 检查错误日志
  tail -f /private/tmp/quantsys-v2-rest.log | grep ERROR
  
  # 验证: 24 小时无连接泄漏、无 "too many clients" 错误
  ```

- [ ] **准备回滚脚本**
  ```bash
  # 保存到 rollback.sh
  cat > /tmp/rollback_sqlalchemy.sh << 'EOF'
  #!/bin/bash
  set -e
  cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
  echo "Rolling back SQLAlchemy migration..."
  git log --oneline -10  # 确认当前位置
  # 方案 A: revert 最近的 commit
  # git revert HEAD --no-edit
  # 方案 B: 回到备份 tag
  BACKUP_TAG=$(git tag | grep "backup-before-sqlalchemy" | tail -1)
  git checkout $BACKUP_TAG
  echo "Rollback complete. Please restart services."
  EOF
  chmod +x /tmp/rollback_sqlalchemy.sh
  ```

---

## 灰度发布(Gradual Rollout)

### Phase 1: 20% 流量(第 1 台实例)

- [ ] **重启第 1 台 API 实例**
  ```bash
  # 假设有多实例部署,先重启 1 台
  # 单实例部署跳过灰度,直接全量
  ssh user@api-instance-1
  cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
  pkill -f "python.*server.py"
  nohup python adapters/inbound/api/server.py > /tmp/api.log 2>&1 &
  ```

- [ ] **观察 30 分钟**
  ```bash
  # 监控指标
  # 1. 连接数
  lsof -nP -iTCP:5432 | grep ESTABLISHED | grep -vi postgres | wc -l
  # 预期: <= 30 (单实例 pool_size=10, max_overflow=20)
  
  # 2. 健康检查
  curl http://127.0.0.1:5001/api/health/db
  # 预期: {"status": "healthy", "utilization": "<80%", ...}
  
  # 3. API 响应时间
  time curl http://127.0.0.1:5001/api/scheduler/tasks?page=1&pageSize=10
  # 预期: < 1s
  
  # 4. 错误日志
  tail -50 /private/tmp/quantsys-v2-rest.log | grep -i "error\|exception"
  # 预期: 无 "too many clients" 或连接相关错误
  ```

- [ ] **验证通过** - 签字: ___________  时间: ___________

### Phase 2: 50% 流量(第 2-3 台实例)

- [ ] **重启第 2-3 台实例**(如有)
  ```bash
  # 重复 Phase 1 步骤
  ```

- [ ] **观察 30 分钟** - 同 Phase 1 监控指标

- [ ] **验证通过** - 签字: ___________  时间: ___________

### Phase 3: 100% 流量(全量上线)

- [ ] **重启所有剩余实例**

- [ ] **重启 scheduler 服务**
  ```bash
  # 找到 scheduler 进程
  ps aux | grep scheduler
  # 重启
  pkill -f "scheduler"
  cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
  nohup python infrastructure/scheduler/scheduler.py > /tmp/scheduler.log 2>&1 &
  ```

- [ ] **验证全量**
  ```bash
  # 连接数
  CONN_COUNT=$(lsof -nP -iTCP:5432 | grep ESTABLISHED | grep -vi postgres | wc -l)
  echo "Total connections: $CONN_COUNT"
  # 预期: <= 容量规划计算值
  
  # 所有实例健康检查
  for host in api-instance-1 api-instance-2 api-instance-3; do
    curl http://$host:5001/api/health/db
  done
  ```

- [ ] **全量验证通过** - 签字: ___________  时间: ___________

---

## 上线后监控(Post-deployment - 24 小时)

### 第 1 小时(密集监控)
- [ ] **每 10 分钟检查连接数**
  ```bash
  for i in {1..6}; do
    echo "Check $i at $(date)"
    lsof -nP -iTCP:5432 | grep ESTABLISHED | grep -vi postgres | wc -l
    curl -s http://127.0.0.1:5001/api/health/db | jq '.utilization'
    sleep 600
  done
  ```

- [ ] **验证无异常** - 签字: ___________

### 第 2-24 小时(常规监控)
- [ ] **每 2 小时检查**(或设置告警)
  ```bash
  # Cron job 示例
  0 */2 * * * /usr/bin/lsof -nP -iTCP:5432 | grep ESTABLISHED | grep -vi postgres | wc -l >> /tmp/db_conn_history.log
  ```

- [ ] **每 4 小时查看错误日志**
  ```bash
  tail -100 /private/tmp/quantsys-v2-rest.log | grep -i "error\|too many"
  ```

### 监控检查点
| 时间 | 连接数 | Utilization | 错误 | 备注 | 签字 |
|---|---|---|---|---|---|
| 上线后 10min | _____ | _____ | [ ]无 [ ]有 | _____ | _____ |
| 上线后 30min | _____ | _____ | [ ]无 [ ]有 | _____ | _____ |
| 上线后 1h | _____ | _____ | [ ]无 [ ]有 | _____ | _____ |
| 上线后 2h | _____ | _____ | [ ]无 [ ]有 | _____ | _____ |
| 上线后 4h | _____ | _____ | [ ]无 [ ]有 | _____ | _____ |
| 上线后 8h | _____ | _____ | [ ]无 [ ]有 | _____ | _____ |
| 上线后 24h | _____ | _____ | [ ]无 [ ]有 | _____ | _____ |

---

## 回滚方案(Rollback Plan)

### 触发条件(任一满足即回滚)
- [ ] 连接数持续 > 容量规划值 80%
- [ ] 出现 "too many clients already" 错误
- [ ] API 响应时间 > 5s(正常 < 1s)
- [ ] 错误率 > 5%

### 回滚步骤
1. **停止所有服务**
   ```bash
   pkill -f "python.*server.py"
   pkill -f "scheduler"
   ```

2. **执行回滚脚本**
   ```bash
   /tmp/rollback_sqlalchemy.sh
   ```

3. **重启服务(旧版本)**
   ```bash
   cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
   nohup python adapters/inbound/api/server.py > /tmp/api.log 2>&1 &
   ```

4. **验证回滚成功**
   ```bash
   curl http://127.0.0.1:5001/api/scheduler/tasks?page=1&pageSize=10
   # 预期: 200 OK
   
   lsof -nP -iTCP:5432 | grep ESTABLISHED | grep -vi postgres | wc -l
   # 预期: 恢复到回滚前水平
   ```

5. **通知相关方** - 邮件/Slack 通知团队,说明回滚原因

### 回滚记录
- [ ] 回滚执行时间: ___________
- [ ] 回滚原因: _______________________
- [ ] 回滚后验证通过: [ ]是 [ ]否
- [ ] 执行人签字: ___________

---

## 上线成功确认

- [ ] **24 小时监控无异常**
- [ ] **连接数稳定在预期范围**
- [ ] **无 "too many clients" 错误**
- [ ] **API 响应时间正常**
- [ ] **错误率 < 1%**

**上线成功** - 项目经理签字: ___________  日期: ___________

---

## 附录: 常见问题排查

### Q1: 连接数突然飙升
```bash
# 查看哪些进程占用连接
lsof -nP -iTCP:5432 | grep ESTABLISHED | grep -vi postgres | awk '{print $2}' | sort | uniq -c | sort -rn

# 杀掉异常进程(谨慎!)
kill <PID>
```

### Q2: 健康检查返回 503
```bash
# 检查 Engine 是否初始化
python3 -c "from infrastructure.persistence.database.engine import get_pool_status; print(get_pool_status())"

# 重启服务
pkill -f "python.*server.py"
python adapters/inbound/api/server.py &
```

### Q3: 出现 "too many clients"
```bash
# 立即降低池大小(临时缓解)
# 编辑 adapters/inbound/api/server.py
# init_engine(pool_size=5, max_overflow=10)  # 从 10/20 降到 5/10

# 或调大 PG max_connections
sudo vi /var/lib/pgsql/data/postgresql.conf
# max_connections = 200
sudo systemctl restart postgresql
```

---

**文档版本:** 1.0  
**最后更新:** 2026-06-24  
**维护人:** Claude (Kiro)
