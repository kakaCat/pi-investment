# t-ba8cc4 假绿灯结构门禁

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
假绿灯结构门禁

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
venv/bin/python -m pytest -q 下，故意新增一个 def test_x(): return True 会让该用例红；venv/bin/python -m pytest tests/test_scheduled_jobs_account_value.py -q 全过且其 Fake 方法与真实仓储签名一致（断言在位）。

## 实施方案（implementation）
改 pytest.ini 把 PytestReturnNotNoneWarning 升级为错误（结构上杜绝「用例体 return True/False、pytest 报 passed」）；改 tests/test_scheduled_jobs_account_value.py：Fake 只提供真实仓储存在的方法，并补一条「Fake 与真实仓储签名一致」的断言（当前 Fake 提供 get_trades_by_date/count_rebalances，真实仓储没有，掩盖了 AttributeError）。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-04T08:28:58.079Z，窗口 session-8eb5b6f2-0d2a-44d3-bfca-878578124cec）

主卡：假绿灯有了两种门禁——用例返回值门禁与假仓库幽灵方法门禁。

### 完成项

- 主卡目标达成：用例体里 return 值这种假绿灯从「靠人自觉」变成「新增即红」
- 落点按实测改写：原计划的一行配置会误伤 37 处无关测试，改为基线门禁（只许降不许升），并写明基线归零后才开严格开关
- 顺手把第二种假绿灯（假仓库比真实实现更宽松）也钉住：幽灵方法被枚举断言，且不许新增
- 卡内 9 passed；工具退出码 0（无新增）

### 改动文件

- `tools/check_fake_green_tests.py`
- `tests/test_fake_green_gate.py`
- `tests/test_scheduled_jobs_account_value.py`

---
