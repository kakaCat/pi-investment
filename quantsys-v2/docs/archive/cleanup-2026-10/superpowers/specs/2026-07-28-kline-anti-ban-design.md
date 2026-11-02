# K线数据源抗封禁设计：baostock 接入 + 请求限速 + 封禁告警

日期：2026-07-28
状态：已确认
范围：quantsys-v2

## 背景

2026-07-28 发现 eastmoney（akshare）与 tencent（ifzq.gtimg.cn）均封禁本机 IP，K线网络更新链路整体不可用。tencent 被封的直接诱因很可能是当日回填时 5 分钟 1348 次连续请求触发 WAF。

根因三层：
1. **无速率控制**：kline_update_job 对单源全速连发请求
2. **源体系单一**：akshare 与 tencent 都是网页 API，易被封；baostock 是独立 TCP 长连接服务，体系不同
3. **故障静默**：源被封时 job 全部标记"跳过"，两周无人发现

## 设计

### 1. BaostockKlineProvider（新 K线 provider）

- 文件：`adapters/outbound/datasources/providers/kline/baostock.py`
- 实现 `KlineProvider` 接口（`get_klines(symbol, period, start_date, end_date)`，仅支持 daily）
- 代码格式转换：`300001 → sz.300001`、`600519 → sh.600519`、`399006 → sz.399006`
- 复权：`adjustflag='2'`（前复权，与 tencent qfq 对齐）
- 字段映射：baostock `volume`（股，无需归一）、`amount`（元）、`turn`（换手率%）
- 会话管理：模块级 lazy `bs.login()`，进程内复用；`query_history_k_data_plus` 返回迭代器逐行组装 KlineData
- `last_error` 契约与 tencent provider 一致（供 manager 聚合失败原因）

### 2. KlineData 契约补 turnover 字段

`turnover_rate: float = 0.0`（%，默认 0 向后兼容）。baostock 填真实值，tencent/akshare 保持 0.0（无原始数据）。
kline_update_job 把硬编码的 `0.0  # turnover_rate` 改为 `float(k.turnover_rate)`。

### 3. Manager fallback 链调整

```
database → baostock → tencent → akshare
```

baostock 为网络首选（独立体系、字段最全）。现有测试 `test_manager_kline_chain_has_tencent_before_akshare` 不受影响。

### 4. kline_update_job 限速

- 每只股票之间 `time.sleep(random.uniform(0.3, 0.8))`
- params 支持 `interval_seconds=(low, high)` 覆盖（默认 (0.3, 0.8)），`interval_seconds=0` 关闭（测试/小批量用）

### 5. 封禁检测与告警

job 统计失败率：处理 ≥20 只且失败率 >50% 时：
- `logger.critical` 记录"数据源疑似被封/故障"
- 结果 dict 增加 `'provider_health': 'degraded'`（正常为 `'ok'`）
- 区分 skipped（股票无数据）与 failed（源异常）：manager 返回 `success=False` 计入 failed，而非现在的全部 skipped

### 6. 回填

baostock 接入验证后，用其重跑 2026-07-13 以来窗口（真实数据校正 volume 单位 + amount + turnover，替代 07-28 的 SQL 估算）。

## 明确不做（YAGNI）

- 国内 VPS relay 中转（P2 最后手段，暂不需要）
- sina K线 provider（第二备选，baostock 不够用再加）
- 每日更新范围分级（持仓+池子 ~300 只）：等限速效果验证后再评估
- 飞书告警：webhook 未配置，先 critical 日志 + 结果字段

## 验收标准

1. 新增测试全绿（provider 解析/单位/链顺序/限速调用/降级检测）
2. `venv/bin/python -c "from adapters.outbound.datasources.manager import DataProviderManager; m=DataProviderManager(); r=m.get_klines('300750','daily','2026-07-20','2026-07-28'); print(r['success'], r.get('source'), len(r.get('data') or []))"` 返回 success=True source=baostock
3. baostock 回填后 `SELECT count(*) FROM quant.daily_klines WHERE trade_date>='2026-07-13' AND (amount=0 OR turnover_rate=0)` 显著下降（turnover 指数/部分股票无原始值除外）
4. `_get_stock_pool` 查询结果 ≥ 400 只（与 07-28 SQL 回填后相当或更好）
