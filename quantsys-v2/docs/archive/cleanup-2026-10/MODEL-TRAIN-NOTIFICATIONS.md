# 模型训练通知与监控配置

## 概述

训练自动化系统支持飞书通知，在以下场景自动发送消息：
- ✅ 训练成功（含性能指标）
- ❌ 训练失败（含错误信息）
- ⊙ 训练跳过（可选，默认不发送）
- 🚨 性能告警（测试准确率<50%）

---

## 配置飞书Webhook

### 1. 创建飞书机器人

1. 打开飞书群聊
2. 群设置 → 机器人 → 添加机器人 → 自定义机器人
3. 设置机器人名称：`模型训练通知`
4. 复制Webhook地址（格式：`https://open.feishu.cn/open-apis/bot/v2/hook/xxx`）

### 2. 配置环境变量

```bash
# 方式A：添加到环境变量（推荐）
echo 'export FEISHU_WEBHOOK_MODEL_TRAIN="https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_TOKEN"' >> ~/.zshrc
source ~/.zshrc

# 方式B：添加到activate脚本
cd /Users/yunpeng/pi-investment/quantsys-v2
echo 'export FEISHU_WEBHOOK_MODEL_TRAIN="https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_TOKEN"' >> activate-py313.sh
```

### 3. 测试通知

```bash
cd /Users/yunpeng/pi-investment/quantsys-v2
source activate-py313.sh

python3 << 'PYEOF'
from application.services.ml_train_notification import send_feishu_notification
import os

webhook = os.getenv("FEISHU_WEBHOOK_MODEL_TRAIN")
if webhook:
    success = send_feishu_notification(
        webhook_url=webhook,
        title="✅ 测试通知",
        content="这是一条测试消息，如果收到说明配置成功！"
    )
    print(f"发送{'成功' if success else '失败'}")
else:
    print("❌ 未配置环境变量 FEISHU_WEBHOOK_MODEL_TRAIN")
PYEOF
```

---

## 通知场景

### 1. 训练成功通知

**触发条件**：训练完成且性能正常

**消息内容**：
```
✅ 模型训练成功

模型版本: 20260820_030015
训练样本: 480 只股票
训练准确率: 62.34%
测试准确率: 58.12%
自动切换: ✅ 已切换

训练时间: 2026-08-20T03:15:22Z
```

### 2. 训练成功但性能低

**触发条件**：训练完成但test_accuracy < 0.52

**消息内容**：
```
⚠️ 模型训练成功（性能低）

模型版本: 20260820_030015
训练样本: 480 只股票
训练准确率: 62.34%
测试准确率: 48.50%
自动切换: ⊙ 未切换

⚠️ 警告: 测试准确率低于52%，建议检查特征质量

训练时间: 2026-08-20T03:15:22Z
```

### 3. 训练失败告警

**触发条件**：训练过程中发生异常

**消息内容**：
```
❌ 模型训练失败

错误信息: 数据不足：仅加载30只股票（需>=50）

失败时间: 2026-08-20T03:05:10Z

建议检查:
- 数据可用性（因子数据是否充足）
- 后端日志（/tmp/quantsys-v2.log）
- 数据库连接
```

### 4. 训练跳过通知

**触发条件**：智能判断不需要训练

**默认行为**：不发送（避免打扰）

如需启用，编辑 `application/services/ml_train_notification.py`：
```python
def notify_train_skipped(...):
    # 取消下面的注释
    reason = result.get("reason", "未知原因")
    title = "⊙ 模型训练跳过"
    content = f"**原因**: {reason}\n\n**时间**: {result.get('timestamp')}"
    return send_feishu_notification(webhook_url, title, content)
```

---

## 性能监控告警

### 自动监控

**定时任务**：每天检查当前模型性能

```bash
# 配置cron（每天10:00检查）
crontab -e

# 添加：
0 10 * * * /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_monitor_model_performance.sh
```

**告警条件**：当前模型test_accuracy < 0.50

**告警消息**：
```
🚨 模型性能告警

当前模型: lightgbm_20260815_030015
测试准确率: 48.50% (阈值: 50%)
训练日期: 2026-08-15

建议: 立即重新训练模型
```

### 手动检查

```bash
cd /Users/yunpeng/pi-investment/quantsys-v2
source activate-py313.sh

python3 -c "
from application.services.ml_train_notification import check_model_performance_alert
alerted = check_model_performance_alert()
print('⚠️ 性能告警' if alerted else '✓ 性能正常')
"
```

---

## 完整配置清单

### 1. 配置Webhook

```bash
# 添加环境变量
export FEISHU_WEBHOOK_MODEL_TRAIN="https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_TOKEN"
```

### 2. 配置定时任务

```bash
crontab -e

# 添加以下行：
# 每周一03:00训练
0 3 * * 1 /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model.sh

# 每月1号03:00强制训练
0 3 1 * * /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_train_model_force.sh

# 每天10:00性能监控
0 10 * * * /Users/yunpeng/pi-investment/quantsys-v2/tools/cron_monitor_model_performance.sh
```

### 3. 验证配置

```bash
# 测试训练通知
cd quantsys-v2 && source activate-py313.sh
python -c "
from application.services.scheduler_tasks import handle_model_train_auto
result = handle_model_train_auto({'symbols_limit': 20, 'force_train': True})
# 应该在飞书收到通知
"

# 测试性能监控
./tools/cron_monitor_model_performance.sh
```

---

## 高级配置

### 自定义通知模板

编辑 `application/services/ml_train_notification.py`：

```python
def notify_train_success(result: Dict[str, Any], webhook_url: str = None):
    # 自定义标题
    title = "🎉 模型训练完成"
    
    # 自定义内容
    content = f"""
**模型**: {result['version']}
**性能**: {result['test_accuracy']:.2%}
自定义内容...
"""
    
    return send_feishu_notification(webhook_url, title, content)
```

### 多群通知

```bash
# 配置多个webhook
export FEISHU_WEBHOOK_MODEL_TRAIN="https://..."       # 主群
export FEISHU_WEBHOOK_ALERT="https://..."             # 告警群

# 代码中按场景选择
if test_acc < 0.50:
    webhook = os.getenv("FEISHU_WEBHOOK_ALERT")  # 发送到告警群
else:
    webhook = os.getenv("FEISHU_WEBHOOK_MODEL_TRAIN")  # 发送到主群
```

### 禁用通知

```bash
# 临时禁用（清空环境变量）
unset FEISHU_WEBHOOK_MODEL_TRAIN

# 或在代码中禁用
# application/services/scheduler_tasks.py
# 注释掉 notify_train_result() 调用
```

---

## 监控与日志

### 查看通知日志

```bash
# 训练日志（含通知发送记录）
tail -100 /tmp/model-train-$(date +%Y%m%d).log | grep "通知"

# 性能监控日志
tail -50 /tmp/model-monitor-$(date +%Y%m%d).log
```

### 排查通知失败

1. **检查环境变量**：
   ```bash
   echo $FEISHU_WEBHOOK_MODEL_TRAIN
   ```

2. **手动测试Webhook**：
   ```bash
   curl -X POST $FEISHU_WEBHOOK_MODEL_TRAIN \
     -H "Content-Type: application/json" \
     -d '{"msg_type":"text","content":{"text":"测试"}}'
   ```

3. **查看Python日志**：
   ```bash
   grep "飞书通知" /tmp/quantsys-v2.log
   ```

---

## 最佳实践

1. **使用独立机器人**：为训练通知创建专用机器人，避免与其他通知混淆
2. **合理设置阈值**：test_accuracy < 0.50 告警，可根据实际调整
3. **定期检查**：每天监控性能，每周训练保持模型新鲜
4. **告警分级**：性能低（<0.52）警告，严重低（<0.50）告警
5. **保留历史**：通知日志保留30天，便于回溯

---

**创建时间**：2026-08-20  
**适用版本**：quantsys-v2 v2.0+  
**依赖**：飞书机器人、Python requests库
