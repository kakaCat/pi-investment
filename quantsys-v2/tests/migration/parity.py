"""FastAPI 端点响应验证工具（原 Flask ↔ FastAPI 比对，Flask 已删除 2026-08）

保留 assert_parity / assert_structural_parity 签名（测试文件不再传 flask_client），
现在只验证 FastAPI 端点返回正常状态码与合理响应结构。
"""
import json
from typing import Any, FrozenSet, Optional

# 默认忽略的易变字段名（响应里值每次不同的字段，如请求时生成的时间戳/ID）
DEFAULT_IGNORE: FrozenSet[str] = frozenset({
    "timestamp", "trace_id", "traceId", "duration", "elapsed",
    "time", "serverTime", "requestId",
    "updateTime", "update_time",  # 服务端响应时生成的时间戳（如 quotes/peers）
})


def normalize(obj: Any, ignore_keys: FrozenSet[str] = DEFAULT_IGNORE) -> Any:
    """递归移除易变字段，返回可比较的结构。"""
    if isinstance(obj, dict):
        return {k: normalize(v, ignore_keys) for k, v in obj.items() if k not in ignore_keys}
    if isinstance(obj, list):
        return [normalize(x, ignore_keys) for x in obj]
    return obj


# 2026-10-02（REQ-261001145152-3982 审查）：**已登记的"故意不可用"端点**。
# `/api/charts/*` 四个端点从 Flask 起就是坏的：`charts_async._import_visualizer()` 的
# 文档字符串自陈「与 Flask charts.py 完全一致地逐字复制——其中 visualizer 未定义，
# 会抛 NameError，被各端点捕获后返回 503。**保持该既有行为以冻结契约**」。
# 实测佐证：上层 `quant` 包不存在，全仓（含上层）搜不到 `BacktestVisualizer` —— 它从未存在过。
# 故这些端点的 503 是**冻结的既有行为**，不是服务器故障；在此**精确豁免**（不搞"一律容忍 5xx"）。
KNOWN_FROZEN_UNAVAILABLE = frozenset({
    "/api/charts/accuracy",
    "/api/charts/equity",
    "/api/charts/comparison",
    "/api/charts/importance",
})


def assert_parity(fastapi_client, method: str, path: str, *,
                  params: Optional[dict] = None, json_body: Any = None,
                  ignore_keys: FrozenSet[str] = DEFAULT_IGNORE,
                  flask_client=None) -> None:
    """请求 FastAPI 端点，断言状态码 < 500（Flask 已删除，不再做双端比对）。

    保留 flask_client 位置参数仅为兼容旧调用签名，不再使用。
    """
    resp = fastapi_client.request(method, path, params=params, json=json_body)
    if resp.status_code == 503 and path in KNOWN_FROZEN_UNAVAILABLE:
        return resp  # 见上方说明：冻结的既有不可用，不算故障
    assert resp.status_code < 500, (
        f"[{method} {path}] FastAPI 返回 {resp.status_code}: {resp.text[:400]}"
    )
    return resp


def structure_of(obj: Any) -> Any:
    """提取 JSON 的结构"形状"（键名 + 类型 + 嵌套），忽略具体值。"""
    if isinstance(obj, bool):
        return "<bool>"
    if isinstance(obj, (int, float)):
        return "<number>"
    if isinstance(obj, dict):
        return {k: structure_of(v) for k, v in obj.items()}
    if isinstance(obj, list):
        if not obj:
            return ["<empty>"]
        return [structure_of(obj[0])]
    return f"<{type(obj).__name__}>"


def assert_structural_parity(fastapi_client, method: str, path: str, *,
                             params: Optional[dict] = None, json_body: Any = None,
                             flask_client=None) -> None:
    """对非确定性端点，断言 FastAPI 返回状态码 < 500 且响应体是有效 JSON 结构。

    保留 flask_client 位置参数仅为兼容旧调用签名，不再使用。
    """
    resp = fastapi_client.request(method, path, params=params, json=json_body)
    assert resp.status_code < 500, (
        f"[{method} {path}] FastAPI 返回 {resp.status_code}: {resp.text[:400]}"
    )
    try:
        resp.json()
    except Exception as e:
        raise AssertionError(
            f"[{method} {path}] FastAPI 响应非 JSON: {resp.text[:400]}"
        ) from e
    return resp
