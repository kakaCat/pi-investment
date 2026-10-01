# t-d8f0c3 git 产物出库（含 ignore 失效项）·研发

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
git 产物出库（含 ignore 失效项）·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
改动已落盘，相关测试或命令跑通并附输出摘要

---
## 汇报 1（2026-10-01T07:48:59.417Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

研发段：把 111 个"不该进仓库却进来了"的运行时产物从版本控制里请出去（磁盘文件一个没删），根目录的 ERROR_TRACKING.md 也归档到工作日志目录；同时把"脚本到底该不该入库"这个自相矛盾点裁定清楚并写进 .gitignore 注释——中途我第一版选错了方向，实测发现会让 60+ 个一次性脚本涌进仓库，已回退改正。

### 完成项

- git rm --cached 出库 98 个 .pyc/.pkl/.log（90 个 scripts/*/__pycache__ 下的 .pyc + 8 个 .pi-invest/ml/models 下的 .pkl）；工作区文件全部保留（抽查确认）
- git rm --cached 出库 .pi-invest/ 全部 19 个（.gitignore 早已声明该目录应忽略，属规则失效的已入库产物）
- git rm --cached 出库 test_reports/（1）与 data/groups.json（1）
- git mv ERROR_TRACKING.md → docs/work-logs/2026-09/（保留 git 历史，符合根目录只留 README/CLAUDE 的规范）
- 裁定 ③：**保持 scripts/ 忽略规则**（脚本属一次性资产）——并附证据与理由写入 .gitignore 注释
- 过程修正（如实记录）：第一次我选择“删掉 scripts/ 忽略规则”并已落盘，随即实测发现 60+ 个从未入库的一次性脚本立刻涌成 untracked（git status 由干净变 84 条）——方向相反，已回退并改为“保持忽略 + 80 个历史脚本不追溯删除”
- 验收：产物计数 0、.pi-invest 跟踪 0、test_reports/data 跟踪 0、ERROR_TRACKING.md 已归档、被出库文件磁盘副本仍在、git status 噪声回落至 3 条（均为未入库新文档）

### 改动文件

- `.gitignore`
- `ERROR_TRACKING.md → docs/work-logs/2026-09/ERROR_TRACKING.md`

---
