# t-e8a5e3 让异常检测真的运行，并输出可区分的三态·测试

> 需求：REQ-261006133733-1fdf 异常值检测静默失效：成交量段迭代错对象（每只必抛错、被 except 吞成无异常）

## 在做什么
让异常检测真的运行，并输出可区分的三态·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-06T05:44:24.174Z，窗口 session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6）

测试阶段完成：数据质量链 37 passed / 1 skipped，三态探针与静态均按设计口径通过。

### 完成项

- ① 既有回归（数据质量链）：tests/test_data_quality_job_guardrails.py + test_service_factory_p2.py + test_anomaly_detection_stage.py → 37 passed, 1 skipped
- ② 三态探针复跑：detect_anomalies('600519.SH') → ok=True、has_anomalies=True、error=None、total_anomalies=1
- ③ 静态复跑：data_validator 内 has_anomalies 无代码级真值判断（命中 2 行均为 docstring 正文）
- ④ 新增用例文件由 t3 承载（tests/test_data_validator_anomaly_detection.py）——本卡只复跑既有回归与探针
- ⑤ 基线对照：改前失败数 0 → 改后 0（不高于基线）
- ⑥ 模板不符：本卡 acceptance 的 pnpm test / npx tsc 属 JS 栈模板，本仓无 package.json，改用 pytest 等价口径

### 下一步

父卡 t1 收尾；随后 t2 子卡链与 t3 用例文件。

---
