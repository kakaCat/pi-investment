# t-d65d4c 定义卡片四轴类型系统·测试

> 需求：REQ-260928001915-f978 队列 DAG 真图卡片类型与可视化设计

## 在做什么
定义卡片四轴类型系统·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

运行 `cd docs/requirements/REQ-260928001915-f978 && python3 demo/build-demo.py`，退出码必须为 0，且日志中出现「模块自测全绿」（失败数 0）；产物 demo/dag-card-types-demo.html 必须存在。

## 汇报 1（2026-09-28T05:49:33.578Z，窗口 session-6cbda737-2159-497d-9384-10ef3330279f）

【测试·链执行回填】定义卡片四轴类型系统·测试：测试阶段完成：对有效交付物 docs/requirements/REQ-260928001915-f978/demo/card-types.ts 跑通全部验收命令与模块自测，全部输出全绿（0 失败）

### 完成项

- 测试阶段完成：对有效交付物 docs/requirements/REQ-260928001915-f978/demo/card-types.ts 跑通全部验收命令与模块自测，全部输出全绿（0 失败）
- 父卡验收命令 1 通过：npx tsc demo/card-types.ts --noEmit → EXIT=0；并做负向对照（拷贝副本注入 const __fault: number = "not a number"）→ EXIT=2 + TS2322，证明该命令确实在做真实类型检查而非空跑
- 父卡验收命令 2 通过：grep 'export' demo/card-types.ts | wc -l → 22 行（≥4 达标），EXIT=0
- 一键构建 + 自测通过：python3 docs/requirements/REQ-260928001915-f978/demo/build-demo.py → 「[汇总] 88 通过 / 0 失败」+「模块自测全绿」+ EXIT=0
- 独立复核（不复用 demo 自测）通过：npx tsx 直接 import demo/card-types.ts 断言 16/16 全绿——四轴枚举值逐字相符（Phase 7=implement/test/doc/review/ui/analysis/merge；Side 4=backend/frontend/fullstack/doc；Role 3=parent/child/solo；Status 6=todo/in_progress/integrating/testing/in_review/done，合计 20），PHASE_COLORS 7 色互异、STATUS_BACKGROUND_COLORS 6 色互异、三张中文标签表 7/4/6 齐全、deriveTaskFields 三态判定正确
- 口径确认：被测交付物为 demo/card-types.ts（复核卡 t-730c85 认定的有效交付，逐条对齐 FR-1）；packages/web/dsh-pmboard/src/domain/card-types.ts 属另一需求 REQ-260927182328-6e7d 的越界残留、四轴语义偏离 FR-1，未计入本卡测试对象与证据
- 副作用说明：一键脚本按最新 queue.json 重新生成 demo/dag-card-types-demo.html（磁盘 109514 字节，脚本计数字符 100844；sha256 6f45952dc2573559df8802bd34ae559d2995f5ce2c9401287fac85cd0f493852）；重建幂等（两次 sha256 一致）。结论族阶段不计入 filesChanged

---
