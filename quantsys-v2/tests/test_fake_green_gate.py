"""假绿灯门禁（REQ-261004154902-a7cd · t13 / FR-1、FR-5、FR-6、FR-10）。

为什么需要这条门禁，见 `tools/check_fake_green_tests.py` 的模块 docstring：
`return True / return False` 的用例体会让 pytest 忽略真实结果——危险型（整套逻辑包在
try/except 里、失败只 print）会**打印 ❌ 却报 passed**，本仓实测 37 处、横跨 20 个文件。

本文件把「只许降不许升」变成一条会失败的断言（与 `tests/test_layer_purity.py` 同构）：
- 新增一处假绿灯 → 本文件变红；
- 清掉一处后忘了下调基线 → 也变红（防基线虚高、防"看着干净其实没清"）；
- 扫描器本身再用一个合成样本自检，防止门禁空转。
"""
from __future__ import annotations

import pathlib
import textwrap

from tools.check_fake_green_tests import (
    FAKE_GREEN_BASELINE,
    new_offenders,
    scan,
    scan_paths,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_no_new_fake_green_tests():
    """新增「用例体 return 值」必须失败——这正是 2026-10-04 那三条假绿灯的形态。"""
    found = scan(str(REPO_ROOT / "tests"))
    offenders = new_offenders(found)

    assert not offenders, (
        "新增假绿灯（用例体里 return 了值，pytest 会忽略它）：\n"
        + "\n".join(f"  {p}:{lines}  {n}" for p, n, lines in offenders)
        + "\n修法：把 return 改成 assert；若整体包在 try/except 里，先删掉 except 里的 return。"
    )


def test_baseline_has_no_stale_entries():
    """基线里不许留有「已经不存在」的条目——清一处就要同步下调基线。"""
    found = scan(str(REPO_ROOT / "tests"))
    present = {(path, name) for path, name, _ in found}
    stale = sorted(pair for pair in FAKE_GREEN_BASELINE if pair not in present)

    assert not stale, (
        "基线里这些条目已经不存在了，请从 tools/check_fake_green_tests.py 的 "
        f"FAKE_GREEN_BASELINE 中删除：{stale}"
    )


def test_scanner_detects_the_dangerous_shape(tmp_path):
    """扫描器自检：危险型（try/except + return False）与无害型（尾部 return True）都要被抓到。"""
    sample = tmp_path / "test_synthetic_fake_green.py"
    sample.write_text(
        textwrap.dedent(
            '''
            def test_dangerous_shape():
                try:
                    print("✅ 通过")
                    return True
                except Exception as exc:  # 失败只打印 → pytest 报 passed
                    print(f"❌ 失败: {exc}")
                    return False


            def test_harmless_tail_return():
                assert 1 + 1 == 2
                return True


            def test_nested_return_is_not_an_offender():
                """嵌套函数里的 return 不算——否则会把所有用闭包的用例误判。"""
                def helper():
                    return 42

                assert helper() == 42


            def test_clean_case():
                assert True
            '''
        ),
        encoding="utf-8",
    )

    hits = {(name) for _path, name, _lines in scan_paths([sample])}

    assert hits == {"test_dangerous_shape", "test_harmless_tail_return"}, hits
    assert "test_nested_return_is_not_an_offender" not in hits
    assert "test_clean_case" not in hits


def test_baseline_is_a_frozenset_of_pairs():
    """基线必须是 (文件, 用例名) 对——按对数冻结才能防「修一处、添一处」的等量替换。"""
    assert isinstance(FAKE_GREEN_BASELINE, frozenset)
    assert FAKE_GREEN_BASELINE, "基线不该为空（本仓实测有存量）"
    for pair in FAKE_GREEN_BASELINE:
        assert isinstance(pair, tuple) and len(pair) == 2, pair
        assert pair[0].startswith("tests/"), pair
