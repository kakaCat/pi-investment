# t-0bf4ae 实现三层覆盖度自动计算

> 需求：REQ-260926140539-457b RTM YAML 追溯基础设施 - Dive 模式自动化的数据底座

## 在做什么
实现三层覆盖度自动计算

## 解决什么问题
创建 src/rtm/coverage-calculator.ts，实现 calculateDesignCoverage / calculateImplementationCoverage / calculateTestingCoverage，统计映射中有值项占比。

## 得到什么结果
运行 `pnpm test rtm-coverage.test.ts` 通过；3 FR 中 2 有设计返回 rate 0.67 且 uncovered=["FR-3"]；100% 覆盖返回 rate=1.0 且 uncovered=[]

---
## 汇报 1（2026-09-26T10:32:48.553Z，窗口 session-c5ea210f-afc3-4735-a4d1-f9058b378363）

这一步做完，系统能自己报出「哪里还没覆盖」：设计覆盖度 67% 就说缺 FR-3，不会只给一个百分比让人猜。

### 完成项

- 三层覆盖度计算（设计/实施/测试）
- 门禁校验器：设计/拆分要求 100%、验收要求 ≥80%，不过时点名缺口
- 3 FR 覆盖 2 → 67%、5 任务覆盖 2 → 40% 等数字有单测钉住

### 改动文件

- `packages/tools/reqboard/src/rtm/coverage-calculator.ts`
- `packages/tools/reqboard/src/rtm/validator.ts`

---
