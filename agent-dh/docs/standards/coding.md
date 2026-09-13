---
id: std-coding
title: 编码与协作规范（命名 / 放置 / worktree / 注释写为什么）
type: standard
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [standards, coding, collab]
---

# 编码与协作规范

**这页回答**：写代码与文档时的命名、放置、协作约定；违反会造成什么。

## 结论先行

1. **多会话并行**：每个工作线在**独立 worktree** 开发（`git worktree add .claude/worktrees/<name> -b feat/<name>`），
   合回 main 再推。**不在共享主工作区做 feature 提交**。
2. **脏工作区是停手信号**：`git status` 出现不属于自己的改动 → 只 add 自己任务的文件；
   **禁止** `git checkout <ref> -- .` / `git restore --source` 这类批量覆盖。
3. **文档放置**：根目录只留 `README.md` + `CLAUDE.md`；其余按决策树进 `docs/`
   （决策→adr、提案→rfcs、架构→architecture、指南→guides、**规范→standards**、工作记录→work-logs）；
   子项目放各自 `docs/`；命名 kebab-case，ADR/RFC 用 `NNN-title.md`。
4. **注释写"为什么"**：写事故、取舍与反直觉之处（"这里必须 X，否则 2026-09-11 那次会重现"）；
   不写"是什么"（代码已经说了）。
5. **提交信息**：`type(scope): 一句话结论` + 正文写证据（数字、命令、文件），署名窗口编码。

## 关键机制

- TypeScript：ESM、`type` 字段、`strict` 视包而定；跨包类型**显式注解**（`: any` 也好过
  不可移植的推断类型——曾因 dts 推断内联 .pnpm 路径导致构建失败）。
- 包内组织：`src/index.ts` 注册入口；宿主逻辑放 `src/host/`；客户端逻辑放 `src/client/`；
  测试放 `tests/`（`*.test.ts`）。
- 错误处理：抛 `Object.assign(new Error(msg), { code })`；**不要**吞异常后返回默认值。

## 依据

- 2026-09-11 多实例事故与 worktree 规则写入根 CLAUDE.md；
- 文档混乱整治（`DOCUMENT-MANAGEMENT-PLAN.md`：根目录 33 个 MD → 分类归档）；
- 构建失败事故：static Config 推断类型引用 .pnpm 内部路径 → 加显式注解修好。

## 自检清单

- [ ] 我在 worktree 里做的吗？分支名与任务对得上吗？
- [ ] `git status` 里有没有别人的改动被我 add？
- [ ] 新文件放对目录了吗（走决策树）？命名是 kebab-case 吗？
- [ ] 注释解释了"为什么"吗？三个月后的我能看懂事故背景吗？

## 相关页面

- [测试与门禁规范](testing.md)
- [构建与发版规范](build-and-release.md)
- [留痕与文档规范](audit-and-docs.md)
- [文档规范与 Wiki 约定](../../../docs/DOCUMENT-MANAGEMENT-PLAN.md)
