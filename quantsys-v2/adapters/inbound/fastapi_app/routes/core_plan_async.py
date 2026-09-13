"""core 建仓计划只读 API（B8，2026-09-13 w-a9ec14d7）

为什么需要这个接口：三个例行任务原先靠**硬编码文件路径**直读 `config/core_plan.json`
（agent-brain-core-plan 09:10 / agent-brain-candidate-hunt 08:45 / live-order-test）。
直读文件有三个问题：
  ① 路径知识散落在各任务提示词里；
  ② **读不出"陈不陈"**——周五的计划周一照样读得出来，内容看着完全正常；
  ③ core-plan 任务第 2 步要求"核对与当前持仓的差额"，而服务端从未产出过这个差额。

本接口把「计划全文 + 新鲜度 + 与当前持仓的机械差额」一次给全。**只读**：
不触发重新生成（生成参数集是已审批的，补跑走 POST /api/scheduler/tasks/337/trigger）。

⚠️ 本接口**刻意不使用 api_response()**：那个helper会递归把 key 转成驼峰，
会把计划自身的 `generated_at`/`weight_pct_of_core` 变成 `generatedAt`/`weightPctOfCore`——
于是**同一份计划出现两套 key 词汇表**（文件里蛇形、接口里驼峰），
读文件的三个任务与走接口的调用方看到的结构不一致，属"同一状态两种定义"的经典事故面
（本仓已因此出过真实故障：self_finalize 与 boot-recovery 对同一退出状态定义相反）。
故此处原样返回计划结构，只做 sanitize_for_json（NaN/日期安全），不转 key。
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import structlog

from adapters.inbound.fastapi_app.shared import sanitize_for_json

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Core Plan - 建仓计划"])


@router.get('/api/core-plan')
def get_core_plan(request: Request):
    """读取最新 core 建仓计划（只读：计划 + 新鲜度 + 与当前持仓的机械差额）

    查询参数：
      account  可选。缺省 = 计划文件自身记录的账户（计划只服务单一账户；
               显式传入不同账户时不计算跨账户差额，而是说明原因）。
    """
    from application.services.core_plan_service import plan_snapshot

    account = request.query_params.get('account')
    try:
        snapshot = plan_snapshot(account=account)
    except Exception as exc:  # noqa: BLE001 —— 读不到计划必须显式，不能返回空壳冒充"无计划"
        logger.error(f"读取 core 计划失败: {exc}", exc_info=True)
        return JSONResponse(
            content={"success": False, "error": "%s: %s" % (type(exc).__name__, exc)},
            status_code=500)
    # 200 + available=false 是**有意义的正常响应**（文件缺失/过期都能解释），
    # 让调用方拿到 unavailable_reason 而不是一个没有上下文的 5xx。
    return JSONResponse(content=sanitize_for_json({"success": True, "data": snapshot}))
