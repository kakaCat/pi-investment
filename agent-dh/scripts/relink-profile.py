#!/usr/bin/env python3
"""把 DSH profile 里 @pi-investment/* 的依赖换成/校验为指向仓库源码的符号链接。

## 为什么需要这个脚本

profile 的 package.json 用 `file:` 或 `link:` 引用 agent-dh 的插件包。pnpm 对 `file:` 依赖
做的是**硬链接**：硬链接共享 inode，所以"当时"确实是实时同步的 —— 但这只在**没人替换过该文件**
时成立。任何一次 Write/Edit（写临时文件再 rename）都会换掉 inode、**断链**，于是 profile
那边静默停在旧版本，且没有任何提示。

2026-09-11 就是这么踩的：profile 冻结在当天 02:23 的 `pnpm install`，此后全天提交的
RFC 015 工作全部没有生效，而"发版"看起来是成功的。

改成符号链接后：改源码 → 重启即生效，且**不存在"忘记部署"这个失败模式**。

## 2026-09-12 修正（w-adb088f2）—— 本脚本此前对 :13080 **空检**

实测：:13080 运行 profile（~/.dsh-agent-dh/profiles/investment）的 23 个 @pi-investment 依赖
**全部是 `link:` 协议**，而本脚本只认 `file:` → 每个包都被"不是 file: 依赖，跳过"，
最后打印 `共 0 个包` 却依然输出 **OK: 所有插件均为指向仓库的符号链接**。
一句什么都没检查的 OK —— 这正是它最危险的地方（我被它骗过一次）。
本次修正：
  ① 同时支持 `file:` 与 `link:` 两种协议；
  ② **检查到 0 个包 → 判为失败**（没有校验能力不许报 OK）；
  ③ 新增 symlink-dangling 状态（链接指向的目标不存在）；
  ④ 默认 profile 改为"真实运行的那个"（$DSH_INVESTMENT_PROFILE → $DSH_HOME/profiles/investment
     → ~/.dsh-agent-dh/profiles/investment → ~/.dsh/profiles/investment），并显式打印所用路径。

## 注意

跑过 `pnpm install` 之后，pnpm 可能把符号链接换回硬链接副本，必须重跑本脚本。
`agent-dh/scripts/restart-with-build.sh` 已内置该步骤，正常发版走它即可。

## 用法

    python3 agent-dh/scripts/relink-profile.py --check      # 体检（漂移/空检 → 退出码 1）
    python3 agent-dh/scripts/relink-profile.py --dry-run    # 预览
    python3 agent-dh/scripts/relink-profile.py              # 执行（旧副本备份到 .deploy-backup/）
    python3 agent-dh/scripts/relink-profile.py --profile DIR
"""

import argparse
import json
import os
import shutil
import sys
import time

PKG_SCOPE = "@pi-investment"
BACKUP_DIRNAME = ".deploy-backup"
SUPPORTED_PROTOCOLS = ("file:", "link:")
FALLBACK_PROFILES = (
    "~/.dsh-agent-dh/profiles/investment",
    "~/.dsh/profiles/investment",
)


def resolve_profile(cli=None):
    """确定要处理的 profile：显式参数 > 环境变量 > DSH_HOME > 已知候选（取第一个存在的）。"""
    if cli:
        return os.path.abspath(os.path.expanduser(cli))
    env = os.environ.get("DSH_INVESTMENT_PROFILE")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    cands = []
    dsh_home = os.environ.get("DSH_HOME")
    if dsh_home:
        cands.append(os.path.join(dsh_home, "profiles", "investment"))
    cands += [os.path.expanduser(p) for p in FALLBACK_PROFILES]
    for c in cands:
        if os.path.isfile(os.path.join(c, "package.json")):
            return c
    return os.path.expanduser(FALLBACK_PROFILES[0])


def load_plan(profile):
    """返回 (plan, skipped)。plan 元素 = (短名, 安装路径, 仓库目标, 状态)。

    状态 ∈ symlink-ok / symlink-bad / symlink-dangling / copy / missing
    映射由 profile 依赖声明推导 —— 不硬编码包列表，新增包自动纳入。
    """
    pkg_dir = os.path.join(profile, "node_modules", PKG_SCOPE)
    pkg_json = os.path.join(profile, "package.json")
    if not os.path.isfile(pkg_json):
        raise SystemExit(f"profile package.json 不存在: {pkg_json}")

    with open(pkg_json) as f:
        deps = json.load(f).get("dependencies", {})

    plan, skipped = [], []
    for name, spec in sorted(deps.items()):
        if not name.startswith(PKG_SCOPE + "/"):
            continue
        proto = next((p for p in SUPPORTED_PROTOCOLS if str(spec).startswith(p)), None)
        if proto is None:
            skipped.append((name, spec))
            continue
        short = name.split("/", 1)[1]
        installed = os.path.join(pkg_dir, short)
        target = os.path.normpath(os.path.join(profile, str(spec)[len(proto):]))
        want = os.path.relpath(target, pkg_dir)

        if os.path.islink(installed):
            if os.readlink(installed) != want:
                state = "symlink-bad"
            elif not os.path.isdir(target):
                state = "symlink-dangling"
            else:
                state = "symlink-ok"
        elif os.path.isdir(installed):
            state = "copy"
        else:
            state = "missing"
        plan.append((short, installed, target, state))
    return plan, skipped


def main():
    ap = argparse.ArgumentParser(description="把 profile 插件依赖改成/校验为指向仓库的符号链接")
    ap.add_argument("--profile", default=None,
                    help="DSH profile 目录（默认：$DSH_INVESTMENT_PROFILE → $DSH_HOME/profiles/investment → ~/.dsh-agent-dh/... → ~/.dsh/...）")
    ap.add_argument("--check", action="store_true", help="只体检不做改动；存在漂移或空检时退出码 1")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要做什么")
    ap.add_argument("--exclude", action="append", default=[], help="保持现状的包名（可重复）")
    args = ap.parse_args()

    profile = resolve_profile(args.profile)
    plan, skipped = load_plan(profile)
    pkg_dir = os.path.join(profile, "node_modules", PKG_SCOPE)

    print(f"profile: {profile}")
    print(f"可检查的 {PKG_SCOPE}/* 依赖：{len(plan)} 个")

    # ② 空检即失败：什么都没检查时，绝不能输出 OK
    if not plan:
        print("❌ 未发现任何可检查的 @pi-investment 依赖（file:/link: 均为 0 个）——")
        print("   这不代表没问题，而是**本脚本对该 profile 没有校验能力**。")
        print(f"   请确认 --profile 指向真实运行的 profile（当前：{profile}）")
        return 1

    if skipped:
        print(f"⚠️ 以下 {len(skipped)} 个依赖协议不受支持，未纳入检查（不是 OK）：")
        for name, spec in skipped:
            print(f"     {name} = {spec}")

    counts = {}
    for _, _, _, state in plan:
        counts[state] = counts.get(state, 0) + 1
    print("状态统计: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    drift_states = ("copy", "symlink-bad", "symlink-dangling", "missing")
    drift = [p for p in plan if p[3] in drift_states]
    todo = [p for p in plan if p[3] in ("copy", "symlink-bad") and p[0] not in args.exclude]

    if args.exclude:
        print(f"已排除（保持现状）: {', '.join(sorted(args.exclude))}")

    if drift:
        print("\n有漂移的包:")
        for short, _, target, state in drift:
            why = {
                "copy": "硬链接副本（编辑后会静默停在旧版本）",
                "symlink-bad": "符号链接指向别处",
                "symlink-dangling": "符号链接悬空（目标不存在）",
                "missing": "未安装",
            }[state]
            tag = " [已排除]" if short in args.exclude else ""
            print(f"  {short:24s} {why}{tag}")
            print(f"      期望 -> {os.path.relpath(target, pkg_dir)}")

    actionable = [p for p in drift if p[0] not in args.exclude]

    if args.check:
        if actionable:
            print(f"\n存在 {len(actionable)} 个漂移包 —— 运行 relink-profile.py 修复。")
            return 1
        print(f"\nOK: 已检查 {len(plan)} 个包，均为指向仓库的符号链接（且目标存在）。")
        return 0

    if args.dry_run:
        print("\n[dry-run] 将要执行:")
        for short, _, target, _ in todo:
            print(f"  {short:24s} -> {os.path.relpath(target, pkg_dir)}")
        return 0

    if not todo:
        print("\n无需转换。")
        return 0

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(profile, BACKUP_DIRNAME, stamp)
    os.makedirs(backup, exist_ok=True)
    print(f"\n备份到: {backup}")

    failed = []
    for short, installed, target, _ in todo:
        if not os.path.isdir(target):
            print(f"  跳过 {short}: 仓库目录不存在 {target}")
            failed.append(short)
            continue
        # 注意: `ln -sfn` 对**已存在的目录**不会替换，而是在目录内建一个同名链接。
        # 必须先把旧目录移走，绝不能直接 ln 覆盖。
        shutil.move(installed, os.path.join(backup, short))
        os.symlink(os.path.relpath(target, pkg_dir), installed)
        ok = os.path.isdir(installed)
        print(f"  {'OK ' if ok else 'BAD'} {short:24s} -> {os.path.relpath(target, pkg_dir)}")
        if not ok:
            failed.append(short)

    print(f"\n完成 {len(todo) - len(failed)} 个" + (f"，失败: {failed}" if failed else ""))
    if failed:
        print(f"回滚: 把 {backup} 里的条目 mv 回 {pkg_dir}")
        return 1
    print("重启后生效: launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
