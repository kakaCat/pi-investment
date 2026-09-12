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
# 仓库外的历史 profile 副本：仅作兜底（回滚场景），正常情况下不该被选中。
LEGACY_PROFILES = ("~/.dsh-agent-dh/profiles/investment", "~/.dsh/profiles/investment")


def project_profile(profile_name="investment"):
    """项目内托管布局的 profile 目录 —— 2026-09-13 起 :13080 的现役布局。

    从脚本自身位置反推（scripts/ -> agent-dh/ -> .dsh-home/profiles/<name>），
    **不硬编码 home**：硬编码正是 2026-09-13 那次漂移的成因 —— 发版工具链指着
    ~/.dsh-agent-dh，而真正在跑的是 .dsh-home，体检整个验错了对象。
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


def process_start_subsec(pid):
    """macOS: 用 proc_pidinfo 取**亚秒**进程启动时间。失败返回 (None, '')。

    2026-09-13（独立审阅 H2 实证）：ps -o lstart 只有秒级精度，配合 1 秒容差会掩盖
    "进程启动后 ~1 秒内写入的代码"。实测真实 manifest 的 PASS 余量只有 0.102s
    （进程 00:17:13.930927 vs 代码 00:17:13.828433）—— 判据落在噪声里，不构成证据。
    """
    try:
        import ctypes
        import ctypes.util
        libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)

        class BSP(ctypes.Structure):
            _fields_ = [
                ("pbi_flags", ctypes.c_uint32), ("pbi_status", ctypes.c_uint32),
                ("pbi_xstatus", ctypes.c_uint32), ("pbi_pid", ctypes.c_uint32),
                ("pbi_ppid", ctypes.c_uint32), ("pbi_uid", ctypes.c_uint32),
                ("pbi_gid", ctypes.c_uint32), ("pbi_ruid", ctypes.c_uint32),
                ("pbi_rgid", ctypes.c_uint32), ("pbi_svuid", ctypes.c_uint32),
                ("pbi_svgid", ctypes.c_uint32), ("rfu_1", ctypes.c_uint32),
                ("pbi_comm", ctypes.c_char * 16), ("pbi_name", ctypes.c_char * 32),
                ("pbi_nfiles", ctypes.c_uint32), ("pbi_pgid", ctypes.c_uint32),
                ("pbi_pjobc", ctypes.c_uint32), ("e_tdev", ctypes.c_uint32),
                ("e_tpgid", ctypes.c_uint32), ("pbi_nice", ctypes.c_int32),
                ("pbi_start_tvsec", ctypes.c_uint64), ("pbi_start_tvusec", ctypes.c_uint64),
            ]

        b = BSP()
        n = libc.proc_pidinfo(pid, 3, 0, ctypes.byref(b), ctypes.sizeof(b))
        if n > 0 and b.pbi_start_tvsec > 0:
            return b.pbi_start_tvsec + b.pbi_start_tvusec / 1e6, "proc_pidinfo(亚秒)"
    except Exception:
        pass
    return None, ""


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


def package_fingerprint(real_dir):
    """包内容指纹：md5(排序后的 (相对路径, 文件内容md5))，覆盖 dist/index.mjs 与 src/**/*.ts。

    用**内容**而非 mtime 判断"运行实例加载的代码是否仍是当前磁盘上的代码"——
    mtime 会被重建（内容未变）或无关注销（git 操作）污染，实测已造成误报。
    """
    items = []
    for sub in ("dist/index.mjs", "src"):
        p = os.path.join(real_dir, sub)
        if os.path.isfile(p):
            items.append(p)
        elif os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for f in files:
                    if f.endswith(".ts"):
                        items.append(os.path.join(root, f))
    items.sort()
    h = hashlib.md5()
    for p in items:
        try:
            h.update(os.path.relpath(p, real_dir).encode("utf-8"))
            h.update(md5_of(p).encode("ascii"))
        except OSError:
            continue
    return h.hexdigest()[:16]


def plugin_dirs(profile):
    """profile 里 @pi-investment/* 依赖解析到的仓库目录（跟随符号链接）。"""
    pkg_dir = os.path.join(profile, "node_modules", PKG_SCOPE)
    dirs = {}
    if not os.path.isdir(pkg_dir):
        return dirs
    skipped = []
    for short in sorted(os.listdir(pkg_dir)):
        if ".bak" in short:
            continue  # 残留备份目录：不纳入新鲜度，否则碰一下备份就误判 FAIL（审阅 L5）
        p = os.path.join(pkg_dir, short)
        if os.path.isdir(p):
            dirs[short] = os.path.realpath(p)
        else:
            skipped.append(short)
    return dirs, skipped


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
    dirs, unresolved = plugin_dirs(profile)
    if unresolved:
        # 审阅 L5：条目无法解析必须报错，不能静默丢弃
        print(f"[L3] ⚠️ profile 中有 {len(unresolved)} 个条目无法解析：{', '.join(unresolved[:5])}")
        failures.append("L3 进程层：profile 条目无法解析（悬空/类型异常）：" + ", ".join(unresolved[:5]))
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
        # 2026-09-13（H2）：优先用 proc_pidinfo 取**亚秒**启动时间；只有它可用时才谈得上"余量"
        start_ts, start_src = process_start_subsec(pid)
        precise = start_ts is not None
        started = datetime.datetime.fromtimestamp(start_ts) if precise else process_start(pid)
        if started is None:
            print("[L3] 进程加载新鲜度 ... FAIL  (无法读取进程启动时间)")
            report["checks"]["L3_process"] = {"ok": False, "detail": "无法读取进程启动时间"}
            failures.append("L3 进程层：无法读取进程启动时间")
        else:
            # ── 判据一（优先）：内容指纹与"进程启动前的最后一次记录"一致 ⇒ 期间代码内容没变，
            #    进程加载的就是当前磁盘上的代码（免疫重建/mtime 抖动）。
            prev = {}
            if os.path.isfile(manifest_path):
                try:
                    with open(manifest_path, encoding="utf-8") as pf:
                        prev = json.load(pf)
                except (OSError, ValueError):
                    prev = {}
            prev_fps = prev.get("fingerprints") or {}
            prev_ts = prev.get("ts")
            cur_fps = {short: package_fingerprint(real) for short, real in dirs.items()}
            prev_before_process = False
            if prev_ts and prev_fps:
                try:
                    prev_before_process = datetime.datetime.fromisoformat(prev_ts) < started
                except ValueError:
                    prev_before_process = False
            changed = sorted(
                k for k in set(prev_fps) | set(cur_fps)
                if prev_fps.get(k) != cur_fps.get(k)
            )
            report["fingerprints"] = cur_fps
            if prev_before_process and not changed:
                # 判据一（优先）：内容指纹一致 ⇒ 进程加载的就是当前磁盘上的代码
                detail = (f"进程 {pid} 启动于 {started.strftime('%m-%d %H:%M:%S')}；"
                          f"启动后插件代码内容未变（指纹一致，免疫 mtime 抖动）")
                print(f"[L3] 进程加载新鲜度 ... OK  ({detail})")
                report["checks"]["L3_process"] = {"ok": True, "detail": detail, "pid": pid,
                                                  "process_started": started.isoformat(),
                                                  "basis": "content_fingerprint"}
            else:
                # 判据二（兜底）：mtime 先后。
                # 2026-09-13（独立审阅 H2）：有亚秒启动时间时**不再用容差**，直接比真实余量；
                # 只有秒级时间且余量落在 1s 内时 → "先后不可知" → 判**不可判定**（不等于 OK）。
                code_dt = datetime.datetime.fromtimestamp(newest_m)
                margin = (started - code_dt).total_seconds()
                TOLERANCE_SEC = 1.0
                indeterminate = (not precise) and abs(margin) <= TOLERANCE_SEC
                stale = (margin <= 0) if precise else (margin < -TOLERANCE_SEC)
                ms = lambda d: f"{int((d.microsecond / 1e6) * 1000):03d}"
                detail = (f"进程 {pid} 启动于 {started.strftime('%m-%d %H:%M:%S')}"
                          + (f".{ms(started)}" if precise else "")
                          + f"（{start_src or 'ps(秒级)'}）；最新插件代码 mtime {code_dt.strftime('%m-%d %H:%M:%S')}.{ms(code_dt)}"
                          + f"，余量 {margin:+.3f}s"
                          + (f"（{os.path.relpath(newest_f, os.path.dirname(HERE))}）" if newest_f else ""))
                if indeterminate:
                    print("[L3] 进程加载新鲜度 ... 不可判定（只有秒级启动时间且余量落入 1s 容差内）")
                    print(f"       {detail}")
                    report["checks"]["L3_process"] = {"ok": False, "detail": detail, "pid": pid,
                                                      "process_started": started.isoformat(),
                                                      "newest_code": code_dt.isoformat(),
                                                      "basis": "indeterminate"}
                    failures.append("L3 进程层：余量落在容差内、先后不可知 —— 不构成『已加载最新代码』的证据（判为未通过）")
                elif stale:
                    print(f"[L3] 进程加载新鲜度 ... FAIL  (进程比代码还老 ⇒ 未加载最新包)")
                    print(f"       {detail}")
                    report["checks"]["L3_process"] = {"ok": False, "detail": detail, "pid": pid,
                                                      "process_started": started.isoformat(),
                                                      "newest_code": code_dt.isoformat(),
                                                      "basis": "mtime"}
                    failures.append("L3 进程层：进程启动时间早于最新代码 mtime ⇒ 运行实例未加载最新包，需重启")
                else:
                    print(f"[L3] 进程加载新鲜度 ... OK  ({detail})")
                    report["checks"]["L3_process"] = {"ok": True, "detail": detail, "pid": pid,
                                                      "process_started": started.isoformat(),
                                                      "newest_code": code_dt.isoformat(),
                                                      "newest_code_file": newest_f,
                                                      "margin_sec": round(margin, 3),
                                                      "basis": "mtime_subsec" if precise else "mtime"}

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
