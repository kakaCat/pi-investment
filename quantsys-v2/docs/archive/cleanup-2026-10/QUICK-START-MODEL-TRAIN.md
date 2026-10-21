# 模型训练自动化 - 快速配置指南

## 1分钟配置完成

### 前置条件
- ✅ quantsys-v2后端运行（5001端口）
- ✅ 因子数据已回填（146万条）
- ✅ Python环境已激活

### 配置步骤

#### 1. 测试训练脚本（可选）
```bash
cd /Users/yunpeng/pi-investment/quantsys-v2

# 小规模测试（20只股票，约5分钟）
./tools/cron_train_model.sh
```

#### 2. 配置cron定时任务

**方式A：使用命令行**
```bash
# 编辑crontab
crontab -e

# 添加以下两行：
0 3 * * 1 /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model.sh
0 3 1 * * /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model_force.sh

# 保存退出（:wq）
```

**方式B：使用脚本添加**
```bash
# 自动添加到crontab
(crontab -l 2>/dev/null; echo "0 3 * * 1 /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model.sh") | crontab -
(crontab -l 2>/dev/null; echo "0 3 1 * * /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model_force.sh") | crontab -
```

#### 3. 验证配置
```bash
# 查看已配置的定时任务
crontab -l | grep model

# 应显示：
# 0 3 * * 1 /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model.sh
# 0 3 1 * * /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model_force.sh
```

### 完成！✅

系统将在以下时间自动运行：
- **每周一 03:00** - 智能训练（7天未更新或性能低时训练）
- **每月1号 03:00** - 强制训练（定期更新，需人工审核）

---

## 手动触发训练

### 完整训练（500只股票）
```bash
cd /Users/yunpeng/pi-investment/quantsys-v2
./tools/cron_train_model.sh
```

### 快速测试（20只股票）
```bash
cd /Users/yunpeng/pi-investment/quantsys-v2
source activate-py313.sh
python3 << 'PYEOF'
from application.services.scheduler_tasks import handle_model_train_auto
result = handle_model_train_auto({"symbols_limit": 20, "force_train": True})
print(f"Status: {result['status']}")
if result['status'] == 'success':
    print(f"Version: {result['version']}, Acc: {result['test_accuracy']}")
PYEOF
```

---

## 查看运行日志

```bash
# 查看今天的日志
tail -100 /tmp/model-train-$(date +%Y%m%d).log

# 查看所有历史日志
ls -lh /tmp/model-train-*.log

# 实时监控
tail -f /tmp/model-train-$(date +%Y%m%d).log
```

---

## 查看训练历史

```bash
# 连接数据库
psql postgresql://mac@127.0.0.1:5432/quant_investment

# 查看最近10次训练
SELECT model_type, version, train_accuracy, test_accuracy, 
       train_date, status
FROM quant.ml_models
ORDER BY train_date DESC
LIMIT 10;

# 查看最新模型
SELECT * FROM quant.ml_models
WHERE model_type = 'lightgbm'
ORDER BY train_date DESC
LIMIT 1;
```

---

## 停止/修改定时任务

```bash
# 临时禁用
crontab -e
# 在对应行前加 # 注释

# 完全删除
crontab -e
# 删除对应行

# 修改时间
crontab -e
# 编辑cron表达式
```

---

## 时间配置说明

**Cron表达式格式**：`分 时 日 月 周`

| 配置 | 说明 |
|------|------|
| `0 3 * * 1` | 每周一 03:00 |
| `0 3 1 * *` | 每月1号 03:00 |
| `0 3 * * *` | 每天 03:00 |
| `0 */6 * * *` | 每6小时（00:00, 06:00, 12:00, 18:00） |

---

## 故障排查

### 问题1：cron未执行
```bash
# 检查cron服务
ps aux | grep cron

# 检查cron日志（macOS）
log show --predicate 'process == "cron"' --last 1h
```

### 问题2：脚本执行失败
```bash
# 检查脚本权限
ls -l /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model.sh

# 应显示：-rwxr-xr-x（可执行）
# 如果不是，执行：
chmod +x /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model.sh
```

### 问题3：Python环境错误
```bash
# 手动测试激活脚本
cd /Users/yunpeng/pi-investment/quantsys-v2
source activate-py313.sh
python --version  # 应显示 Python 3.13.14
```

---

**配置时间**：< 1分钟  
**首次训练**：约30-60分钟（500只股票）  
**后续智能训练**：仅在需要时执行  

✅ 配置完成后即可享受全自动模型训练！
