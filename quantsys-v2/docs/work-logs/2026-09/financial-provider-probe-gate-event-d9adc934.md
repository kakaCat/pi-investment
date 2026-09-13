# 错误事件处置：003021 财报抓取失败（All providers failed）· d9adc934

- **事件 ID**：`d9adc934-4a26-4f3d-a1f5-091d0454f129`（source=v2，error，频次 263）
- **处置窗口**：w-32314d00

## 1. 事件读数纠正：不是"003021 失败 263 次"

```console
$ grep -c "财报抓取失败" logs/launchd-stdout.log          → 263
$ grep -o "[0-9]\{6\}: 财报抓取失败" ... | sort -u | wc -l → 186   # 186 只不同标的
$ grep -c "003021: 财报抓取失败"                           → 1      # 该标的只失败过 1 次
```

采集器按**数字归一化**的指纹聚合，`msg` 取了首行文本，于是卡片读起来像"003021 连续失败 263 次"，
实际是 **186 只标的各失败若干次**、覆盖全宇宙（≈367 只）的一半以上 → 指向**源整体不可用**，不是单只问题。

## 2. 根因：环境（源链整体抖动）+ 代码缺口（无探活门控、逐只刷屏）

- **环境**：2026-09-12 20:03 ~ 09-13 00:28 期间 sina_web / eastmoney / akshare-financial 全线取不到数；
  同期日志可见 akshare 东财接口 `'NoneType' object is not subscriptable`、sina 返回非 JSON 等源侧异常。
- **代码缺口**：`financial_statement_update_job.execute` 无条件遍历整个扫描宇宙，逐只重试；
  源全挂时 367 次请求全部无效，还产生 263 条失败日志（被采集器聚成一条"263 次"的事件），
  并可能加重源侧限流/WAF。

## 3. 落地动作

1. **探活门控**（对齐 kline 任务 `_probe_kline_sources` 的 2026-09-02 WAF 封禁教训）：
   开跑前探活参考标的 `600519` / `000001`，任一能取到报表即放行；全部失败 → **快速失败**
   （返回 `success=false` + `probe_failed=true`，任务在台账里可见地失败），不再对全宇宙做无效请求。
2. **失败日志聚合**：逐只失败不再各打一行，改为循环结束后**一条汇总**（失败数量 + 样例标的 + 首个失败原因）。
3. 重启 v2-api 使改动生效。

## 4. 验证

```console
# ① 源当前健康（含出问题的 003021）——说明该时段属瞬时不可用、已自愈
003021 OK  source=akshare-financial income=32  balance=31
600519 OK  source=akshare-financial income=103 balance=103
000001 OK  / 688322 OK / 000983 OK

# ② 健康路径不被门控误拦
$ python -m infrastructure.jobs.financial_statement_update_job --symbols 003021 600519 --periods 2
{'success': True, 'universe': 2, 'updated': 2, 'rows': 135, 'balance_rows': 134, 'failed': 0}

# ③ 回归测试
$ pytest tests/test_financial_probe_gate.py -q      → 4 passed
     （源全挂 → 只探活参考标的、业务标的零调用；首个探活成功即收工；
       失败日志有且仅有一条聚合、含 4/4 与样例 003021）
```

## 5. 结论 / 遗留

- **事件性质**：环境抖动为主因，已被探活门控 + 聚合日志收敛；健康路径回执证明改动不误伤正常取数。
- 这类"源整体不可用"的时段无需人工补数：下一次例行（周六 20:00 宿主任务）与逾期自动补救
  （`financial_timeliness_check_job._maybe_auto_remediate`）都会重跑，且数据契约/时效性巡检会兜底报警。