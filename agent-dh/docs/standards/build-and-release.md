---
id: std-build-and-release
title: 构建与发版规范（改了不等于生效）
type: standard
status: living
updated: 2026-09-14
owners: [w-1cee2467]
tags: [standards, build, release]
---

# 构建与发版规范

**这页回答**：改完代码怎么让它真正生效；哪些"看起来部署了"其实没有。

## 结论先行

1. **`pnpm build` 不是部署，`pnpm install` 更不是**——2026-09-11 的事故正是这么来的。
2. profile 的 `@pi-investment/*` 依赖**必须是符号链接**；`pnpm install` 会换成**硬链接副本**，
   任何一次写文件（临时文件 + rename）都会换 inode → **静默停在旧版本，且不报错**。
   更阴的是**部分过期**：没被编辑过的文件仍是硬链接、看着"是同步的"。
3. 发版唯一正确入口：`agent-dh/scripts/restart-with-build.sh`（= relink → build → kickstart）。
4. :13080 由 **launchd 托管**：`kill` 会被 KeepAlive 秒级拉起，紧接着手工 `./start.sh` 必然
   `EADDRINUSE`。重启只能 `launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh`。
5. **构建后必须校验产物**：文件存在 + 关键符号 grep 命中。构建失败会**清空 dist**，
   等于让插件消失（历史事故：tsdown 因 dts 报错失败，构建前 dist 已被清空）。

## 加载方式（决定"要不要 build"）

- `main` 指向 **`./dist/index.mjs`** 的包：**改源码必须 build 才生效**——
  competition / data-manager / evolution / factor / genome / intelligence / investment /
  investment-agent-loop / lifecycle / market / memory / notification / risk / scheduler / strategy /
  trading / agent-dh-client；
- `main` 指向 **`./src/...`** 的包：**tsx 直载，改完重启即生效**——
  agent-os-manager / core-tool / evolver / learning / quantsys-v2-manager / solve-kit，
  以及全部**页面插件**（bulletin / dsh-pmboard / execution / genome(pages) / holdings / page-kit）。
  ⚠️ 页面插件的 **client 半**另有打包产物 `lib/client.js`（见插件与页面插件规范）。
- 判断某个包走 dist 还是 src：`python3 -c "import json;print(json.load(open('包/package.json'))['main'])"`。

## 发版流程（照抄即可）

```bash
# 0) 体检：有漂移则退出码 1
python3 agent-dh/scripts/relink-profile.py --check

# 1) 把副本换回符号链接（旧的备份到 .deploy-backup/<时间戳>/）
python3 agent-dh/scripts/relink-profile.py

# 2) 构建（dist 包）
cd agent-dh && pnpm build

# 3) 校验产物（别只看退出码）
ls packages/<pkg>/dist/index.mjs && grep -c '<新增的关键符号>' packages/<pkg>/dist/index.mjs

# 4) 重启（launchd 托管）
launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh
```

## 依据

- 2026-09-11：`pnpm install` 造成硬链接副本 → 部署静默停在旧版本（写成 agent-dh/CLAUDE.md 的铁律）；
- "改了源码却以为已生效"事故：新增工具在 dist 里出现 0 次 → 工具从未注册成功；
- 构建失败清空 dist 事故（intelligence 的 dts 推断类型报错）。
- **2026-09-14：体检对象错了、且把空集当通过。** 体检脚本的 profile 名写死 `investment`，而实跑的是 `agent-dh`（`ps eww` 无 `DSH_PROFILE`）→ **一直在体检那个休眠的 profile**；改对之后又暴露出「0 个安装条目」这种空检查集。规矩：**体检前先确认对象（profile / 端口 / 目录）是对的，且检查集非空——空集不是通过。** 复盘见 [.dsh-home 并入 .dsh-data](../work-logs/2026-09/dsh-home-data-merge.md)。

## 自检清单

- [ ] 我改的包走 dist 还是 src？走 dist 我 build 了吗？
- [ ] build 之后 `dist` 里的关键符号 grep 得到吗？退出码是 0 就够了吗（不够）？
- [ ] 这次要不要重启？重启方式是不是 kickstart（不是 kill）？
- [ ] 重启会影响哪些并行窗口？我有没有先问过？
- [ ] 我这次体检/校验的**对象**对吗（profile 名 / 端口 / 目录）？检查集是空的吗？（**空集 ≠ 通过**）

## 相关页面

- [工具开发规范](tool-development.md)
- [测试与门禁规范](testing.md)
- [某些包为何没有 dist](../architecture/WHY-NO-DIST.md)
- [自修复重启行为](../architecture/self-restart-behavior.md)