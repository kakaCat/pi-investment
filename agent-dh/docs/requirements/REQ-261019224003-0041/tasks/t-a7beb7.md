# t-a7beb7 依赖声明与构建/映射/分层清单对齐·研发

> 需求：REQ-261019224003-0041 改用dsh-workprocess的内容

## 在做什么
依赖声明与构建/映射/分层清单对齐·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
改动已落盘，相关测试或命令跑通并附输出摘要

---
## 汇报 1（2026-10-20T00:34:17.815Z，窗口 session-66f19830-f3c9-42a7-a3cc-3791a19cd16f）

依赖/构建/映射/分层四项对齐全部核验落绿（boundary 20/20、软链×4、workprocess 348/348 测试）；构建红色被证实是 t6 范围的 goal 旧名引用所致（对照实验定位到 06864df1），经你裁定后 build 判定后移、本卡收口。另：误清的 pm/dist 已用 b7ee7c21 产物恢复。

### 完成项

- 核验 e3e90150 已落盘的四处对齐（pm/package.json 四包依赖、tsdown 内联正则、tsconfig/vitest.base 四包映射、boundary 清单放行）
- boundary:check 退出码 0（20/20 包）
- pm/node_modules 四条 workprocess 软链在位
- workprocess 四包测试 348/348 通过
- 构建红色隔离归因：stash + b7ee7c21 worktree 对照实验，证实破坏源自 06864df1 的 goal 退役（16 文件旧名引用），与本卡改动无关
- 恢复被构建 clean 清空的 pm/dist（从 b7ee7c21 产物），防止宿主重启加载失败
- 按用户裁定方案A 修订本卡验收口径：build/install 判定后移至 t6 后由 t7 兜底

### 下一步

推进联调/复核/测试子卡链；t-af00f4（goal 旧名收尾）完成后需重跑 pnpm install + build grep 判定（t-52f01f 兜底）

---
