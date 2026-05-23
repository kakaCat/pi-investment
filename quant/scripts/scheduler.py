#!/usr/bin/env python3
"""
量化系统定时任务调度器（API 模式）

使用 APScheduler 管理所有定时任务，通过 Flask API 触发。
前置条件: Flask API 服务运行在 127.0.0.1:5002（可通过 QUANT_API_URL 环境变量覆盖）

运行方式：python3 scripts/scheduler.py
"""

import os
import sys
import logging
import time
import requests
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

API_BASE = os.getenv("QUANT_API_URL", "http://127.0.0.1:5002")

# 禁用代理
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(key, None)

# 添加项目路径（APScheduler 需要）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 日志
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


def wait_for_api(max_retries=30, delay=2):
    """等待 Flask API 就绪"""
    for i in range(max_retries):
        try:
            resp = requests.get(f"{API_BASE}/api/health", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"✅ API 就绪 (模型: {'已加载' if data.get('model_loaded') else '未加载'}, "
                          f"DB: {'已连接' if data.get('db_connected') else '未连接'})")
                return True
        except requests.ConnectionError:
            pass
        except Exception as e:
            logger.warning(f"API 检查异常: {e}")

        if i < max_retries - 1:
            logger.info(f"等待 API 就绪... ({i+1}/{max_retries})")
            time.sleep(delay)

    logger.error(f"❌ API 未能在 {max_retries * delay}s 内就绪")
    return False


def api_post(endpoint, json_data=None, timeout=1800):
    """调用 API POST 端点，返回结果"""
    try:
        resp = requests.post(f"{API_BASE}{endpoint}", json=json_data or {},
                           timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.error(f"API 返回 {resp.status_code}: {resp.text[:500]}")
            return None
    except requests.Timeout:
        logger.error(f"API 超时 ({endpoint})")
        return None
    except Exception as e:
        logger.error(f"API 调用失败 ({endpoint}): {e}")
        return None


# ============================================================================
# 任务函数（全部改为 API 调用）
# ============================================================================

def task_daily_update():
    """每日数据更新 - 16:00"""
    logger.info("=" * 60)
    logger.info("开始执行：每日数据更新 (API)")
    result = api_post('/api/data/update')
    if result and result.get('success'):
        logger.info("✅ 每日数据更新完成")
    else:
        logger.error(f"❌ 数据更新失败: {result}")
    logger.info("=" * 60)


def task_calculate_factors():
    """计算因子 - 16:30"""
    logger.info("=" * 60)
    logger.info("开始执行：计算因子 (API)")
    result = api_post('/api/compute/factors')
    if result and result.get('success'):
        logger.info("✅ 因子计算完成")
    else:
        logger.error(f"❌ 因子计算失败: {result}")
    logger.info("=" * 60)


def task_generate_signals():
    """生成交易信号 - 17:00"""
    logger.info("=" * 60)
    logger.info("开始执行：生成交易信号 (API)")
    result = api_post('/api/signals/generate', timeout=600)
    if result and result.get('success'):
        n_signals = len(result.get('signals', []))
        logger.info(f"✅ 交易信号生成完成 ({n_signals} 个信号)")
    else:
        logger.error(f"❌ 信号生成失败: {result}")
    logger.info("=" * 60)


def task_ml_predict():
    """ML模型预测 - 17:30"""
    logger.info("=" * 60)
    logger.info("开始执行：ML模型预测 (API)")

    # 先获取股票列表
    try:
        resp = requests.get(f"{API_BASE}/api/stocks/list", params={'market': 'A', 'has_data': True}, timeout=30)
        stocks = resp.json().get('stocks', [])
        symbols = [s['symbol'] for s in stocks]
        logger.info(f"共 {len(symbols)} 只股票")
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        logger.info("=" * 60)
        return

    result = api_post('/api/ml/predict-batch', json_data={'symbols': symbols}, timeout=1200)
    if result:
        logger.info(f"✅ ML预测完成 ({result.get('count', 0)} 只)")
    else:
        logger.error("❌ ML预测失败")
    logger.info("=" * 60)


def task_daily_report():
    """每日报告 - 18:00"""
    logger.info("=" * 60)
    logger.info("开始执行：生成每日报告 (API)")
    # 调用 daily_report.py（已改为 HTTP 客户端）
    import subprocess
    script = os.path.join(os.path.dirname(__file__), 'daily_report.py')
    result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=300)
    if result.returncode == 0:
        logger.info("✅ 每日报告生成完成")
    else:
        logger.error(f"❌ 报告生成失败: {result.stderr[:500]}")
    logger.info("=" * 60)


def task_risk_check():
    """风险检查 - 09:00"""
    logger.info("=" * 60)
    logger.info("开始执行：持仓风险检查 (API)")
    result = api_post('/api/risk/check', timeout=30)
    if result:
        level = result.get('risk_level', 'unknown')
        score = result.get('risk_score', 0)
        logger.info(f"✅ 风险检查完成 - 评分: {score}/100, 等级: {level}")
    else:
        logger.error("❌ 风险检查失败")
    logger.info("=" * 60)


def task_ml_retrain():
    """ML模型重训练 - 每周六 20:00（异步）"""
    logger.info("=" * 60)
    logger.info("开始执行：ML模型重训练 (API 异步)")
    result = api_post('/api/ml/retrain', timeout=30)
    if result and result.get('job_id'):
        job_id = result['job_id']
        logger.info(f"✅ 重训练已提交 - job_id: {job_id}")
        logger.info(f"   查询状态: GET /api/jobs/{job_id}")
    else:
        logger.error(f"❌ 重训练提交失败: {result}")
    logger.info("=" * 60)


def task_weekly_backtest():
    """策略回测 - 每周日 10:00（异步）"""
    logger.info("=" * 60)
    logger.info("开始执行：策略回测 (API 异步)")

    # 获取有数据的股票作为回测标的
    try:
        resp = requests.get(f"{API_BASE}/api/stocks/data-status", timeout=30)
        stocks = resp.json().get('stocks', [])
        # 选取部分有代表性和完整数据的股票
        symbols = [s['symbol'] for s in stocks[:5] if s.get('data_complete')]
        logger.info(f"回测标的: {symbols}")
    except Exception as e:
        symbols = ['000001', '600036', '600519']
        logger.warning(f"获取股票列表失败，使用默认标的: {symbols}")

    result = api_post('/api/backtest/run', json_data={'symbols': symbols}, timeout=30)
    if result and result.get('job_id'):
        job_id = result['job_id']
        logger.info(f"✅ 回测已提交 - job_id: {job_id}")
    else:
        logger.error(f"❌ 回测提交失败: {result}")
    logger.info("=" * 60)


def task_weekly_performance():
    """绩效分析 - 每周日 20:00"""
    logger.info("=" * 60)
    logger.info("开始执行：每周绩效分析 (API)")
    result = api_post('/api/performance/weekly')
    if result and result.get('success'):
        logger.info("✅ 绩效分析完成")
    else:
        logger.error(f"❌ 绩效分析失败: {result}")
    logger.info("=" * 60)


# ============================================================================
# 调度器配置
# ============================================================================

def main():
    logger.info("=" * 60)
    logger.info("量化系统定时任务调度器启动 (API 模式)")
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 等待 API 就绪
    if not wait_for_api():
        logger.error("❌ API 不可用，调度器退出")
        sys.exit(1)

    # 创建调度器
    scheduler = BlockingScheduler(timezone='Asia/Shanghai')

    # ========== 每日任务 ==========
    scheduler.add_job(task_daily_update,
        CronTrigger(hour=16, minute=0, day_of_week='mon-fri'),
        id='daily_update', name='每日数据更新')

    scheduler.add_job(task_calculate_factors,
        CronTrigger(hour=16, minute=30, day_of_week='mon-fri'),
        id='calculate_factors', name='计算因子')

    scheduler.add_job(task_generate_signals,
        CronTrigger(hour=17, minute=0, day_of_week='mon-fri'),
        id='generate_signals', name='生成交易信号')

    scheduler.add_job(task_ml_predict,
        CronTrigger(hour=17, minute=30, day_of_week='mon-fri'),
        id='ml_predict', name='ML模型预测')

    scheduler.add_job(task_daily_report,
        CronTrigger(hour=18, minute=0, day_of_week='mon-fri'),
        id='daily_report', name='生成每日报告')

    scheduler.add_job(task_risk_check,
        CronTrigger(hour=9, minute=0, day_of_week='mon-fri'),
        id='risk_check', name='持仓风险检查')

    # ========== 每周任务 ==========
    scheduler.add_job(task_ml_retrain,
        CronTrigger(hour=20, minute=0, day_of_week='sat'),
        id='ml_retrain', name='ML模型重训练')

    scheduler.add_job(task_weekly_backtest,
        CronTrigger(hour=10, minute=0, day_of_week='sun'),
        id='weekly_backtest', name='策略回测验证')

    scheduler.add_job(task_weekly_performance,
        CronTrigger(hour=20, minute=0, day_of_week='sun'),
        id='weekly_performance', name='每周绩效分析')

    # 打印任务
    logger.info("\n已配置的定时任务：")
    logger.info("-" * 60)
    for job in scheduler.get_jobs():
        logger.info(f"  [{job.id}] {job.name} → 下次: {job.next_run_time}")
    logger.info("-" * 60)

    try:
        logger.info("\n✅ 调度器已启动，按 Ctrl+C 停止")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("\n⚠️  正在关闭调度器...")
        scheduler.shutdown()
        logger.info("✅ 调度器已停止")


if __name__ == '__main__':
    main()
