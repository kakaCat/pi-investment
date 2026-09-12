#!/usr/bin/env python3
"""发行包判定与产物校验（2026-09-12，w-adb088f2）

背景（真实事故）：restart-with-build.sh 原先硬编码只构建两个 client 包，并断言
『其余包 tsx 直载 TS，无需构建』——与事实不符：investment / genome / lifecycle 的
package.json main 指向 ./dist/index.mjs，只改 src 不构建 ⇒ 重启后仍是旧代码（本次
5 项修复里有 3 项因此静默未生效）。本模块把"哪些包需要构建"改为**按 main 字段自动判定**，
并把"产物是否与源码同步"做成可校验的断言。

用法：
  dist-packages.py list   <agent-dh-root>    # 输出 "包目录<TAB>main"，每行一个
  dist-packages.py verify <agent-dh-root>    # 校验产物存在且不比 src/ 陈旧；失败退出码 1
"""
import json
import pathlib
import sys


def candidates(root: pathlib.Path):
    dirs = sorted([d for d in (root / "packages").glob("*/") if d.is_dir()])
    for extra in (root.parent / "agent-os-client", root.parent / "quantsys-v2-client"):
        if (extra / "package.json").exists():
            dirs.append(extra)
    return dirs


def dist_packages(root: pathlib.Path):
    out = []
    for d in candidates(root):
        pj = d / "package.json"
        if not pj.exists():
            continue
        try:
            meta = json.loads(pj.read_text(encoding="utf-8"))
        except Exception as exc:  # 解析失败要显式可见，不能静默跳过
            print(f"WARN 无法解析 {pj}: {exc}", file=sys.stderr)
            continue
        main = str(meta.get("main") or "")
        if "dist/" in main:
            out.append((d.resolve(), main))
    return out


def artifact_of(pkg_dir: pathlib.Path, main: str) -> pathlib.Path:
    return (pkg_dir / main.lstrip("./")).resolve()


def cmd_list(root: pathlib.Path) -> int:
    pkgs = dist_packages(root)
    for d, main in pkgs:
        print(f"{d}\t{main}")
    print(f"# 需构建的 dist 包：{len(pkgs)} 个", file=sys.stderr)
    return 0


def cmd_verify(root: pathlib.Path) -> int:
    pkgs = dist_packages(root)
    # 2026-09-13（独立审阅 M1）：0 个包 = "没有可校验对象"，绝不等于通过。
    # 此前返回 "0/0 通过" exit 0，配合发版脚本里被 2>/dev/null 吞掉的 lister 失败，
    # 会演成"什么都没构建、什么都没校验"却宣布发版成功。
    if not pkgs:
        print("❌ 未发现任何 main 指向 dist/ 的包 —— 无可校验对象 ≠ 通过（可能根目录不对或解析失败）")
        return 2
    fails = []
    for d, main in pkgs:
        art = artifact_of(d, main)
        if not art.exists():
            fails.append((d.name, f"产物缺失：{art}"))
            continue
        src = d / "src"
        if src.is_dir():
            newer = [p for p in src.rglob("*.ts") if p.stat().st_mtime > art.stat().st_mtime]
            if newer:
                shown = ", ".join(str(p.relative_to(d)) for p in newer[:3])
                fails.append((d.name, f"产物陈旧（源文件比产物新）：{shown}"))
                continue
        print(f"OK   {d.name:26} {main}  ({art.stat().st_size} bytes)")
    for name, why in fails:
        print(f"FAIL {name:26} {why}")
    ok = len(pkgs) - len(fails)
    print(f"---- dist 产物校验：{ok}/{len(pkgs)} 通过")
    return 1 if fails else 0


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in ("list", "verify"):
        print(__doc__)
        return 2
    action, root = sys.argv[1], pathlib.Path(sys.argv[2]).resolve()
    if not (root / "packages").is_dir():
        print(f"❌ 不是有效的 agent-dh 根目录：{root}")
        return 2
    return cmd_list(root) if action == "list" else cmd_verify(root)


if __name__ == "__main__":
    raise SystemExit(main())
