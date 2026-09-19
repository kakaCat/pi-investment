# superpowers vendor 原文 · 来源与许可（REQ-422af1 t7）

本目录下的 14 份 `<skill>/SKILL.md` 是 **obra/superpowers** 的原文（逐字节落盘、不改写），
用作六节点 heavy 档的"主 skill 原文"。它们**不是**运行时读盘对象：构建期由
`scripts/inline-prompt-fragments.mjs` 把 `fragments/<stage>/heavy.md`（其逐字节镜像）内联进
`src/domain/prompt/generated/fragments.ts`，运行时只读内存常量。

## 1. 来源

| 项 | 值 |
|----|----|
| 仓库 | https://github.com/obra/superpowers.git |
| 引用 | `origin/main` |
| commit | `b36e0829c6d0140e93cfef2ca599b1b07d4a7797` |
| tag | `v6.3.0` |
| 许可 | MIT（Copyright (c) 2025 Jesse Vincent） |
| 抓取时点 | 2026-09-17 22:42:44 CST |
| 抓取方式 | `cd /Users/yunpeng/.claude/skills/superpowers && git show origin/main:skills/<name>/SKILL.md`（逐字节重定向落盘，无任何改写） |
| 核对 | `git log -1 origin/main` = b36e0829c6d0140e93cfef2ca599b1b07d4a7797；`git tag --list v6.3.0` = v6.3.0；`git remote -v` = https://github.com/obra/superpowers.git |

## 2. 落盘清单（14 份 = 仓库 skills/ 全量）

| skill | 字节数 | 行数 | 本仓角色 |
|-------|-------:|-----:|----------|
| brainstorming | 15456 | 250 | **heavy 主 skill**：brainstorming（整份 vendor，逐字一致断言对象） |
| writing-plans | 7053 | 171 | **heavy 主 skill**：design |
| executing-plans | 2305 | 64 | **heavy 主 skill**：implementing |
| verification-before-completion | 3646 | 120 | **heavy 主 skill**：accepting |
| finishing-a-development-branch | 7781 | 225 | **heavy 主 skill**：archived |
| test-driven-development | 9015 | 320 | 按需片段（implementing，同一次注入最多挂一个） |
| subagent-driven-development | 32339 | 568 | 按需片段（implementing） |
| using-git-worktrees | 6813 | 167 | 按需片段（implementing） |
| dispatching-parallel-agents | 6078 | 167 | 按需片段（implementing） |
| requesting-code-review | 2956 | 95 | 按需片段（accepting） |
| receiving-code-review | 6203 | 205 | 按需片段（accepting） |
| systematic-debugging | 9465 | 283 | 横切（排障场景） |
| writing-skills | 26360 | 679 | 横切（写提示词本身） |
| using-superpowers | 3108 | 63 | 横切（先分类宣布的元纪律） |

> **decomposing 无对应**：14 份里没有"拆分/任务 DAG/卡质量"的 skill（对照结论 §4.5 口径例外），
> 其 heavy 为自写完整档，不做"与 vendor 原文逐字一致"断言。
>
> **按需片段（附属 skill）**本阶段只落盘原文、不注册为分片：注册即需被路由命中（否则违反
> 门禁 4"无孤岛"）。待其在节点内子步骤上被 include 时再注册。

## 3. 逐字一致门禁（防漂移）

`fragments/<stage>/heavy.md` 是上表 5 份**主 skill 原文的镜像**，必须与 vendor 原文逐字节一致：

- 构建/同步门禁：`node scripts/check-prompt-fragments.mjs`（不一致即 exit 1）；
- 验收测试：`tests/prompt-tiers.test.ts`（brainstorming/heavy 与 vendor 原文逐字一致，byte-level）。

镜像关系（唯一映射见 `scripts/inline-prompt-fragments.mjs` 的 `VENDOR_MAIN_SKILLS`）：
brainstorming→brainstorming；design→writing-plans；implementing→executing-plans；
accepting→verification-before-completion；archived→finishing-a-development-branch。

## 4. 许可原文（MIT）

```
MIT License

Copyright (c) 2025 Jesse Vincent

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
