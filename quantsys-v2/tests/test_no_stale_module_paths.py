"""字符串模块路径守卫（2026-09-14 w-c8cae280）

为什么要有这个测试（根因，不是症状）：
  mock.patch('pkg.mod.attr') / importlib.import_module('pkg.mod') / register_adapter("x","pkg.mod.Cls")
  这类调用把**模块路径写成字符串**，包搬家时字符串不会跟着动，也没有任何工具会警告 ——
  直到运行时炸出 ModuleNotFoundError，而栈全是 <frozen importlib._bootstrap>，看不到仓内帧。
  实证：2026-09-13 全量测试里这一类根因占约 80 项红账（quantlib 53 + cli/daemon 27）。

本测试把 tools/check_module_paths.py 接进常规套件 —— **机制必须被强制执行**，
否则"修完这一次"等于没修：下一次包搬家会原样复现。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.check_module_paths import scan  # noqa: E402


def test_no_unresolvable_string_module_paths():
    findings = scan(ROOT)
    detail = chr(10).join(
        "  %s:%d  %s('%s')" % (f["file"], f["line"], f["call"], f["path"]) for f in findings
    )
    assert not findings, (
        "发现 %d 处无法解析的字符串模块路径（包已搬家但字符串没动）：" % len(findings)
        + chr(10) + detail + chr(10)
        + "修法：① 改到当前路径；② 更稳的做法是不写字符串 —— import 模块后用 patch.object(module, 'attr')，"
        + "搬家时会在 import 处立刻报错，且 IDE/类型检查能解析。"
    )