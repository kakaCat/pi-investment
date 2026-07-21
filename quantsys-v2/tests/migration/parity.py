"""Flask ↔ FastAPI 响应比对工具"""
import json
from typing import Any, FrozenSet, Optional

# 默认忽略的易变字段名（响应里值每次不同的字段，如请求时生成的时间戳/ID）
DEFAULT_IGNORE: FrozenSet[str] = frozenset({
    "timestamp", "trace_id", "traceId", "duration", "elapsed",
    "time", "serverTime", "requestId",
    "updateTime", "update_time",  # 服务端响应时生成的时间戳（如 quotes/peers）
})


def normalize(obj: Any, ignore_keys: FrozenSet[str] = DEFAULT_IGNORE) -> Any:
    """递归移除易变字段，返回可比对的结构。
    dict 用 == 比较本就无序；list 保持顺序（顺序即契约的一部分）。
    """
    if isinstance(obj, dict):
        return {k: normalize(v, ignore_keys) for k, v in obj.items() if k not in ignore_keys}
    if isinstance(obj, list):
        return [normalize(x, ignore_keys) for x in obj]
    return obj


def assert_parity(flask_client, fastapi_client, method: str, path: str, *,
                  params: Optional[dict] = None, json_body: Any = None,
                  ignore_keys: FrozenSet[str] = DEFAULT_IGNORE) -> None:
    """用相同输入分别请求 Flask 与 FastAPI，断言状态码与响应体一致。"""
    flask_resp = flask_client.open(path, method=method, query_string=params, json=json_body)
    fa_resp = fastapi_client.request(method, path, params=params, json=json_body)

    assert fa_resp.status_code == flask_resp.status_code, (
        f"[{method} {path}] 状态码不一致: flask={flask_resp.status_code} "
        f"fastapi={fa_resp.status_code}\nflask={flask_resp.get_data(as_text=True)[:400]}\n"
        f"fastapi={fa_resp.text[:400]}"
    )

    try:
        flask_json = flask_resp.get_json()
    except Exception:
        flask_json = None
    try:
        fa_json = fa_resp.json()
    except Exception:
        fa_json = None

    # 任一方响应体非 JSON（如 Flask 500 HTML vs FastAPI 500 JSON）时，
    # 只能按状态码比对（既有 bug 导致的 5xx 两边框架错误格式不同属正常）。
    if flask_json is None or fa_json is None:
        assert fa_resp.status_code == flask_resp.status_code, (
            f"[{method} {path}] 状态码不一致(非JSON): flask={flask_resp.status_code} "
            f"fastapi={fa_resp.status_code}"
        )
        return

    f_norm = normalize(flask_json, ignore_keys)
    fa_norm = normalize(fa_json, ignore_keys)
    assert fa_norm == f_norm, (
        f"[{method} {path}] 响应体不一致:\n"
        f"flask  = {json.dumps(f_norm, ensure_ascii=False, default=str)[:800]}\n"
        f"fastapi= {json.dumps(fa_norm, ensure_ascii=False, default=str)[:800]}"
    )


def structure_of(obj: Any) -> Any:
    """提取 JSON 的结构"形状"（键名 + 类型 + 嵌套），忽略具体值。
    用于非确定性（mock/随机/实时）端点的结构比对。
    int 与 float 统一视为 <number>（随机数据整数/小数不定，避免假结构性不匹配）。"""
    if isinstance(obj, bool):
        return "<bool>"
    if isinstance(obj, (int, float)):
        return "<number>"
    if isinstance(obj, dict):
        return {k: structure_of(v) for k, v in obj.items()}
    if isinstance(obj, list):
        if not obj:
            return ["<empty>"]
        # 用第一个元素代表列表元素结构
        return [structure_of(obj[0])]
    return f"<{type(obj).__name__}>"


def assert_structural_parity(flask_client, fastapi_client, method: str, path: str, *,
                             params: Optional[dict] = None, json_body: Any = None) -> None:
    """对非确定性（mock/随机）端点，只比对响应结构与状态码，不比对具体值。"""
    flask_resp = flask_client.open(path, method=method, query_string=params, json=json_body)
    fa_resp = fastapi_client.request(method, path, params=params, json=json_body)

    assert fa_resp.status_code == flask_resp.status_code, (
        f"[{method} {path}] 状态码不一致: flask={flask_resp.status_code} fastapi={fa_resp.status_code}"
    )

    f_struct = structure_of(flask_resp.get_json())
    fa_struct = structure_of(fa_resp.json())
    assert fa_struct == f_struct, (
        f"[{method} {path}] 响应结构不一致:\n"
        f"flask  = {json.dumps(f_struct, ensure_ascii=False)[:600]}\n"
        f"fastapi= {json.dumps(fa_struct, ensure_ascii=False)[:600]}"
    )
