#!/usr/bin/env python3
"""
QuantSys V13 Scheduler Daemon - 企业级调度服务守护进程

功能：
1. 启动UnifiedSchedulerService调度器
2. 从数据库加载所有启用的任务配置
3. 动态导入并注册Job函数
4. 保持进程运行，提供优雅退出
5. 支持热重载（重新加载任务配置）

使用：
    python3 scheduler_daemon.py               # 前台运行
    python3 scheduler_daemon.py --daemon      # 后台运行
    python3 scheduler_daemon.py --reload      # 重新加载任务
"""
import sys
import signal
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Callable
import importlib

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from application.services.unified_scheduler import UnifiedSchedulerService
from adapters.outbound.repositories.scheduler_repository import SchedulerRepository

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/scheduler_daemon.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SchedulerDaemon:
    """调度器守护进程"""
    
    def __init__(self):
        self.scheduler_service = None
        self.repo = SchedulerRepository()
        self.running = False
        self.job_registry = {}  # {task_name: job_id}
        
    def _dynamic_import_job_func(self, command: str) -> Callable:
        """
        动态导入Job函数
        
        Args:
            command: 函数路径，如 "infrastructure.jobs.v13_trading_job.execute"
            
        Returns:
            可调用的函数对象
        """
        try:
            module_path, func_name = command.rsplit('.', 1)
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)
            return func
        except Exception as e:
            logger.error(f"Failed to import job function '{command}': {e}")
            raise
    
    def load_tasks(self):
        """从数据库加载所有启用的任务"""
        logger.info("Loading tasks from database...")
        
        try:
            # 获取所有启用的任务配置
            configs = self.repo.list_task_configs(enabled_only=True)
            
            logger.info(f"Found {len(configs)} enabled tasks")
            
            for config in configs:
                try:
                    # 动态导入Job函数
                    job_func = self._dynamic_import_job_func(config.command)
                    
                    # 添加到调度器
                    job_id = self.scheduler_service.add_cron_job(
                        func=job_func,
                        cron_expr=config.cron_expression,
                        job_id=config.task_name,
                        name=config.description or config.task_name,
                        kwargs=config.params or {},
                        executor=config.executor or 'default'
                    )
                    
                    self.job_registry[config.task_name] = job_id
                    
                    logger.info(f"✓ Task loaded: {config.task_name}")
                    logger.info(f"  Description: {config.description}")
                    logger.info(f"  Schedule: {config.cron_expression}")
                    logger.info(f"  Command: {config.command}")
                    
                except Exception as e:
                    logger.error(f"✗ Failed to load task '{config.task_name}': {e}")
                    continue
            
            logger.info(f"Successfully loaded {len(self.job_registry)} tasks")
            
        except Exception as e:
            logger.error(f"Failed to load tasks from database: {e}")
            raise
    
    def reload_tasks(self):
        """重新加载任务配置"""
        logger.info("Reloading tasks...")
        
        try:
            # 移除所有现有任务
            for task_name in list(self.job_registry.keys()):
                try:
                    self.scheduler_service.remove_job(task_name)
                    logger.info(f"Removed task: {task_name}")
                except Exception as e:
                    logger.warning(f"Failed to remove task '{task_name}': {e}")
            
            self.job_registry.clear()
            
            # 重新加载
            self.load_tasks()
            
            logger.info("Tasks reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload tasks: {e}")
            raise
    
    def start(self):
        """启动调度器守护进程"""
        logger.info("="*70)
        logger.info("QuantSys V13 Scheduler Daemon Starting...")
        logger.info("="*70)
        
        try:
            # 初始化调度服务
            logger.info("Initializing UnifiedSchedulerService...")
            self.scheduler_service = UnifiedSchedulerService()
            
            # 加载任务配置
            self.load_tasks()
            
            # 注册日常编排器（状态机驱动每日投资循环）
            self._register_orchestrator()

            # 注册 WatchEngine 实时盯盘引擎（后台线程）
            self._register_watch_engine()
            
            # 启动调度器
            logger.info("Starting scheduler...")
            self.scheduler_service.start()
            
            self.running = True
            
            logger.info("="*70)
            logger.info("✓ Scheduler Daemon Started Successfully")
            logger.info(f"  Tasks loaded: {len(self.job_registry)}")
            logger.info(f"  Scheduler running: {self.scheduler_service.scheduler.running}")
            logger.info(f"  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("="*70)
            
            # 保持运行
            self._keep_running()
            
        except Exception as e:
            logger.error(f"Failed to start scheduler daemon: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    def _register_orchestrator(self):
        """注册日常编排器和盘中监控到调度器"""
        try:
            from application.services.daily_orchestrator import get_daily_orchestrator
            
            orchestrator = get_daily_orchestrator()
            
            # 每分钟 tick（工作日 08:00-17:59）
            self.scheduler_service.add_cron_job(
                func=orchestrator.tick,
                job_id='daily_orchestrator_tick',
                name='日常编排器 Tick',
                minute='*',
                hour='8-17',
                day_of_week='mon-fri',
            )
            
            # 进程启动时尝试断点续跑
            orchestrator.resume_from_breakpoint()
            
            logger.info("✓ DailyOrchestrator registered")
            
        except Exception as e:
            logger.error(f"Failed to register DailyOrchestrator: {e}")

        # 注册盘中监控
        try:
            from application.services.intraday_monitor import get_intraday_monitor
            
            monitor = get_intraday_monitor()
            
            # 上午 09:30-11:30 每30分钟
            self.scheduler_service.add_cron_job(
                func=monitor.check,
                job_id='intraday_monitor_am',
                name='盘中监控(上午)',
                minute='0,30',
                hour='9-11',
                day_of_week='mon-fri',
            )
            
            # 下午 13:00-15:00 每30分钟
            self.scheduler_service.add_cron_job(
                func=monitor.check,
                job_id='intraday_monitor_pm',
                name='盘中监控(下午)',
                minute='0,30',
                hour='13-14',
                day_of_week='mon-fri',
            )
            
            logger.info("✓ IntradayMonitor registered")
            
        except Exception as e:
            logger.error(f"Failed to register IntradayMonitor: {e}")

    def _register_watch_engine(self):
        """注册 WatchEngine 实时盯盘引擎（后台线程）"""
        try:
            from application.services.watch_engine.factory import start_watch_engine_in_thread
            start_watch_engine_in_thread()
        except Exception as e:
            logger.error(f"Failed to register WatchEngine: {e}")

    def _keep_running(self):
        """保持进程运行"""
        logger.info("Scheduler daemon is running. Press Ctrl+C to stop.")
        
        try:
            while self.running:
                time.sleep(60)  # 每分钟心跳一次
                
                # 健康检查
                if not self.scheduler_service.scheduler.running:
                    logger.error("Scheduler stopped unexpectedly, restarting...")
                    self.scheduler_service.start()
                    
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            self.stop()
    
    def stop(self):
        """停止调度器"""
        logger.info("Stopping scheduler daemon...")
        
        self.running = False
        
        if self.scheduler_service:
            self.scheduler_service.shutdown(wait=True)
        
        logger.info("✓ Scheduler daemon stopped")
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='QuantSys V13 Scheduler Daemon')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('--reload', action='store_true', help='Reload tasks')
    args = parser.parse_args()
    
    daemon = SchedulerDaemon()
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, daemon._signal_handler)
    signal.signal(signal.SIGTERM, daemon._signal_handler)
    
    if args.reload:
        logger.info("Reloading tasks...")
        daemon.start()
        daemon.reload_tasks()
        logger.info("Tasks reloaded")
    else:
        daemon.start()


if __name__ == '__main__':
    main()
