"""
定时任务：每日股票池扫描

功能：
1. 每天16:05自动扫描所有股票池
2. 检测买入信号
3. 生成报告并通知
"""
import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

logger = structlog.get_logger(__name__)


class PoolScanScheduler:
    """股票池扫描定时任务调度器"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.is_running = False

    def start(self):
        """启动定时任务"""
        if self.is_running:
            logger.warning("扫描定时任务已在运行")
            return

        # 添加每日扫描任务
        self.scheduler.add_job(
            func=self._daily_scan_job,
            trigger=CronTrigger(
                hour=16,
                minute=5,
                day_of_week='mon-fri'  # 周一到周五
            ),
            id='daily_pool_scan',
            name='每日股票池扫描',
            replace_existing=True
        )

        self.scheduler.start()
        self.is_running = True
        logger.info("股票池扫描定时任务已启动：每天16:05执行")

    def stop(self):
        """停止定时任务"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("股票池扫描定时任务已停止")

    def _daily_scan_job(self):
        """每日扫描任务执行函数"""
        logger.info(f"开始每日股票池扫描 - {datetime.now()}")

        try:
            from application.services.pool_scanner_service import pool_scanner_service

            # 扫描所有股票池
            result = pool_scanner_service.scan_all_pools(
                strategy_ids=[272, 273],
                min_score=70
            )

            # 记录结果
            logger.info(f"扫描完成：扫描了 {result['pools_scanned']} 个股票池，"
                       f"发现 {result['total_signals']} 个买入信号")

            # 如果发现信号，发送通知
            if result['total_signals'] > 0:
                self._send_notification(result)

        except Exception as e:
            logger.error(f"每日扫描任务失败: {e}", exc_info=True)

    def _send_notification(self, scan_result: dict):
        """
        发送扫描结果通知

        Args:
            scan_result: 扫描结果
        """
        # TODO: 实现通知逻辑（邮件、飞书、钉钉等）
        logger.info(f"🎯 发现 {scan_result['total_signals']} 个买入机会！")

        for result in scan_result['results']:
            if result['signals_found'] > 0:
                logger.info(f"  {result['pool_name']}: {result['signals_found']}个信号")

    def trigger_scan_now(self):
        """立即触发一次扫描（测试用）"""
        logger.info("手动触发股票池扫描")
        self._daily_scan_job()


# 全局实例
pool_scan_scheduler = PoolScanScheduler()
