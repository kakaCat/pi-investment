#!/usr/bin/env python3
"""
量化系统定时任务调度器

使用 APScheduler 管理所有定时任务，替代系统 crontab
运行方式：python3 scripts/scheduler.py
"""

import os
import sys
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# 禁用代理
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'scheduler.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# ============================================================================
# 任务函数定义
# ============================================================================

def task_daily_update():
    """每日数据更新 - 16:00"""
    logger.info("=" * 60)
    logger.info("开始执行：每日数据更新")
    try:
        from quantsys.data.db import Database
        from quantsys.data.fetchers.klines import KlineFetcher

        db_path = os.path.join(
            os.path.expanduser('~'),
            '.pi-invest', 'stock-db', 'stocks.db'
        )

        db = Database(db_path)
        fetcher = KlineFetcher(db)
        symbols = db.get_all_symbols(market='A')

        logger.info(f"共 {len(symbols)} 只股票需要更新")
        fetcher.run(symbols=symbols, days=5, market='A')

        logger.info("✅ 每日数据更新完成")
    except Exception as e:
        logger.error(f"❌ 每日数据更新失败: {e}", exc_info=True)
    logger.info("=" * 60)


def task_calculate_factors():
    """计算因子 - 16:30"""
    logger.info("=" * 60)
    logger.info("开始执行：计算因子")
    try:
        # 调用因子计算脚本
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), 'calculate_factors.py')
        result = subprocess.run(
            ['python3', script_path],
            capture_output=True,
            text=True,
            timeout=1800  # 30分钟超时
        )

        if result.returncode == 0:
            logger.info(result.stdout)
            logger.info("✅ 因子计算完成")
        else:
            logger.error(f"❌ 因子计算失败: {result.stderr}")
    except Exception as e:
        logger.error(f"❌ 因子计算失败: {e}", exc_info=True)
    logger.info("=" * 60)


def task_generate_signals():
    """生成交易信号 - 17:00"""
    logger.info("=" * 60)
    logger.info("开始执行：生成交易信号")
    try:
        # 调用信号生成脚本
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), 'generate_signals.py')
        result = subprocess.run(
            ['python3', script_path],
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )

        if result.returncode == 0:
            logger.info(result.stdout)
            logger.info("✅ 交易信号生成完成")
        else:
            logger.error(f"❌ 信号生成失败: {result.stderr}")
    except Exception as e:
        logger.error(f"❌ 信号生成失败: {e}", exc_info=True)
    logger.info("=" * 60)


def task_ml_predict():
    """ML模型预测 - 17:30"""
    logger.info("=" * 60)
    logger.info("开始执行：ML模型预测")
    try:
        # 调用ML预测脚本
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), 'ml_predict.py')
        result = subprocess.run(
            ['python3', script_path],
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )

        if result.returncode == 0:
            logger.info(result.stdout)
            logger.info("✅ ML预测完成")
        else:
            logger.error(f"❌ ML预测失败: {result.stderr}")
    except Exception as e:
        logger.error(f"❌ ML预测失败: {e}", exc_info=True)
    logger.info("=" * 60)


def task_daily_report():
    """每日报告 - 18:00"""
    logger.info("=" * 60)
    logger.info("开始执行：生成每日报告")
    try:
        # 调用报告生成脚本
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), 'daily_report.py')
        result = subprocess.run(
            ['python3', script_path],
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )

        if result.returncode == 0:
            logger.info(result.stdout)
            logger.info("✅ 每日报告生成完成")
        else:
            logger.error(f"❌ 报告生成失败: {result.stderr}")
    except Exception as e:
        logger.error(f"❌ 报告生成失败: {e}", exc_info=True)
    logger.info("=" * 60)


def task_risk_check():
    """风险检查 - 09:00"""
    logger.info("=" * 60)
    logger.info("开始执行：持仓风险检查")
    try:
        # 调用风险检查脚本
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), 'risk_check.py')
        result = subprocess.run(
            ['python3', script_path],
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )

        if result.returncode == 0:
            logger.info(result.stdout)
            logger.info("✅ 风险检查完成")
        else:
            logger.error(f"❌ 风险检查失败: {result.stderr}")
    except Exception as e:
        logger.error(f"❌ 风险检查失败: {e}", exc_info=True)
    logger.info("=" * 60)


def task_ml_retrain():
    """ML模型重训练 - 每周六 20:00"""
    logger.info("=" * 60)
    logger.info("开始执行：ML模型重训练")
    try:
        # 调用ML重训练脚本
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), 'ml_retrain.py')
        result = subprocess.run(
            ['python3', script_path],
            capture_output=True,
            text=True,
            timeout=3600  # 60分钟超时
        )

        if result.returncode == 0:
            logger.info(result.stdout)
            logger.info("✅ ML模型重训练完成")
        else:
            logger.error(f"❌ 模型重训练失败: {result.stderr}")
    except Exception as e:
        logger.error(f"❌ 模型重训练失败: {e}", exc_info=True)
    logger.info("=" * 60)


def task_weekly_backtest():
    """策略回测 - 每周日 10:00"""
    logger.info("=" * 60)
    logger.info("开始执行：策略回测验证")
    try:
        # 调用回测脚本
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), 'weekly_backtest.py')
        result = subprocess.run(
            ['python3', script_path],
            capture_output=True,
            text=True,
            timeout=1800  # 30分钟超时
        )

        if result.returncode == 0:
            logger.info(result.stdout)
            logger.info("✅ 策略回测完成")
        else:
            logger.error(f"❌ 回测失败: {result.stderr}")
    except Exception as e:
        logger.error(f"❌ 回测失败: {e}", exc_info=True)
    logger.info("=" * 60)


def task_weekly_performance():
    """绩效分析 - 每周日 20:00"""
    logger.info("=" * 60)
    logger.info("开始执行：每周绩效分析")
    try:
        # 调用绩效分析脚本
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), 'weekly_performance.py')
        result = subprocess.run(
            ['python3', script_path],
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )

        if result.returncode == 0:
            logger.info(result.stdout)
            logger.info("✅ 绩效分析完成")
        else:
            logger.error(f"❌ 绩效分析失败: {result.stderr}")
    except Exception as e:
        logger.error(f"❌ 绩效分析失败: {e}", exc_info=True)
    logger.info("=" * 60)


# ============================================================================
# 调度器配置
# ============================================================================

def main():
    """主函数 - 配置并启动调度器"""
    logger.info("=" * 60)
    logger.info("量化系统定时任务调度器启动")
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 创建调度器
    scheduler = BlockingScheduler(timezone='Asia/Shanghai')

    # ========== 每日任务（周一至周五） ==========

    # 1. 数据更新 - 16:00
    scheduler.add_job(
        task_daily_update,
        CronTrigger(hour=16, minute=0, day_of_week='mon-fri'),
        id='daily_update',
        name='每日数据更新'
    )

    # 2. 因子计算 - 16:30
    scheduler.add_job(
        task_calculate_factors,
        CronTrigger(hour=16, minute=30, day_of_week='mon-fri'),
        id='calculate_factors',
        name='计算因子'
    )

    # 3. 信号生成 - 17:00
    scheduler.add_job(
        task_generate_signals,
        CronTrigger(hour=17, minute=0, day_of_week='mon-fri'),
        id='generate_signals',
        name='生成交易信号'
    )

    # 4. ML预测 - 17:30
    scheduler.add_job(
        task_ml_predict,
        CronTrigger(hour=17, minute=30, day_of_week='mon-fri'),
        id='ml_predict',
        name='ML模型预测'
    )

    # 5. 每日报告 - 18:00
    scheduler.add_job(
        task_daily_report,
        CronTrigger(hour=18, minute=0, day_of_week='mon-fri'),
        id='daily_report',
        name='生成每日报告'
    )

    # 6. 风险检查 - 09:00（次日开盘前）
    scheduler.add_job(
        task_risk_check,
        CronTrigger(hour=9, minute=0, day_of_week='mon-fri'),
        id='risk_check',
        name='持仓风险检查'
    )

    # ========== 每周任务 ==========

    # 7. ML模型重训练 - 每周六 20:00
    scheduler.add_job(
        task_ml_retrain,
        CronTrigger(hour=20, minute=0, day_of_week='sat'),
        id='ml_retrain',
        name='ML模型重训练'
    )

    # 8. 策略回测 - 每周日 10:00
    scheduler.add_job(
        task_weekly_backtest,
        CronTrigger(hour=10, minute=0, day_of_week='sun'),
        id='weekly_backtest',
        name='策略回测验证'
    )

    # 9. 绩效分析 - 每周日 20:00
    scheduler.add_job(
        task_weekly_performance,
        CronTrigger(hour=20, minute=0, day_of_week='sun'),
        id='weekly_performance',
        name='每周绩效分析'
    )

    # 打印所有任务
    logger.info("\n已配置的定时任务：")
    logger.info("-" * 60)
    for job in scheduler.get_jobs():
        logger.info(f"  [{job.id}] {job.name}")
        logger.info(f"    下次运行: {job.next_run_time}")
    logger.info("-" * 60)

    # 启动调度器
    try:
        logger.info("\n✅ 调度器已启动，按 Ctrl+C 停止")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("\n⚠️  收到停止信号，正在关闭调度器...")
        scheduler.shutdown()
        logger.info("✅ 调度器已停止")


if __name__ == '__main__':
    main()
