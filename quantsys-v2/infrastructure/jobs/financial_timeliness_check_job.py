"""
财报时效性检查 Job

检查财务数据是否及时更新，超期未更新发送告警。

调度配置：
    task_name: financial_timeliness_check
    cron: 0 9 * * * (每日 09:00)
    command: infrastructure.jobs.financial_timeliness_check_job.execute
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)


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

        # 5. 发送告警（如果超期）
        if is_overdue:
            _send_timeliness_alert(result_dict)
            result_dict['alert_sent'] = True
            logger.warning(f"⚠️ 财报数据超期 {days_overdue} 天未更新")
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


def _send_timeliness_alert(check_result: Dict) -> None:
    """发送财报时效性告警

    Args:
        check_result: 检查结果字典
    """
    try:
        message = f"""📅 财报时效性告警

⚠️ 财务数据超期未更新

当前日期: {check_result['check_date']}
预期报告期: {check_result['expected_report_date']}
实际报告期: {check_result['latest_report_date'] or '未知'}
披露截止: {check_result['disclosure_deadline']}
超期天数: {check_result['days_overdue']} 天

建议行动:
手动执行财务数据更新任务
cd /Users/yunpeng/pi-investment/quantsys-v2
python -m infrastructure.jobs.financial_data_update_job --report-date {check_result['expected_report_date'].replace('-', '')}
"""

        # 写入 system_logs
        from infrastructure.persistence.orm.config import get_session
        from sqlalchemy import text

        session = get_session()
        session.execute(text("""
            INSERT INTO system_logs (level, source, message, created_at)
            VALUES ('WARNING', 'financial_timeliness_check', :message, NOW())
        """), {'message': message})
        session.commit()

        logger.info("财报时效性告警已记录到 system_logs")

    except Exception as e:
        logger.error(f"发送时效性告警失败: {e}")


if __name__ == '__main__':
    result = execute()
    print(result)
