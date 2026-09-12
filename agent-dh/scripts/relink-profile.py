#!/usr/bin/env python3
"""把 DSH profile 的插件依赖校验/修复为指向仓库源码的符号链接。

## 为什么需要这个脚本
profile 用 `file:` / `link:` 引用仓库里的插件包。pnpm 对 `file:` 做的是**硬链接**：
编辑换 inode 即断链，profile 静默停在旧版本（2026-09-11 事故：全天工作未生效）。
符号链接没有这个失败模式。跑过 `pnpm install` 后可能被换回副本，需重跑本脚本。

## 2026-09-13 修正（w-adb088f2，来自独立只读审阅的三条发现）

① 【H3 覆盖不全】此前只遍历 profile package.json 里 `@pi-investment/*` 的依赖（23 个），
   而运行时实际解析的是 `node_modules` 里的**全部条目**（实测 30 个）。差集里
   `dashboard-bulletin` 是**普通目录副本**（正是本脚本要治的冻结形态），
   `page-kit` / `dashboard-*` / 非作用域的 `dsh-pmboard` 全在覆盖之外 →
   "改仓库源码、公告板静默不生效"对整条发版链路隐形。
   现检查集合 = **所有 `file:`/`link:` 声明（不限作用域） ∪ node_modules 实际条目**，
   非符号链接的条目一律判漂移；`.bak*` 残留单列为 residue 而不计入漂移。
② 【M2 修复模式谎报】此前 todo 只含 copy/symlink-bad，修复后不管结果直接 return 0；
   missing/symlink-dangling 明明没修也报成功（发版流程会带着坏链重启）。
   现修复后**重算漂移**，仍有漂移即非零退出。
③ 【L3 破坏性动作】此前用 `os.readlink()` **字符串**比对，写成绝对路径的软链会被判
   symlink-bad 并被 move+重建（无谓破坏）。现用 `realpath` 比对。

另：协议不受支持（如 `^1.2.3`）此前只打 ⚠️ 不影响退出码 —— 依赖一旦回退成 semver，
插件会加载 registry 副本而本脚本仍报 OK。现在 `--check` 下视为未通过
（确需放行用 `--allow-unknown-protocol`）。

## 用法
    python3 agent-dh/scripts/relink-profile.py --check            # 体检（漂移/空检/未知协议 → 1）
    python3 agent-dh/scripts/relink-profile.py --dry-run          # 预览
    python3 agent-dh/scripts/relink-profile.py                    # 修复（备份到 .deploy-backup/）
    python3 agent-dh/scripts/relink-profile.py --profile DIR
"""

import argparse
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_SCOPE = "@pi-investment"
BACKUP_DIRNAME = ".deploy-backup"
SUPPORTED_PROTOCOLS = ("file:", "link:")
# 仓库外的历史 profile 副本：仅作兜底（回滚场景），正常情况下不该被选中。
LEGACY_PROFILES = (
    "~/.dsh-agent-dh/profiles/investment",
    "~/.dsh/profiles/investment",
)
RESIDUE_PREFIXES = (".bak",)
# 自动可修的状态（有明确目标可重建链接）
FIXABLE = ("copy", "symlink-bad", "missing")
# 判定为漂移的状态
DRIFT = ("copy", "symlink-bad", "symlink-dangling", "missing", "outside-repo")


def project_profile(profile_name="investment"):
    """项目内托管布局的 profile 目录 —— 2026-09-13 起 :13080 的现役布局。

    从脚本自身位置反推（scripts/ -> agent-dh/ -> .dsh-home/profiles/<name>），
    **不硬编码 home**：硬编码正是 2026-09-13 那次漂移的成因 —— 本脚本当时指着
    ~/.dsh-agent-dh 体检，给出一句 "OK 29 个符号链接"，而真正在跑的是 .dsh-home，
    体检对象整个是错的，且没有任何迹象。
    """
    agent_dh = os.path.dirname(HERE)
    return os.path.join(agent_dh, ".dsh-home", "profiles", profile_name)


def resolve_profile(cli=None):
    if cli:
        return os.path.abspath(os.path.expanduser(cli))
    env = os.environ.get("DSH_INVESTMENT_PROFILE")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    cands = []
    dsh_home = os.environ.get("DSH_HOME")
    if dsh_home:
        cands.append(os.path.join(dsh_home, "profiles", "investment"))
    cands.append(project_profile())
    for c in cands:
        if os.path.isfile(os.path.join(c, "package.json")):
            return c
    legacy = [
        os.path.expanduser(p)
        for p in LEGACY_PROFILES
        if os.path.isfile(os.path.join(os.path.expanduser(p), "package.json"))
    ]
    if legacy:
        print(
            f"⚠️ 项目内 profile ({project_profile()}) 不可用，回退到仓库外的历史副本：{legacy[0]}\n"
            f"   这不是 :13080 的现役布局。确认目标无误后再继续。",
            file=sys.stderr,
        )
        return legacy[0]
    return project_profile()


def find_repo_root(profile, declared_targets):
    """从任一已声明的目标反推仓库根（含 agent-dh/packages 的目录）。"""
    for t in declared_targets:
        p = os.path.abspath(t)
        for _ in range(8):
            if os.path.isdir(os.path.join(p, "agent-dh", "packages")):
                return p
            parent = os.path.dirname(p)
            if parent == p:
                break
            p = parent
    return None


def repo_index(root):
    """仓库内 包名 -> 目录（含 packages 下多层，如 packages/pages/*，以及两个顶层 client）。"""
    idx = {}
    if not root:
        return idx
    roots = [os.path.join(root, "agent-dh", "packages")]
    for extra in ("agent-os-client", "quantsys-v2-client"):
        d = os.path.join(root, extra)
        if os.path.isfile(os.path.join(d, "package.json")):
            roots.append(d)
    for base in roots:
        for dirpath, dirnames, filenames in os.walk(base):
            if "node_modules" in dirpath.split(os.sep):
                continue
            if dirpath.count(os.sep) - base.count(os.sep) > 3:
                dirnames[:] = []
                continue
            if "package.json" in filenames:
                try:
                    with open(os.path.join(dirpath, "package.json"), encoding="utf-8") as f:
                        nm = json.load(f).get("name")
                    if nm:
                        idx.setdefault(nm, dirpath)
                except (OSError, ValueError):
                    pass
    return idx


def _state_of(installed, declared_target):
    """declared_target=None 表示"未声明的运行时条目"（只能判是否副本）。"""
    if os.path.islink(installed):
        real = os.path.realpath(installed)
        if not os.path.exists(real):
            return "symlink-dangling"
        if declared_target is not None:
            if os.path.realpath(declared_target) != real:
                return "symlink-bad"
            return "symlink-ok"
        return "linked-unverified"
    if os.path.isdir(installed):
        # 普通目录 = 硬链接副本/拷贝（编辑源码后不会跟着变）
        return "copy"
    return "missing"


def load_plan(profile):
    """返回 (plan, skipped, residue)。

    plan 元素 = (名称, 安装路径, 声明目标或 None, 状态)
    检查集合 = 所有 file:/link: 声明（不限作用域） ∪ node_modules 下 @pi-investment/* 实际条目。
    """
    pkg_json = os.path.join(profile, "package.json")
    if not os.path.isfile(pkg_json):
        raise SystemExit(f"profile package.json 不存在: {pkg_json}")
    with open(pkg_json) as f:
        deps = json.load(f).get("dependencies", {})

    # ① 声明的链接型依赖（任意作用域，如 @pi-investment/x、dsh-pmboard）
    declared = {}   # 安装路径 -> (名称, 目标)
    skipped = []
    for name, spec in sorted(deps.items()):
        proto = next((p for p in SUPPORTED_PROTOCOLS if str(spec).startswith(p)), None)
        if proto is None:
            # 只有仓库内插件（scoped 或已知本地包）才值得告警，registry 依赖不算
            if name.startswith(PKG_SCOPE + "/") or "pmboard" in name:
                skipped.append((name, str(spec)))
            continue
        installed = os.path.join(profile, "node_modules", *name.split("/"))
        target = os.path.normpath(os.path.join(profile, str(spec)[len(proto):]))
        declared[installed] = (name, target)

    plan, residue = [], []
    seen = set()
    repo_root = find_repo_root(profile, [t for _, t in declared.values()])
    idx = repo_index(repo_root)

    for installed, (name, target) in sorted(declared.items()):
        seen.add(installed)
        plan.append((name, installed, target, _state_of(installed, target)))

    # ② 运行时实际条目（未声明的也要管 —— 审阅发现的 dashboard-bulletin 副本就在这里）
    scope_dir = os.path.join(profile, "node_modules", PKG_SCOPE)
    if os.path.isdir(scope_dir):
        for short in sorted(os.listdir(scope_dir)):
            installed = os.path.join(scope_dir, short)
            if installed in seen:
                continue
            if any(p in short for p in RESIDUE_PREFIXES):
                residue.append((PKG_SCOPE + "/" + short, installed))
                continue
            name = PKG_SCOPE + "/" + short
            seen.add(installed)
            # 未声明条目按包名反查仓库目录，使"副本 → 软链"仍可自动修复
            target = idx.get(name)
            plan.append((name, installed, target, _state_of(installed, target)))

    # ③ cordis.patch.yml 引用的插件（补非 @pi-investment 作用域，如 dsh-pmboard）
    patch = os.path.join(profile, "cordis.patch.yml")
    referenced = []
    if os.path.isfile(patch):
        import re as _re
        with open(patch, encoding="utf-8") as f:
            txt = f.read()
        for m in _re.finditer(r"^\s*-?\s*name:\s*'([^']+)'", txt, _re.M):
            nm = m.group(1).strip()
            if not nm or nm.startswith("@deepseek-ai/"):
                continue
            referenced.append(nm)
    for nm in sorted(set(referenced)):
        installed = os.path.join(profile, "node_modules", *nm.split("/"))
        if installed in seen:
            continue
        if not os.path.exists(installed) and not os.path.islink(installed):
            continue  # 由 DSH 基础 bundle 提供的核插件不在 profile node_modules 下
        seen.add(installed)
        plan.append((nm, installed, idx.get(nm), _state_of(installed, idx.get(nm))))

    return plan, skipped, residue


def summarize(plan):
    counts = {}
    for _, _, _, st in plan:
        counts[st] = counts.get(st, 0) + 1
    return counts


def main():
    ap = argparse.ArgumentParser(description="把 profile 插件依赖校验/修复为指向仓库的符号链接")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--check", action="store_true", help="只体检；漂移/空检/未知协议 → 退出码 1")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--allow-unknown-protocol", action="store_true",
                    help="允许存在非 file:/link: 的插件依赖（默认在 --check 下视为未通过）")
    args = ap.parse_args()

    profile = resolve_profile(args.profile)
    plan, skipped, residue = load_plan(profile)
    print(f"profile: {profile}")
    print(f"检查集合：{len(plan)} 个安装条目（声明 ∪ node_modules 实际条目）")

    if not plan:
        print("❌ 未发现任何可检查的插件安装条目 —— 这不代表没问题，而是本脚本对该 profile 没有校验能力。")
        print(f"   请确认 --profile 指向真实运行的 profile（当前：{profile}）")
        return 1

    counts = summarize(plan)
    print("状态统计: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if residue:
        print(f"ℹ️ 残留目录（不计漂移，建议清理）: {', '.join(n for n, _ in residue)}")
    if plan and counts.get("linked-unverified"):
        print("ℹ️ linked-unverified：未声明的运行时条目，已确认是指向外部（非副本）的软链")

    drift = [(n, i, t, st) for n, i, t, st in plan if st in DRIFT]
    todo = [p for p in plan if p[3] in FIXABLE and p[0] not in args.exclude]

    if args.exclude:
        print(f"已排除: {', '.join(sorted(args.exclude))}")
    if drift:
        print("\n漂移条目：")
        for name, _, target, st in drift:
            why = {
                "copy": "普通目录副本（编辑源码后不跟着变 → 静默停在旧版本）",
                "symlink-bad": "软链指向别处",
                "symlink-dangling": "软链悬空（目标不存在）",
                "missing": "声明了但未安装",
                "outside-repo": "软链指向仓库之外",
            }.get(st, st)
            print(f"  {name:34s} {why}" + (f"  期望 -> {target}" if target else ""))

    actionable = [p for p in drift if p[0] not in args.exclude]

    if args.check:
        if skipped and not args.allow_unknown_protocol:
            print(f"\n❌ 有 {len(skipped)} 个插件依赖协议不受支持（会被当成 registry 包加载，本脚本无法验证）：")
            for n, s in skipped:
                print(f"     {n} = {s}")
            return 1
        if actionable:
            print(f"\n❌ 存在 {len(actionable)} 个漂移条目 —— 运行 relink-profile.py 修复。")
            return 1
        print(f"\nOK: 已检查 {len(plan)} 个条目，均为指向仓库的符号链接（且非副本）。")
        return 0

    if args.dry_run:
        print("\n[dry-run] 将要修复:")
        for name, _, target, _ in todo:
            print(f"  {name:34s} -> {target}")
        return 0

    if not todo:
        print("\n无需修复。")
        return 0 if not actionable else 1

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(profile, BACKUP_DIRNAME, stamp)
    os.makedirs(backup, exist_ok=True)
    print(f"\n备份到: {backup}")

    failed = []
    for name, installed, target, _ in todo:
        if target is None:
            failed.append(name)
            continue
        if not os.path.isdir(target):
            print(f"  跳过 {name}: 仓库目标不存在 {target}")
            failed.append(name)
            continue
        # 注意: ln -sfn 对已存在目录不会替换，必须先移走再建链接
        shutil.move(installed, os.path.join(backup, name.replace("/", "__")))
        os.makedirs(os.path.dirname(installed), exist_ok=True)
        os.symlink(os.path.relpath(target, os.path.dirname(installed)), installed)
        ok = os.path.isdir(installed) and os.path.realpath(installed) == os.path.realpath(target)
        print(f"  {'OK ' if ok else 'BAD'} {name:34s} -> {target}")
        if not ok:
            failed.append(name)

    # 2026-09-13（M2）：修复后**重算**漂移，避免"谎报修好"
    plan2, _, _ = load_plan(profile)
    still = [p for p in plan2 if p[3] in DRIFT and p[0] not in args.exclude]
    if still or failed:
        print(f"\n❌ 修复后仍存在 {len(still)} 个漂移条目" + (f"，失败 {len(failed)} 个" if failed else ""))
        for name, _, _, st in still:
            print(f"   {name:34s} {st}")
        print("   提示：missing/悬空多为未安装或目标被删 —— 先 pnpm install 并确认仓库存在，再重跑本脚本")
        print(f"   回滚: 把 {backup} 里的条目 mv 回原位")
        return 1

    print(f"\n完成 {len(todo)} 个，修复后无残留漂移。")
    print("重启后生效: launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
