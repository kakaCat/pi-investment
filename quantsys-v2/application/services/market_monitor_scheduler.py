"""
市场监控定时任务
盘中每5分钟监控大盘异动，触发条件时通知 Agent

参考 pool_scan_scheduler.py 的模式实现
"""
import structlog
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from infrastructure.config import get_config

config = get_config()
LOG_FILE = config.app.market_monitor_log or '/tmp/market_monitor.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
logger = structlog.get_logger(__name__)


class MarketMonitorScheduler:
    """市场监控定时任务调度器"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.is_running = False

    def start(self):
        """启动市场监控任务"""
        if self.is_running:
            logger.warning("市场监控任务已在运行")
            return

        # 盘中每5分钟监控
        self.scheduler.add_job(
            func=self._market_monitor_job,
            trigger=CronTrigger(
                minute='*/5',
                hour='9-15',
                day_of_week='mon-fri'
            ),
            id='market-monitor',
            max_instances=1
        )

        self.scheduler.start()
        self.is_running = True
        logger.info("市场监控定时任务已启动")

    def stop(self):
        """停止监控任务"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("市场监控定时任务已停止")

    def _market_monitor_job(self):
        """市场监控任务执行函数"""
        logger.info(f"执行市场监控 - {datetime.now()}")

        try:
            # 1. 检查是否在静默时段
            if self._is_silent_time():
                logger.debug("当前在静默时段，跳过监控")
                return

            # 2. 获取市场数据
            sh_change = self._get_index_change('000001.SH')
            sz_change = self._get_index_change('399001.SZ')

            # 3. 检查是否触发告警条件
            threshold = 0.03  # 3%
            if abs(sh_change) > threshold or abs(sz_change) > threshold:
                logger.info(f"市场异动触发：上证 {sh_change:.2%}，深成 {sz_change:.2%}")

                data = {
                    'index': '000001.SH',
                    'sh_change': sh_change,
                    'sz_change': sz_change,
                    'timestamp': datetime.now().isoformat(),
                    'reason': '大盘异动超过阈值'
                }

                # 4. 通知 Agent
                from application.services.agent_notification_service import agent_service
                agent_service.notify_agent('market_alert', data)

        except Exception as e:
            logger.error(f"市场监控任务失败: {e}", exc_info=True)

    def _is_silent_time(self) -> bool:
        """检查是否在静默时段（11:30-13:00 午休）"""
        now = datetime.now()
        hour_float = now.hour + now.minute / 60.0
        return 11.5 <= hour_float < 13

    def _get_index_change(self, symbol: str) -> float:
        """获取指数涨跌幅

        TODO: 实现实际的数据获取逻辑
        可以调用 data service 获取实时行情
        """
        # 临时返回模拟数据
        return 0.0


# 全局实例
market_monitor_scheduler = MarketMonitorScheduler()
