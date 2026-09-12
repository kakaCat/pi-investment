#!/usr/bin/env python3
"""发版四层体检（2026-09-12，w-adb088f2）—— 回答一个问题：**运行中的实例到底加载了最新代码吗？**

## 为什么需要它

今天连续两次"部署看起来成功、实际没生效"：
  ① 只改 src 没构建：19 个包里有 3 个 main 指向 dist/index.mjs ⇒ 进程加载的是旧产物；
  ② 先重启、后构建：进程启动时间早于产物 mtime ⇒ 加载的仍不是最新代码。
两次都没有任何运行时报错 —— 属**静默失效**。人肉"记得做几步"不可靠，本脚本把不变量写成断言。

## 四层断言

  L1 依赖层：profile 的 23 个 @pi-investment 依赖必须是指向仓库的符号链接（防空检）
  L2 产物层：每个 main→dist 的包，产物存在且不比 src/ 陈旧
  L3 进程层：**运行进程的启动时间必须晚于所有插件代码文件的最新 mtime**
             —— 这是"是否真的加载了最新包"的直接判据
  L4 留痕层：把结论写成 manifest（git HEAD + 进程 + 关键产物指纹），供事后审计

退出码：全通过 0 / 有失败 1 / 无法判定（服务未运行且未 --allow-stopped）2

## 用法

    python3 agent-dh/scripts/deploy-verify.py                # 全量四层
    python3 agent-dh/scripts/deploy-verify.py --skip-process  # 只查 L1/L2（构建未重启时用）
    python3 agent-dh/scripts/deploy-verify.py --allow-stopped # 服务未运行时不判失败
"""

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_SCOPE = "@pi-investment"
FALLBACK_PROFILES = ("~/.dsh-agent-dh/profiles/investment", "~/.dsh/profiles/investment")


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
    cands += [os.path.expanduser(p) for p in FALLBACK_PROFILES]
    for c in cands:
        if os.path.isfile(os.path.join(c, "package.json")):
            return c
    return os.path.expanduser(FALLBACK_PROFILES[0])


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def md5_of(path, limit=None):
    h = hashlib.md5()
    with open(path, "rb") as f:
        if limit:
            h.update(f.read(limit))
        else:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()


def process_start(pid):
    rc, out = run(["ps", "-o", "lstart=", "-p", str(pid)])
    if rc != 0 or not out.strip():
        return None
    txt = out.strip()
    for fmt in ("%a %b %d %H:%M:%S %Y",):
        try:
            return datetime.datetime.strptime(txt, fmt)
        except ValueError:
            continue
    return None


def listening_pid(port):
    rc, out = run(["lsof", "-ti", ":%d" % port, "-sTCP:LISTEN"])
    if rc != 0 or not out.strip():
        return None
    return int(out.strip().splitlines()[0])


def plugin_dirs(profile):
    """profile 里 @pi-investment/* 依赖解析到的仓库目录（跟随符号链接）。"""
    pkg_dir = os.path.join(profile, "node_modules", PKG_SCOPE)
    dirs = {}
    if not os.path.isdir(pkg_dir):
        return dirs
    for short in sorted(os.listdir(pkg_dir)):
        p = os.path.join(pkg_dir, short)
        if os.path.isdir(p):
            dirs[short] = os.path.realpath(p)
    return dirs


def newest_plugin_code(dirs):
    """所有插件包 src/ 与 dist/ 下文件的最新 mtime（= 当前磁盘上的代码新鲜度上限）。"""
    newest, newest_file = 0.0, None
    for short, real in dirs.items():
        for sub in ("src", "dist"):
            d = os.path.join(real, sub)
            if not os.path.isdir(d):
                continue
            for root, _dirs, files in os.walk(d):
                for f in files:
                    p = os.path.join(root, f)
                    try:
                        m = os.path.getmtime(p)
                    except OSError:
                        continue
                    if m > newest:
                        newest, newest_file = m, p
    return newest, newest_file


def main():
    ap = argparse.ArgumentParser(description="发版四层体检：依赖/产物/进程/留痕")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--port", type=int, default=13080)
    ap.add_argument("--skip-process", action="store_true", help="跳过 L3 进程层（构建未重启时用）")
    ap.add_argument("--allow-stopped", action="store_true", help="服务未运行时不判失败")
    ap.add_argument("--manifest", default=None, help="manifest 输出路径（默认 <profile>/state/deploy-manifest.json）")
    args = ap.parse_args()

    profile = resolve_profile(args.profile)
    manifest_path = args.manifest or os.path.join(profile, "state", "deploy-manifest.json")
    report = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "profile": profile, "checks": {}}
    failures = []

    print("=" * 60)
    print("  发版四层体检")
    print("=" * 60)
    print(f"profile: {profile}")

    # ---- L1 依赖层 ----
    rc, out = run(["python3", os.path.join(HERE, "relink-profile.py"), "--check", "--profile", profile])
    line = [l for l in out.splitlines() if l.startswith("可检查的")]
    print(f"[L1] 依赖符号链接 ... {'OK' if rc == 0 else 'FAIL'}"
          + (f"  ({line[0]})" if line else ""))
    report["checks"]["L1_links"] = {"ok": rc == 0, "detail": line[0] if line else out.strip()[-200:]}
    if rc != 0:
        failures.append("L1 依赖层：存在非符号链接依赖或空检（详见 relink-profile.py --check 输出）")

    # ---- L2 产物层 ----
    rc, out = run(["python3", os.path.join(HERE, "dist-packages.py"), "verify", os.path.dirname(HERE)])
    tail = [l for l in out.splitlines() if l.startswith("----")]
    print(f"[L2] dist 产物 ... {'OK' if rc == 0 else 'FAIL'}" + (f"  ({tail[0]})" if tail else ""))
    report["checks"]["L2_artifacts"] = {"ok": rc == 0, "detail": tail[0] if tail else out.strip()[-200:]}
    if rc != 0:
        failures.append("L2 产物层：有包产物缺失或落后于源码（详见 dist-packages.py verify 输出）")

    # ---- L3 进程层 ----
    dirs = plugin_dirs(profile)
    newest_m, newest_f = newest_plugin_code(dirs)
    pid = listening_pid(args.port)
    if args.skip_process:
        print("[L3] 进程加载新鲜度 ... SKIP（--skip-process）")
        report["checks"]["L3_process"] = {"ok": None, "detail": "skipped"}
    elif pid is None:
        msg = f"端口 {args.port} 无监听进程，无法判定运行实例是否加载最新代码"
        if args.allow_stopped:
            print(f"[L3] 进程加载新鲜度 ... SKIP（服务未运行，--allow-stopped）")
            report["checks"]["L3_process"] = {"ok": None, "detail": msg}
        else:
            print(f"[L3] 进程加载新鲜度 ... FAIL  ({msg})")
            report["checks"]["L3_process"] = {"ok": False, "detail": msg}
            failures.append("L3 进程层：" + msg)
    else:
        started = process_start(pid)
        if started is None:
            print("[L3] 进程加载新鲜度 ... FAIL  (无法读取进程启动时间)")
            report["checks"]["L3_process"] = {"ok": False, "detail": "无法读取进程启动时间"}
            failures.append("L3 进程层：无法读取进程启动时间")
        else:
            code_dt = datetime.datetime.fromtimestamp(newest_m)
            stale = started < code_dt
            detail = (f"进程 {pid} 启动于 {started.strftime('%m-%d %H:%M:%S')}；"
                      f"最新插件代码 mtime {code_dt.strftime('%m-%d %H:%M:%S')}"
                      + (f"（{os.path.relpath(newest_f, os.path.dirname(HERE))}）" if newest_f else ""))
            if stale:
                print(f"[L3] 进程加载新鲜度 ... FAIL  (进程比代码还老 ⇒ 未加载最新包)")
                print(f"       {detail}")
                report["checks"]["L3_process"] = {"ok": False, "detail": detail, "pid": pid,
                                                  "process_started": started.isoformat(),
                                                  "newest_code": code_dt.isoformat()}
                failures.append("L3 进程层：进程启动时间早于最新代码 mtime ⇒ 运行实例未加载最新包，需重启")
            else:
                print(f"[L3] 进程加载新鲜度 ... OK  ({detail})")
                report["checks"]["L3_process"] = {"ok": True, "detail": detail, "pid": pid,
                                                  "process_started": started.isoformat(),
                                                  "newest_code": code_dt.isoformat(),
                                                  "newest_code_file": newest_f}

    # ---- L4 留痕 ----
    _, head = run(["git", "-C", os.path.dirname(HERE), "rev-parse", "--short", "HEAD"])
    _, dirty = run(["git", "-C", os.path.dirname(HERE), "status", "--porcelain", "--", "packages/"])
    report["git_head"] = head.strip()
    report["packages_dirty"] = [l for l in dirty.splitlines() if l.strip()]
    report["plugin_packages"] = len(dirs)
    report["dist_artifact_fingerprints"] = {}
    for short, real in sorted(dirs.items()):
        art = os.path.join(real, "dist", "index.mjs")
        if os.path.isfile(art):
            report["dist_artifact_fingerprints"][short] = {
                "md5": md5_of(art)[:16],
                "mtime": datetime.datetime.fromtimestamp(os.path.getmtime(art)).isoformat(timespec="seconds"),
                "bytes": os.path.getsize(art),
            }
    process_check = report["checks"].get("L3_process", {})
    report["process_verified"] = process_check.get("ok") is True
    report["result"] = "FAIL" if failures else ("PASS" if report["process_verified"] else "PASS_PARTIAL")
    report["failures"] = failures

    try:
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"[L4] manifest 已写入 {manifest_path}")
    except OSError as e:
        print(f"[L4] manifest 写入失败（不阻断判定）：{e}")

    print("-" * 60)
    if failures:
        print("❌ 体检未通过：")
        for f in failures:
            print("   - " + f)
        return 1
    if report["process_verified"]:
        print("✅ 体检通过：运行实例加载的是最新代码")
    else:
        # 跳过/无法判定进程层时，**不得**宣称"已加载最新代码"（那是本脚本要治的话术）
        print("✅ L1/L2 通过（进程层未判定 —— 这不等于运行实例已加载最新代码）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
