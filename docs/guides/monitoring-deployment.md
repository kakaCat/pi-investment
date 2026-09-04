# quantsys-v2 数据源监控部署指南

**创建日期**: 2026-09-01  
**版本**: v1.0

---

## 概述

本指南介绍如何部署 quantsys-v2 多数据源的 Prometheus + Grafana 监控系统。

---

## 1. 安装依赖

### 1.1 Python 依赖

```bash
cd /Users/yunpeng/pi-investment/quantsys-v2
source venv/bin/activate

# 安装 prometheus_client
pip install prometheus-client==0.20.0
```

### 1.2 Prometheus 安装（macOS）

```bash
# 使用 Homebrew 安装
brew install prometheus

# 或下载二进制文件
# https://prometheus.io/download/
```

### 1.3 Grafana 安装（macOS）

```bash
# 使用 Homebrew 安装
brew install grafana

# 启动 Grafana 服务
brew services start grafana

# 默认访问地址：http://localhost:3000
# 默认用户名/密码：admin/admin
```

---

## 2. 配置 Prometheus

### 2.1 创建 Prometheus 配置文件

创建 `/usr/local/etc/prometheus.yml`（或自定义路径）：

```yaml
global:
  scrape_interval: 15s      # 抓取间隔
  evaluation_interval: 15s  # 告警规则评估间隔
  external_labels:
    cluster: 'pi-investment'
    environment: 'production'

# 告警管理器配置（可选）
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - localhost:9093

# 告警规则文件
rule_files:
  - "/Users/yunpeng/pi-investment/quantsys-v2/config/prometheus/alert_rules.yml"

# 抓取目标配置
scrape_configs:
  # quantsys-v2 数据源监控
  - job_name: 'quantsys-v2-datasources'
    static_configs:
      - targets: ['localhost:5001']
    metrics_path: '/metrics'
    scrape_interval: 15s
    scrape_timeout: 10s
```

### 2.2 验证配置

```bash
# 检查配置文件语法
promtool check config /usr/local/etc/prometheus.yml

# 检查告警规则
promtool check rules /Users/yunpeng/pi-investment/quantsys-v2/config/prometheus/alert_rules.yml
```

### 2.3 启动 Prometheus

```bash
# 启动 Prometheus（使用 Homebrew）
brew services start prometheus

# 或手动启动
prometheus --config.file=/usr/local/etc/prometheus.yml \
  --storage.tsdb.path=/usr/local/var/prometheus \
  --web.console.templates=/usr/local/etc/prometheus/consoles \
  --web.console.libraries=/usr/local/etc/prometheus/console_libraries

# 访问 Prometheus UI：http://localhost:9090
```

---

## 3. 配置 quantsys-v2 暴露指标

### 3.1 注册 metrics 端点到 Flask

编辑 `adapters/inbound/flask_app/app.py`（或主应用文件）：

```python
from adapters.inbound.flask_app.metrics_endpoint import metrics_bp

def create_app():
    app = Flask(__name__)
    
    # ... 其他配置 ...
    
    # 注册 metrics 蓝图
    app.register_blueprint(metrics_bp)
    
    return app
```

### 3.2 重启 quantsys-v2 服务

```bash
# 使用 launchctl 重启
launchctl kickstart -k gui/501/com.pi-investment.v2-api

# 或手动重启
pkill -f "python.*quantsys-v2"
cd /Users/yunpeng/pi-investment/quantsys-v2
python start_all.py
```

### 3.3 验证指标暴露

```bash
# 检查 metrics 端点
curl http://localhost:5001/metrics

# 预期看到类似输出：
# # HELP provider_health_score Provider health score based on success rate
# # TYPE provider_health_score gauge
# provider_health_score{provider_name="tencent",provider_type="quote"} 0.85
# provider_health_score{provider_name="sina",provider_type="quote"} 0.78
# ...
```

---

## 4. 配置 Grafana 仪表盘

### 4.1 添加 Prometheus 数据源

1. 访问 Grafana：http://localhost:3000
2. 登录（默认 admin/admin）
3. 进入 **Configuration → Data Sources**
4. 点击 **Add data source**
5. 选择 **Prometheus**
6. 配置：
   - **Name**: `Prometheus`
   - **URL**: `http://localhost:9090`
   - **Access**: `Server (default)`
7. 点击 **Save & Test**

### 4.2 导入仪表盘模板

将以下 JSON 保存为 `quantsys-v2-datasources-dashboard.json`：

```json
{
  "dashboard": {
    "title": "quantsys-v2 数据源监控",
    "tags": ["quantsys-v2", "datasources", "monitoring"],
    "timezone": "browser",
    "panels": [
      {
        "title": "Provider 健康评分",
        "type": "graph",
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "provider_health_score",
            "legendFormat": "{{provider_name}} ({{provider_type}})"
          }
        ]
      },
      {
        "title": "Provider 熔断器状态",
        "type": "stat",
        "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "provider_circuit_breaker_state",
            "legendFormat": "{{provider_name}}"
          }
        ],
        "fieldConfig": {
          "overrides": [],
          "defaults": {
            "mappings": [
              {"value": 0, "text": "CLOSED", "color": "green"},
              {"value": 1, "text": "OPEN", "color": "red"},
              {"value": 2, "text": "HALF_OPEN", "color": "yellow"}
            ]
          }
        }
      },
      {
        "title": "缓存命中率",
        "type": "graph",
        "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "cache_hit_ratio",
            "legendFormat": "{{method}}"
          }
        ],
        "yaxes": [
          {"format": "percentunit", "min": 0, "max": 1}
        ]
      },
      {
        "title": "Provider 请求耗时 (P95)",
        "type": "graph",
        "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(provider_request_duration_seconds_bucket[5m]))",
            "legendFormat": "{{provider_name}}"
          }
        ],
        "yaxes": [
          {"format": "s"}
        ]
      },
      {
        "title": "Provider 请求总数",
        "type": "graph",
        "gridPos": {"x": 0, "y": 16, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "rate(provider_request_total[5m])",
            "legendFormat": "{{provider_name}} - {{result}}"
          }
        ]
      },
      {
        "title": "降级事件",
        "type": "graph",
        "gridPos": {"x": 12, "y": 16, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "rate(provider_failover_total[5m])",
            "legendFormat": "{{provider_name}} - {{reason}}"
          }
        ]
      }
    ]
  }
}
```

**导入步骤**：
1. Grafana 左侧菜单 → **Dashboards → Import**
2. 上传 JSON 文件或粘贴 JSON 内容
3. 选择 Prometheus 数据源
4. 点击 **Import**

---

## 5. 配置告警通知（可选）

### 5.1 安装 Alertmanager

```bash
brew install alertmanager
```

### 5.2 配置 Alertmanager

创建 `/usr/local/etc/alertmanager.yml`：

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'priority']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'
  routes:
    # P0 告警立即发送
    - match:
        priority: P0
      receiver: 'critical'
      group_wait: 0s
      repeat_interval: 1h
    # P1 告警批量发送
    - match:
        priority: P1
      receiver: 'warning'
      group_wait: 30s
      repeat_interval: 4h

receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://localhost:8080/alerts'
  
  - name: 'critical'
    # 飞书 Webhook（替换为实际 URL）
    webhook_configs:
      - url: 'https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_TOKEN'
        send_resolved: true
  
  - name: 'warning'
    webhook_configs:
      - url: 'https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_TOKEN'
        send_resolved: true

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'provider_name']
```

### 5.3 启动 Alertmanager

```bash
brew services start alertmanager

# 访问 Alertmanager UI：http://localhost:9093
```

---

## 6. 验证监控系统

### 6.1 触发测试告警

```python
# 在 Python REPL 中手动触发 Provider 失败
from adapters.outbound.datasources.manager import get_data_provider_manager

manager = get_data_provider_manager()

# 模拟连续失败触发熔断
for i in range(15):
    manager._record_failure('tencent', reason='test')

# 检查熔断器状态
cb = manager._circuit_breakers['tencent']
print(f"Circuit breaker state: {cb.get_state()}")

# 检查 Prometheus 指标
# 访问 http://localhost:9090/graph
# 查询：provider_circuit_breaker_state{provider_name="tencent"}
# 应该看到值从 0 变为 1（OPEN）
```

### 6.2 检查告警

1. 访问 Prometheus Alerts 页面：http://localhost:9090/alerts
2. 应该看到 `ProviderCircuitBreakerOpen` 告警触发
3. 访问 Alertmanager：http://localhost:9093
4. 应该看到告警通知

### 6.3 恢复测试

```python
# 重置熔断器
manager.reset_circuit_breakers()

# 验证熔断器已关闭
cb = manager._circuit_breakers['tencent']
print(f"Circuit breaker state: {cb.get_state()}")  # 应该是 CLOSED

# 告警应该在 5 分钟内自动解决
```

---

## 7. 日常运维

### 7.1 查看实时指标

```bash
# Prometheus 查询示例

# 1. Provider 健康评分
provider_health_score

# 2. 缓存命中率（5 分钟平均）
rate(cache_hit_total[5m]) / (rate(cache_hit_total[5m]) + rate(cache_miss_total[5m]))

# 3. Provider 成功率（5 分钟平均）
rate(provider_request_total{result="success"}[5m]) / rate(provider_request_total[5m])

# 4. 最慢的 Provider（P95 耗时）
topk(5, histogram_quantile(0.95, rate(provider_request_duration_seconds_bucket[5m])))

# 5. 降级最频繁的 Provider
topk(5, rate(provider_failover_total[5m]))
```

### 7.2 手动重置熔断器

```python
from adapters.outbound.datasources.manager import get_data_provider_manager

manager = get_data_provider_manager()

# 重置所有熔断器
manager.reset_circuit_breakers()

# 或重置单个 Provider
cb = manager._circuit_breakers['tencent']
cb.reset()
```

### 7.3 清理缓存

```python
from adapters.outbound.datasources.manager import get_data_provider_manager

manager = get_data_provider_manager()

# 清空所有缓存
manager._cache.clear()

# 查看缓存统计
stats = manager._cache.get_stats()
print(stats)
```

---

## 8. 故障排查

### 8.1 指标未上报

**问题**: Prometheus 抓取失败，显示 "context deadline exceeded"

**排查步骤**:
```bash
# 1. 检查 quantsys-v2 是否运行
curl http://localhost:5001/health

# 2. 检查 metrics 端点
curl http://localhost:5001/metrics

# 3. 检查 Prometheus 日志
tail -f /usr/local/var/log/prometheus.log

# 4. 检查防火墙/端口占用
lsof -i :5001
```

**解决方案**:
- 确保 quantsys-v2 服务运行正常
- 确保 metrics_bp 已注册到 Flask app
- 检查 prometheus.yml 中的 targets 配置

### 8.2 告警未触发

**问题**: 告警条件满足但未触发

**排查步骤**:
```bash
# 1. 检查告警规则语法
promtool check rules /Users/yunpeng/pi-investment/quantsys-v2/config/prometheus/alert_rules.yml

# 2. 在 Prometheus UI 中手动查询告警表达式
# 访问 http://localhost:9090/graph
# 粘贴告警规则的 expr

# 3. 检查 Prometheus 日志
grep -i "error" /usr/local/var/log/prometheus.log
```

**解决方案**:
- 确保告警规则文件路径正确
- 检查告警表达式语法
- 确认 Alertmanager 配置正确

### 8.3 Grafana 无数据

**问题**: Grafana 面板显示 "No data"

**排查步骤**:
1. 检查 Prometheus 数据源连接状态
2. 在 Grafana Query Inspector 中查看实际查询
3. 在 Prometheus UI 中手动执行相同查询
4. 检查时间范围选择

**解决方案**:
- 确保 Prometheus 数据源配置正确
- 检查查询表达式语法
- 确认指标名称拼写正确

---

## 9. 性能优化

### 9.1 Prometheus 存储优化

```yaml
# prometheus.yml 添加存储配置
storage:
  tsdb:
    retention.time: 30d      # 保留 30 天数据
    retention.size: 10GB     # 最大 10GB
```

### 9.2 抓取频率调优

```yaml
# 根据实际需求调整抓取间隔
scrape_configs:
  - job_name: 'quantsys-v2-datasources'
    scrape_interval: 30s  # 降低到 30 秒（减少负载）
```

### 9.3 指标降采样

```yaml
# 使用 recording rules 预计算常用查询
rule_files:
  - alert_rules.yml
  - recording_rules.yml  # 添加预聚合规则
```

---

## 10. 安全加固

### 10.1 启用认证

```python
# 为 /metrics 端点添加 HTTP Basic Auth
from flask_httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    return username == 'prometheus' and password == 'YOUR_SECRET_PASSWORD'

@metrics_bp.route('/metrics', methods=['GET'])
@auth.login_required
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
```

### 10.2 限制访问 IP

```python
# 仅允许 Prometheus 服务器访问
from flask import request, abort

@metrics_bp.before_request
def limit_remote_addr():
    allowed_ips = ['127.0.0.1', '::1']  # 仅本地访问
    if request.remote_addr not in allowed_ips:
        abort(403)
```

---

## 11. 监控指标参考

| 指标名称 | 类型 | 说明 | 标签 |
|---------|------|------|------|
| `provider_health_score` | Gauge | Provider 健康评分 (0-1) | provider_name, provider_type |
| `provider_circuit_breaker_state` | Gauge | 熔断器状态 (0/1/2) | provider_name, provider_type |
| `provider_request_total` | Counter | 请求总数 | provider_name, provider_type, result |
| `provider_request_duration_seconds` | Histogram | 请求耗时分布 | provider_name, provider_type |
| `provider_failover_total` | Counter | 降级次数 | provider_name, provider_type, reason |
| `cache_hit_total` | Counter | 缓存命中次数 | method |
| `cache_miss_total` | Counter | 缓存未命中次数 | method |
| `cache_size` | Gauge | 缓存条目数 | - |
| `cache_utilization` | Gauge | 缓存利用率 (0-1) | - |
| `kline_backfill_total` | Counter | K线回填次数 | symbol, result |
| `kline_backfill_rows` | Counter | K线回填行数 | symbol |

---

## 12. 总结

监控系统部署完成后，你将获得：

✅ **实时可见性**: Grafana 仪表盘实时展示所有数据源状态  
✅ **主动告警**: Prometheus 自动检测异常并发送告警  
✅ **历史追溯**: 30 天数据保留，支持历史分析  
✅ **性能优化**: 通过指标发现性能瓶颈  

**下一步**:
1. 根据实际业务调整告警阈值
2. 添加更多自定义仪表盘
3. 集成到现有监控系统（如有）

---

**文档版本**: v1.0  
**最后更新**: 2026-09-01
