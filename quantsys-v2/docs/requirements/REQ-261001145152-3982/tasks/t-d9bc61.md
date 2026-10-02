# t-d9bc61 git 产物出库（含 ignore 失效项）·测试

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
git 产物出库（含 ignore 失效项）·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
目标命令输出全绿（贴命令与结果摘要）

---
## 汇报 1（2026-10-01T07:52:10.897Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

测试段：四条验收命令全部通过（产物计数归零、忽略规则确实生效、111 个文件一个没丢）；顺带复测发现依赖补齐后测试收集从"5264 条 + 119 个模块导不进来"变成"6427 条 + 只剩 1 个"，而剩下那个是又一处"模块已删、测试还在 import"的悬空引用。

### 完成项

- 验收命令全绿：`git ls-files | grep -cE "\.(pyc|pkl|log)$"` = 0；`git ls-files .pi-invest` = 0
- 忽略规则验证：`git check-ignore -v scripts/analyze_factor_ic.py` → 命中 `.gitignore:38:scripts/`（规则生效；已跟踪的 80 个历史脚本不受影响，因跟踪文件不受 ignore 约束）
- 工作区完整性：111 个出库文件逐个确认仍在磁盘（真丢失 0）
- 额外收益（顺带复测）：补装 3 个阻塞依赖后，pytest 收集从 **5264 tests + 119 errors** 改善为 **6427 tests + 1 error**
- 剩余 1 个 collection error 根因：tests/migration/test_watch_backlog_convergence.py → ModuleNotFoundError: No module named 'scripts.migrate_watch_backlog'（目标模块已删、测试仍在 import，属审计报告 §2.1 第 7 行『悬空 import』类，归 t-3f2444 处置）

---
