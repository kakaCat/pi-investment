# t-c19f4f 判据文档与码表同源（修陈旧文案 + 契约判据表）·研发

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
判据文档与码表同源（修陈旧文案 + 契约判据表）·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run tests/` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-07T11:04:04.077Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

t12 研发段完成：判据表落档并与码表机械对拍，陈旧文案清零。

### 完成项

- 契约文档 §6 换成 15 行判据表（与码表同源），原「已知瑕疵」降为 §7
- 设计 data-model.md 与契约文档两份码表都被对拍测试覆盖（代码 + 两份文档三方同源）
- 新增 tests/services/test_watch_contract_parity.py 4 passed：含「正则必须容忍数字」显式断言（RULE_LEVEL_L2）
- 陈旧文案清零：application/domain/docs/architecture 下 grep 0 命中
- 修了两处自己造出的字面串（服务 docstring 的引文 + models.py 历史字段注释），如实保留来龙去脉

### 改动文件

- `docs/architecture/watch-notification-contract.md`
- `application/services/opportunity_to_watch_rule_service.py`
- `domain/watch/models.py`
- `tests/services/test_watch_contract_parity.py`

### 下一步

复核段：判据表与设计顺序表交叉核对。

---
