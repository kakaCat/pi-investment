"""计划 spec 的校验与归一（纯逻辑，无 I/O）

spec 五段（缺一段即拒，不收半成品）：
  targets    [{symbol, budget_pct, role}]   —— 当前版本仅支持恰好 1 个明确 symbol
  entry      {conditions: [...], combinator: all_of|any_of}
  exit       {stop_loss?: {type, value}, reduce_plan?: [{at_pct, sell_ratio}],
              invalidation?: str}   —— stop_loss 与 reduce_plan 至少其一
  monitoring {news?: bool, policy?: bool, sector_flow?: bool}
  schedule   {interval_sec?: int}

多标的/pool 暂不收：计划的持仓推进、关闭收敛与减仓批次当前都是单标语义；
先显式拒绝，避免静默生成「部分标的已关、部分还开着」的不完整计划。

校验只做**结构与值域**（缺段/空数组/类型/比例范围）；业务阈值上限（如单股 20%）
属账户宪法，留给交易层，不在本函数里发明第二套。
"""

from typing import Any, Dict, List

REQUIRED_SECTIONS = ("targets", "entry", "exit", "monitoring", "schedule")
COMBINATORS = ("all_of", "any_of")
EXIT_TYPES = ("pct", "price", "atr")


def validate_plan_spec(spec: Any) -> List[str]:
    """返回缺失/非法项列表（空 = 通过）。每项一句人话，路由层原样回给调用方。"""
    problems: List[str] = []
    if not isinstance(spec, dict):
        return ["spec 必须是对象"]
    for section in REQUIRED_SECTIONS:
        if section not in spec:
            problems.append("缺少必填段：%s" % section)
    if problems:
        return problems

    targets = spec.get("targets")
    if not isinstance(targets, list) or not targets:
        problems.append("targets 必须是非空数组")
    elif len(targets) != 1:
        problems.append("当前版本仅支持单标的计划：targets 必须恰好 1 项")
    else:
        t = targets[0]
        if not isinstance(t, dict) or not t.get("symbol"):
            problems.append("targets[0] 必须含明确 symbol（pool/多标的暂不支持）")
        else:
            bp = t.get("budget_pct")
            if bp is not None and (not isinstance(bp, (int, float)) or bp <= 0 or bp > 100):
                problems.append("targets[0].budget_pct 必须在 (0,100]")

    entry = spec.get("entry")
    if not isinstance(entry, dict):
        problems.append("entry 必须是对象")
    else:
        conds = entry.get("conditions")
        if entry.get("pending") is True:
            # 显式「入场条件待补」（core_plan 适配器用）：空条件合法，编译侧只编止损
            if conds not in (None, []):
                problems.append(
                    "entry.pending=true 时 conditions 必须为空（补条件请同时去掉 pending）"
                )
        elif not isinstance(conds, list) or not conds:
            problems.append("entry.conditions 必须是非空数组（或 entry.pending=true 声明待补）")
        if entry.get("combinator") not in COMBINATORS:
            problems.append("entry.combinator 必须是 all_of 或 any_of")

    exit_spec = spec.get("exit")
    if not isinstance(exit_spec, dict):
        problems.append("exit 必须是对象")
    else:
        sl = exit_spec.get("stop_loss")
        rp = exit_spec.get("reduce_plan")
        if sl is None and not rp:
            problems.append("exit 至少要有 stop_loss 或 reduce_plan 之一")
        if sl is not None:
            if not isinstance(sl, dict) or sl.get("type") not in EXIT_TYPES:
                problems.append("exit.stop_loss.type 必须是 %s 之一" % "/".join(EXIT_TYPES))
            elif not isinstance(sl.get("value"), (int, float)) or sl.get("value") <= 0:
                problems.append("exit.stop_loss.value 必须是正数")
        if rp:
            if not isinstance(rp, list):
                problems.append("exit.reduce_plan 必须是数组")
            else:
                for i, b in enumerate(rp):
                    if not isinstance(b, dict):
                        problems.append("exit.reduce_plan[%d] 必须是对象" % i)
                        continue
                    at = b.get("at_pct")
                    ratio = b.get("sell_ratio")
                    if not isinstance(at, (int, float)) or at <= 0:
                        problems.append("exit.reduce_plan[%d].at_pct 必须是正数" % i)
                    if not isinstance(ratio, (int, float)) or not (0 < ratio <= 1):
                        problems.append("exit.reduce_plan[%d].sell_ratio 必须在 (0,1]" % i)

    schedule = spec.get("schedule")
    if not isinstance(schedule, dict):
        problems.append("schedule 必须是对象")
    else:
        iv = schedule.get("interval_sec")
        if iv is not None and (not isinstance(iv, int) or isinstance(iv, bool) or iv < 1):
            problems.append("schedule.interval_sec 必须是 >=1 的整数秒或省略")

    return problems


def normalize_plan_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """写入口径归一：只做可逆的默认值补齐，不改用户显式值。"""
    out = dict(spec)
    out.setdefault("monitoring", {})
    out.setdefault("schedule", {})
    return out
