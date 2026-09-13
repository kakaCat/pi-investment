# baostock 登录零重试导致上游抖动放大（看板事件 79aaf17d）

- 时间：2026-09-13｜窗口：w-32314d00（投资脑 investor）
- 事件：`baostock 登录失败: 网络接收错误。` 累计 37 次（原始日志 93 条），09-10 22:02 ~ 09-12 01:21

## 1. 现象与放大效应

夜间批量回填窗口内，baostock 服务端偶发抖动 → 登录返回 `error_msg='网络接收错误。'`。
`_ensure_login` 对该类**瞬时**错误零重试：一次 return None，调用方立即把该标的判失败。
于是**一次上游抖动被放大成 93 条同类日志、去重后 37 次错误事件**——错误台账被噪声占满。

## 2. 根因分层

| 层 | 内容 | 归属 |
|----|------|------|
| 外部 | baostock 夜间批量窗口瞬时网络抖动 | 外部依赖 |
| 代码 | 登录对可重试错误无退避重试；失败即 ERROR 直写日志 | 代码缺陷（本轮修） |

## 3. 修复

`BaostockKlineProvider._ensure_login` 增加有限重试：

- 可重试判定：`_LOGIN_RETRYABLE_MARKERS = _SESSION_ERROR_MARKERS + (超时/连接类)`，
  与 `_SESSION_ERROR_MARKERS`（决定是否重置会话重登）**分开**，语义不混用；
- 最多 3 次，退避 0.5s / 1.5s；
- 中间尝试打 WARNING，**仅最终失败打 ERROR**（一次抖动不再刷满台账）；
- 永久错误（如账户不存在）仍立即返回，不白等。

## 4. 验证证据

1. 新增单测 `tests/adapters/test_baostock_login_retry.py` —— **3 passed**：
   可重试→第 2 次成功 / 永久错不重试 / 耗尽时只打 1 条 ERROR；
2. baostock 全组（login_retry + kline_relogin + provider + date_normalization）—— **19 passed**；
3. 活体：真实登录成功（baostock 自身打印 login success!），取回 `000908` 日线 **13 条**
   （2026-08-26 ~ 2026-09-11，末条 6.24）；
4. 重启 v2：启动 **14:48:17 > 文件 mtime 14:47:47**，`/health` ok；
   重启后新增日志中「baostock 登录失败」**0 次**（全量日志末次出现 09-12 01:21）。

## 5. 边界

- 重试只能吸收**瞬时**抖动；若 baostock 长时间不可用，仍会失败（但每次只留 1 条 ERROR，
  且降级链会切到下一数据源，不影响主链路）。
- 该 provider 是抗网页 WAF 的独立 TCP 源，可靠性对回填链路有意义，故按「可恢复」处理而非直接弃用。
