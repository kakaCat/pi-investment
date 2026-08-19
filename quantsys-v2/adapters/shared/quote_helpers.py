"""行情/K线失败诊断工具函数

从 Flask adapters/inbound/api/routes/quote_market.py 提取的纯函数，
供 FastAPI 路由与测试共用（Flask 已废弃，2026-08 删除）。
"""


def _quote_failure_suggestion(symbol: str, provider_errors: dict) -> str:
    """根据各数据源的具体失败原因，生成可行动的修复建议（供 agent 自我纠正）"""
    joined = ' '.join(provider_errors.values())
    hints = []

    code = symbol.split('.')[0]
    if symbol.endswith('.HK') or (code.isdigit() and len(code) <= 5):
        hints.append(
            f"疑似港股代码：本接口主要支持 6 位 A 股代码，港股请尝试 {code.zfill(5)}.HK 格式"
        )
    if any(k in joined for k in ('timeout', 'Timeout', 'Connection', 'RemoteDisconnected', '502', 'Max retries')):
        hints.append("存在网络型失败：数据源可能临时限流/封禁，可稍后重试")
    if code.isdigit() and len(code) == 6:
        hints.append("请检查代码是否正确、是否已上市/已退市")
    if not hints:
        hints.append("请检查代码格式（A股为 6 位数字，可带 .SH/.SZ 后缀）")
    hints.append("也可用 source=db 查询本地缓存（如有）")

    return '；'.join(hints)


def _kline_failure_suggestion(symbol: str, period: str, provider_errors: dict) -> str:
    """根据各数据源的具体失败原因，生成可行动的修复建议（供 agent 自我纠正）"""
    joined = ' '.join(provider_errors.values())
    hints = []

    if '无法映射' in joined:
        hints.append(
            "代码无法映射到任何数据源：A股个股为 60/68(沪)、00/30(深)、4/8/92(北) 开头；"
            "深市指数用 399xxx（如创业板指 399006、深成指 399001）；"
            "上证指数(000xxx段)与深市个股代码歧义，暂不支持"
        )
    if symbol.split('.')[0].startswith('000'):
        hints.append(
            "000xxx 按深市个股解析（000001=平安银行）；"
            "若你想查的是上证指数，当前不支持，可改用深市指数 399001"
        )
    if any(k in joined for k in ('timeout', 'Timeout', 'Connection', 'RemoteDisconnected', '502', 'Max retries')):
        hints.append("存在网络型失败：数据源可能临时限流/封禁，可稍后重试，或缩短日期范围")
    if '数据库无' in joined and len(provider_errors) > 1:
        hints.append("本地数据库无该代码缓存（指数/冷门标的属正常），关键在网络源是否可用")
    if period != 'daily':
        hints.append("周/月线由日线聚合，分钟线仅支持个股最近30天；可先用 daily 验证代码本身是否可取数")
    if not hints:
        hints.append("请检查：代码是否正确（6位数字）、是否已上市/已退市、日期范围内是否有交易")

    return '；'.join(hints)
