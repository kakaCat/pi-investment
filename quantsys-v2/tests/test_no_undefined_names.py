"""未定义名守卫（2026-09-14 w-c8cae280）——作用域：**生产代码**

为什么要有它（根因）：仓里没有 ruff/pyflakes/flake8，"用了但没定义"的名字无人拦截。
实证（2026-09-13 起连查）：
  - adapters/.../quantlib/akshare_adapter.py 用 logger 26 次只在某方法内局部定义过 →
    NameError，**且崩在 except 块内把真实异常掩盖**（排障时永远看不到真正原因）；
  - application/services/attribution_analyzer.py 用了 Optional 却未导入 → **模块本身 import 不了**，
    而它在 service_registry 里被注册为服务 → 解析该服务的路径全部失败；
  - application/services/order_service.py 调用 _update_position_on_buy(ds, ...)：多传了一个不存在的
    ds、真实签名没有它 → 参数整体错位；
  - domain/quantlib/ml/factor_mining.py 在 "except ImportError: raise DependencyError(...)" 里用未导入的
    DependencyError → 真缺依赖时抛的是 NameError，把"请安装 scikit-learn"掩盖掉；
  - infrastructure/services/service_registry.py 的工厂闭包用了未导入的 IStockRepository；
  - adapters/shared/pipeline_exec.py 用了未导入的 sanitize_for_json（每次流水线收尾都会炸）。
以上全部为**真实缺陷**，已修；本测试把检查器接进常规套件，防止复发。

作用域说明（诚实标注，不假装全绿）：
  - 生产目录（application/ domain/ infrastructure/ adapters/）**必须干净**，否则本测试失败；
  - docs/ 是示例片段、scripts/ 与部分 tests/ 是历史脚本 —— 它们里面还有若干未定义名，
    其中多个引用的类**在当前代码库里根本不存在**（如 AsyncKlineORMRepository /
    StrategyPerformanceORMRepository），属"引用已消失的 API"，需要**删除或重写**的归属决策，
    不是加一行 import 能解决的；故暂不纳入闸门，已在报告里逐条列出。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.check_undefined_names import scan_file  # noqa: E402

PRODUCTION_DIRS = ["application", "domain", "infrastructure", "adapters"]


def test_no_undefined_names_in_production_code():
    findings = []
    for d in PRODUCTION_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for py in base.rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            for ln, name in scan_file(py):
                findings.append("%s:%d  %s" % (py.relative_to(ROOT), ln, name))
    assert not findings, (
        "生产代码发现 %d 处未定义名（用了但本作用域与模块级都没绑定）：\n  %s\n"
        "这类问题在运行时是 NameError，若发生在 except 块内还会**掩盖真实异常**。"
        % (len(findings), "\n  ".join(findings))
    )
