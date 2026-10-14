# t-b8daeb 通知层契约落地：_format_elapsed + _summarize_result 支持顶层 summary·测试

> 需求：REQ-261005210015-1603 修复每日任务完成通知误导（耗时 0.0 分钟 / computed 语义 / 全 NULL 仍报 ✅）

## 在做什么
通知层契约落地：_format_elapsed + _summarize_result 支持顶层 summary·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-05T13:16:02.271Z，窗口 session-2bee6968-97b4-45c8-af2d-c3b953e9ff08）

测试段：边界断言与既有每日任务回归全绿，无真实外发

### 完成项

- 回归全过：pytest tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py -q 合计 40 passed, 1 skipped
- 边界断言五组逐条通过：1.21→1.2 秒、59.96→60.0 秒、60.0→1.0 分钟、125.0→2.1 分钟、-1→0.0 秒
- 旧行为对照通过：evening_pipeline 形态渲染仍为 kline_sync[updated=3, status=success]
- notify-guard 会话末计数 intercepted=0 egress=0，无真实外发
- 正式 12 条通知层用例归父卡 t-cef289 创作，本卡只做本阶段验证

### 下一步

父卡 t-cda13d 收尾；正式用例由 t-cef289 承载

---
