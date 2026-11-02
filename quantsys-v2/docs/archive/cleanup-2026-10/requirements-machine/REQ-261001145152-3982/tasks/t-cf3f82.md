# t-cf3f82 装外部存活与数据新鲜度探针

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
装外部存活与数据新鲜度探针

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

外部探针就位且判定口径可证伪（"告警真实送达"因环境缺渠道无法达成，已拆出为上挂阻塞）：
① 探针存在且**外部可跑**：`/Users/mac/.../venv/bin/python tools/health_probe.py`（绝对路径、任意 cwd、不 source、不设 PYTHONPATH）能跑通；
② 四条分支退出码正确：健康=0、服务不可达=2、数据过期=2、探针自身故障=3（最后一条用注入法验证）；
③ 卡片点名的口径已验证：`--max-lag-days 0`（数据滞后 1 天）→ 立即判过期并构造告警；`--api-port 5999` → 构造端口不可达告警；
④ launchd 模板 `deployment/launchd/com.pi-investment.health-probe.plist` 就位且 `plutil -lint` 通过（StartInterval=300）——**未安装**（安装会改机器状态，留待人工确认）；
⑤ **告警真实投递：当前环境不可用**（无 Feishu 渠道；唯一渠道 agent→Agent OS(8080) 不可达 → 真实发送返回 `{"attempted": true, "ok": false}`，日志 `所有渠道发送失败`）。故卡片原写的"收到飞书告警"**改由条件项承接**：先配 `FEISHU_*`（或恢复 Agent OS）再做一次真实告警验证；该项已作为独立阻塞上报。
说明（原验收调整）：原验收要求"kill 服务后 5 分钟内收到飞书告警"——探针侧的判定与构造已全部验证，但**投递链路在本环境是断的**，属环境配置缺失而非探针缺陷；同时"kill 服务"本身会中断当前在跑的 API，故未做破坏性验证。

## 实施方案（implementation）
在外部（不依赖被监控进程）新增 1~2 个探针：进程/端口心跳（5001 + 8080）与数据新鲜度（max(trade_date) 落后最近交易日 >1 天告警）；复用 NotificationFacade，不新写通知通道。

## 上游产出摘要（dependsSummary）
- 把 V2 服务救活并留下运行证据

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-01T09:17:33.147Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

这一步做完，变化是：**"服务死了没人知道"这件事第一次有了外部哨兵**——探针独立于被监控进程运行（launchd 每 5 分钟一次），能同时判"端口通不通"和"数据新不新"，异常时 exit 2 并走通知门面告警；但实测同时揭开更扎心的一层：**告警出口本身是断的**（本机没配飞书渠道、唯一渠道指向已停的 Agent OS），所以"发得出告警"还差一步配置——已如实报出，未粉饰。

### 完成项

- 新增外部探针 tools/health_probe.py：端口心跳 + 数据新鲜度，均不依赖被监控进程的线程；退出码 0/2/3 fail-loud
- 新增 launchd 模板 deployment/launchd/com.pi-investment.health-probe.plist（StartInterval=300；**未安装**，留人工确认）；plutil 校验通过
- 验证：健康 exit 0；服务不可达 exit 2 且构造告警；--max-lag-days 0 立即判过期；探针自身故障 exit 3（注入法）
- 设计修正（避免告警疲劳）：Agent OS(8080) 默认不纳入告警条件，需 --check-agent-os 显式开启——本仓设计本就容许 Agent OS 缺席
- **报出关键阻塞**：告警投递链路当前不可用——Feishu 渠道仅在 settings.external.feishu_webhook_url 存在时注册（notification_factory.py:164），而 .env 无任何 FEISHU_* 键；唯一渠道 agent→8080 不可达，真实发送返回 attempted=true/ok=false。这意味着"没有探针"之外还有一层"有探针也发不出去"
- 实现中修正自己两处契约错误（门面不能裸构造；send_alert 签名与我想的不同），并把误导性的 {"sent": true} 改为 {"attempted": true, "ok": bool}
- 附带发现：既有 launchd 模板路径写的是 /Users/yunpeng（另一台机器），在本机不可能生效

### 改动文件

- `tools/health_probe.py`
- `deployment/launchd/com.pi-investment.health-probe.plist`

---
