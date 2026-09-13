"""
财报时效性检查 Job

检查财务数据是否及时更新，超期未更新发送告警。

调度配置：
    task_name: financial_timeliness_check
    cron: 0 9 * * * (每日 09:00)
    command: infrastructure.jobs.financial_timeliness_check_job.execute
"""
import logging
import threading
from datetime import datetime, date, timedelta
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)


class AlertDeliveryError(RuntimeError):
    """告警未能送达外部渠道（区别于检查本身失败）。"""


# ── 自动重跑（2026-09-13，w-32314d00）────────────────────────────────────────
# 用户指令：「需要自动重跑」。此前本 job 只发告警、补数据要人工执行；
# 而 quant.balance_sheets 当时连写入通道都没有 → 告警每天响、数据永远不动。
# 现在：逾期即自动触发财报落库（利润表+资产负债表），每天最多一次，
# 后台线程执行（不阻塞调度线程），结果写日志；次日检查复测，仍逾期才继续告警。
_AUTO_REMEDIATION_LOCK = threading.Lock()
_last_auto_attempt_at: Optional[datetime] = None
AUTO_REMEDIATION_COOLDOWN_HOURS = 20

# 与 in-process 宿主 job_id 对齐：宿主当天已（正在）跑过就不再触发，避免双跑
_HOST_JOB_ID = 'financial_statements'

_REMEDIATION_TEXT = {
    'triggered': '已自动触发财报落库（利润表+资产负债表，后台执行，每天一次）',
    'cooling_down': '本日已自动触发过，冷却中（20h）',
    'already_today': '宿主今日已跑过，不重复触发',
    'disabled': '已关闭（dry_run 或显式关闭）',
}


def _already_attempted_today() -> bool:
    """今天是否已经触发过（宿主台账里当天有记录即算）。"""
    try:
        from infrastructure.persistence.orm.config import get_session
        from sqlalchemy import text
        session = get_session()
        row = session.execute(text(
            "SELECT status FROM quant.inprocess_job_runs "
            "WHERE job_id = :j AND run_date = CURRENT_DATE LIMIT 1"
        ), {'j': _HOST_JOB_ID}).fetchone()
        return row is not None
    except Exception as e:  # 台账不可读时不阻断补救（宁可多跑一次也不静默不修）
        logger.warning("读取 inprocess_job_runs 失败，跳过当天去重判断: %s", e)
        return False


def _run_statement_update() -> None:
    """后台重跑：把利润表 + 资产负债表刷到最新披露期。"""
    try:
        from infrastructure.jobs.financial_statement_update_job import execute as update_statements
        result = update_statements()
        logger.info("财报自动重跑完成: %s", result)
    except Exception as e:  # noqa: BLE001 后台线程异常不能外泄
        logger.error("财报自动重跑失败: %s", e, exc_info=True)


def _maybe_auto_remediate(check_result: Dict, runner=None) -> str:
    """逾期时自动重跑财报落库。

    Returns:
        str: triggered / cooling_down / already_today / disabled
    """
    global _last_auto_attempt_at
    if check_result.get('dry_run') or check_result.get('auto_remediate') is False:
        return 'disabled'
    now = datetime.now()
    with _AUTO_REMEDIATION_LOCK:
        if _last_auto_attempt_at is not None:
            age_h = (now - _last_auto_attempt_at).total_seconds() / 3600
            if age_h < AUTO_REMEDIATION_COOLDOWN_HOURS:
                return 'cooling_down'
        if _already_attempted_today():
            _last_auto_attempt_at = now
            return 'already_today'
        _last_auto_attempt_at = now

    thread = threading.Thread(
        target=(runner or _run_statement_update),
        name='financial-auto-remediate', daemon=True,
    )
    thread.start()
    logger.warning("财报超期 → 已自动触发财报重跑（后台线程，每天最多一次）")
    return 'triggered'


def execute(**params) -> Dict[str, Any]:
    """执行财报时效性检查

    Returns:
        dict: {success, latest_report_date, expected_report_date,
               is_overdue, days_overdue?, alert_sent?}
    """
    try:
        logger.info("="*70)
        logger.info("财报时效性检查开始")
        logger.info("="*70)

        # 1. 查询当前最新财报数据更新时间
        from infrastructure.persistence.orm.config import get_session
        from sqlalchemy import text

        session = get_session()
        result = session.execute(text("""
            SELECT MAX(updated_at) as last_update
            FROM quant.stocks
            WHERE market = 'A' AND roe IS NOT NULL
        """)).fetchone()

        if not result or not result[0]:
            logger.warning("无法确定最新财务数据更新时间")
            return {
                'success': False,
                'error': 'Unable to determine latest financial data update time'
            }

        last_update = result[0]

        # 2. 计算预期报告期和披露截止日期
        today = date.today()
        expected_report_date, disclosure_deadline = _calculate_expected_report(today)

        # 3. 查询实际最新报告期（从 balance_sheets 推断）
        actual_report = session.execute(text("""
            SELECT MAX(report_date) as latest_report
            FROM quant.balance_sheets
        """)).scalar()

        # 4. 判断是否超期
        grace_days = 7  # 缓冲期
        is_overdue = False
        days_overdue = 0

        if disclosure_deadline:
            overdue_date = disclosure_deadline + timedelta(days=grace_days)
            if today > overdue_date:
                # 超过截止日期+缓冲期
                if actual_report is None or actual_report < expected_report_date:
                    is_overdue = True
                    days_overdue = (today - overdue_date).days

        result_dict = {
            'success': True,
            'check_date': today.isoformat(),
            'latest_report_date': actual_report.isoformat() if actual_report else None,
            'expected_report_date': expected_report_date.isoformat(),
            'disclosure_deadline': disclosure_deadline.isoformat() if disclosure_deadline else None,
            'is_overdue': is_overdue,
            'days_overdue': days_overdue if is_overdue else 0,
            'last_data_update': last_update.isoformat() if last_update else None,
        }

        # 5. 发送告警（如果超期）——先自动重跑再告警，告警里带上补救状态
        if is_overdue:
            result_dict['auto_remediation'] = _maybe_auto_remediate(result_dict)
            # alert_sent 必须反映**真实投递结果**（2026-09-13，w-32314d00）：
            # 原实现无论投递成败都写 True —— 与"任务 success 但功能失败"同源的假成功。
            result_dict['alert_sent'] = _send_timeliness_alert(result_dict)
            logger.warning(f"⚠️ 财报数据超期 {days_overdue} 天未更新")
            if not result_dict['alert_sent']:
                # 让异常抛出来（2026-09-13，w-32314d00）：本 job 的职责就是"超期要告警"，
                # 告警没送达 = 职责没完成。此前只写日志 + 静默 success，
                # scheduler_tasks.last_status 一路记 success（09-12/09-13 两次都是），
                # 只有 error 事件台账能露出。现在显式失败，台账与 last_error 同步可见。
                raise AlertDeliveryError(
                    f"财报时效性告警未送达（expected={expected_report_date}，"
                    f"超期 {days_overdue} 天）：见日志/错误事件台账"
                )
        else:
            logger.info("✅ 财报数据时效性正常")
            result_dict['alert_sent'] = False

        logger.info(f"检查结果: 预期={expected_report_date}, 实际={actual_report}, 超期={is_overdue}")
        logger.info("="*70)

        return result_dict

    except Exception as e:
        logger.error(f"财报时效性检查失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


def _calculate_expected_report(today: date) -> Tuple[date, Optional[date]]:
    """计算预期报告期和披露截止日

    Args:
        today: 当前日期

    Returns:
        (expected_report_date, disclosure_deadline)
    """
    year = today.year
    month = today.month

    # Q1: 1-3月，截止 4月30日
    if 5 <= month <= 7:
        return (date(year, 3, 31), date(year, 4, 30))

    # Q2: 4-6月，截止 8月31日
    elif 9 <= month <= 10:
        return (date(year, 6, 30), date(year, 8, 31))

    # Q3: 7-9月，截止 10月31日
    elif 11 <= month <= 12:
        return (date(year, 9, 30), date(year, 10, 31))

    # Q4: 10-12月，截止次年4月30日
    elif 1 <= month <= 4:
        return (date(year - 1, 12, 31), date(year, 4, 30))

    # 当前处于披露窗口期内，暂不检查
    else:
        return (date(year, 3, 31), None)


def _send_timeliness_alert(check_result: Dict, facade=None) -> bool:
    """发送财报时效性告警：**日志留痕 + 外部投递（NotificationFacade）**

    Args:
        check_result: 检查结果字典
        facade: 通知门面（测试注入用）。None 时经 get_notification_facade() 取单例。

    Returns:
        bool: 外部渠道是否投递成功。False = 日志已留痕但**未送达**（调用方据此写
              alert_sent=False，避免"假成功"）。

    2026-09-13（w-32314d00）：本函数此前**只写日志**——日志没人主动看，等于告警没有送达
    （财报超期 6 天，告警本该 09-10 送达，实际直到 09-13 才被人工发现）。
    现按架构铁律接 NotificationFacade（SYSTEM_ALERT → policy 路由 agent+feishu），
    urgency=high。**禁止**绕过门面直连飞书 SDK / webhook。
    """
    try:
        message = f"""📅 财报时效性告警

⚠️ 财务数据超期未更新

当前日期: {check_result['check_date']}
预期报告期: {check_result['expected_report_date']}
实际报告期: {check_result['latest_report_date'] or '未知'}
披露截止: {check_result['disclosure_deadline']}
超期天数: {check_result['days_overdue']} 天
自动重跑: {_REMEDIATION_TEXT.get(check_result.get('auto_remediation'), '未触发')}

建议行动:
手动执行财务数据更新任务
cd /Users/yunpeng/pi-investment/quantsys-v2
python -m infrastructure.jobs.financial_data_update_job --report-date {check_result['expected_report_date'].replace('-', '')}
"""

        # 财报时效性告警落日志
        # TODO: 如需持久化告警到数据库，需先创建 system_logs 表
        #
        # 2026-09-13 修复（w-32314d00，事件 8006b7ea）：本模块的 logger 是**标准库**
        # logging.getLogger(__name__)（见文件头），不接受 structlog 风格的任意关键字参数
        # —— Logger.warning 只认 exc_info/stack_info/stacklevel/extra。
        # 原写法 logger.warning("financial_timeliness_alert", symbol=..., expected_date=...,
        # message=...) 必然抛 TypeError: Logger._log() got an unexpected keyword argument 'symbol'，
        # 又被本函数的 except 吞掉 → **告警正文从未落日志**，只留下"发送时效性告警失败"这条
        # error（错误事件只报症状、不报根因，于是 09-12/09-13 两次 09:00 各报一次）。
        # 另注：2026-09-11 w-f4aa1f6a 修的是同一调用点的 KeyError('symbol')
        # （check_result['symbol'] → .get(...,'全市场')），把失败点从"取值"挪到了"调用本身"
        # —— 打地鼠式修复会掩盖真正的缺陷（logger 类型不匹配）。
        logger.warning(
            "financial_timeliness_alert symbol=%s expected_date=%s\n%s",
            check_result.get('symbol', '全市场'),
            check_result['expected_report_date'],
            message,
        )

        # ② 外部投递：架构铁律——出站通知只能经 NotificationFacade
        #（application/notification/notification_facade.py），禁止直连飞书 SDK/webhook。
        if facade is None:
            from application.notification import get_notification_facade
            facade = get_notification_facade()

        delivered = bool(facade.send_card(
            title="📅 财报时效性告警：财务数据超期未更新",
            content=message,
            urgency='high',
        ))
        if delivered:
            logger.info(
                "财报时效性告警已投递 symbol=%s expected=%s channel=NotificationFacade",
                check_result.get('symbol', '全市场'),
                check_result['expected_report_date'],
            )
        else:
            # 投递失败必须是 error（会进 public.error_events 台账）——
            # 否则"告警静默失败"又要靠人工翻日志才能发现
            logger.error(
                "财报时效性告警投递失败：NotificationFacade 返回 False"
                "（日志已留痕但外部渠道未送达）expected=%s overdue_days=%s",
                check_result['expected_report_date'],
                check_result['days_overdue'],
            )
        return delivered

    except Exception as e:
        # exc_info=True：告警链路的异常必须带栈，否则只能看到"失败"看不到"为什么"
        logger.error("发送时效性告警失败: %s", e, exc_info=True)
        return False


if __name__ == '__main__':
    result = execute()
    print(result)
