#!/usr/bin/env python3
"""把 DSH profile 里 @pi-investment/* 的硬链接副本换成指向仓库源码的符号链接。

## 为什么需要这个脚本

profile 的 `package.json` 用 `file:` 相对路径引用 agent-dh 的插件包。pnpm 对这类依赖做的
是**硬链接**：硬链接共享 inode，所以"当时"确实是实时同步的 —— 但这只在**没人替换过该文件**
时成立。任何一次 Write/Edit（写临时文件再 rename）都会换掉 inode、**断链**，于是 profile
那边静默停在旧版本，且没有任何提示。

2026-09-11 就是这么踩的：profile 冻结在当天 02:23 的 `pnpm install`，此后全天提交的
RFC 015 工作（分钟线 / 交易状态 / 可交易性闸门 / 产业链图谱 / 政策事件源，共 25 个新文件 +
21 个改动文件）**全部没有生效**，而"发版"看起来是成功的。

改成符号链接后：改源码 → 重启即生效，且**不存在"忘记部署"这个失败模式**。

## 注意

跑过 `pnpm install` 之后，pnpm 会把符号链接换回硬链接副本，必须重跑本脚本。
`agent-dh/scripts/restart-with-build.sh` 已内置该步骤，正常发版走它即可。

## 用法

    # 体检：只看是否有包不是符号链接 / 符号链接是否指对（有漂移则退出码 1，可用于 CI）
    python3 agent-dh/scripts/relink-profile.py --check

    # 预览将要做的改动
    python3 agent-dh/scripts/relink-profile.py --dry-run

    # 执行（先把旧副本 mv 到 .deploy-backup/<时间戳>/ 再建链接）
    python3 agent-dh/scripts/relink-profile.py

    # 某个包正在被别的会话改动、暂时不想发布，可排除
    python3 agent-dh/scripts/relink-profile.py --exclude dashboard-execution

映射来源固定为 profile `package.json` 的 `file:` 依赖声明 —— 权威、不手工维护。
"""

import argparse
import json
import os
import shutil
import sys
import time

PROFILE = os.environ.get("DSH_INVESTMENT_PROFILE", os.path.expanduser("~/.dsh/profiles/investment"))
PKG_SCOPE = "@pi-investment"
BACKUP_DIRNAME = ".deploy-backup"


def load_plan(profile=PROFILE):
    """返回 [(短名, 安装路径, 仓库目标, 状态)]，状态 ∈ symlink-ok/symlink-bad/copy/missing。

    映射由 profile 的 file: 依赖推导 —— 不硬编码包列表，新增包自动纳入。
    """
    pkg_dir = os.path.join(profile, "node_modules", PKG_SCOPE)
    pkg_json = os.path.join(profile, "package.json")
    if not os.path.isfile(pkg_json):
        raise SystemExit(f"profile package.json 不存在: {pkg_json}")

    with open(pkg_json) as f:
        deps = json.load(f).get("dependencies", {})

    plan = []
    for name, spec in sorted(deps.items()):
        if not name.startswith(PKG_SCOPE + "/"):
            continue
        if not spec.startswith("file:"):
            print(f"警告: {name} 不是 file: 依赖（{spec}），跳过", file=sys.stderr)
            continue
        short = name.split("/", 1)[1]
        installed = os.path.join(pkg_dir, short)
        target = os.path.normpath(os.path.join(profile, spec[len("file:"):]))
        want = os.path.relpath(target, pkg_dir)

        if os.path.islink(installed):
            state = "symlink-ok" if os.readlink(installed) == want else "symlink-bad"
        elif os.path.isdir(installed):
            state = "copy"
        else:
            state = "missing"
        plan.append((short, installed, target, state))
    return plan


def report(plan, excluded):
    counts = {}
    for _, _, _, state in plan:
        counts[state] = counts.get(state, 0) + 1
    return counts


def main():
    ap = argparse.ArgumentParser(description="把 profile 插件依赖改成指向仓库的符号链接")
    ap.add_argument("--profile", default=PROFILE)
    ap.add_argument("--check", action="store_true",
                    help="只体检不做改动；存在漂移时退出码 1")
    ap.add_argument("--dry-run", action="store_true", help="只打印将要做什么")
    ap.add_argument("--exclude", action="append", default=[],
                    help="保持现状的包名（可重复）")
    args = ap.parse_args()

    plan = load_plan(args.profile)
    pkg_dir = os.path.join(args.profile, "node_modules", PKG_SCOPE)
    todo = [p for p in plan if p[3] in ("copy", "symlink-bad") and p[0] not in args.exclude]
    drift = [p for p in plan if p[3] in ("copy", "symlink-bad", "missing")]

    counts = report(plan, args.exclude)
    print(f"profile: {args.profile}")
    print(f"共 {len(plan)} 个包: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    if args.exclude:
        print(f"已排除（保持现状）: {', '.join(sorted(args.exclude))}")

    if drift:
        print("\n有漂移的包（不是指向仓库的符号链接）:")
        for short, _, target, state in drift:
            why = {"copy": "硬链接副本（编辑后会静默停在旧版本）",
                   "symlink-bad": "符号链接指向别处",
                   "missing": "未安装"}[state]
            tag = " [已排除]" if short in args.exclude else ""
            print(f"  {short:24s} {why}{tag}")
            print(f"      期望 -> {os.path.relpath(target, pkg_dir)}")

    actionable = [p for p in drift if p[0] not in args.exclude]

    if args.check:
        if actionable:
            print(f"\n存在 {len(actionable)} 个漂移包 —— 运行 relink-profile.py 修复。")
            return 1
        print("\nOK: 所有插件均为指向仓库的符号链接。")
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
    backup = os.path.join(args.profile, BACKUP_DIRNAME, stamp)
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
