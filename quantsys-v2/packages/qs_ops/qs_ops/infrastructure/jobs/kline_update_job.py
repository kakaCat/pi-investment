"""
K线数据更新Job - 使用多数据源自动更新

每日自动更新K线数据，支持多数据源fallback（tencent → akshare）

scope:
- all: 全市场（默认）。K线是全市场功能（机会扫描/市场情绪/行业分析）的
  共同上游——只更创业板会让其余 4500 只股票静默饿死（2026-07-28 定位：
  07-22 后全市场日更覆盖率从 1351 只逐日衰减到 1 只）
- gem: 仅创业板（旧行为，保留兼容）
"""
import os
import sys
import time
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径

from qs_market_data.adapters.outbound.datasources.manager import DataProviderManager
# 2026-09-13（w-32314d00，REQ-24e15d t4）：本作业原先自己持有 engine/raw_connection/cursor
# 与全部 SQL 文本（选股 4 个 scope + 写入 INSERT + 3 个自检查询），现全部收敛到
# adapters/outbound/repositories/kline_sync_repository.py —— 作业层只做编排、限速与告警。
# 下面两个阈值从仓储导入，保持"日志里报的阈值"与"仓储实际用的阈值"是同一个常量。
from adapters.outbound.repositories.kline_sync_repository import (
    AMOUNT_SCALE_THRESHOLD,
    KlineSyncRepository,
    VOLUME_CROSS_SECTION_THRESHOLD,
)

logger = logging.getLogger(__name__)

# 单次运行的墙钟预算（秒）。2026-10-21（w-36c3225e）实测：全市场 5277 只按
# interval 0.3~0.8s 限速 + 每只一次同步 HTTP，实测约 1.7s/只 ⇒ 单次跑完约
# 2.5 小时。这么长的一次占用会同时带来三个问题：
#   ① 进程重启后从头再来（每次都白跑前面已完成的 3000+ 只）；
#   ② 长时间占住一个 worker 线程与 DB 连接；
#   ③ 上游一旦中途限流，本次成果全部作废。
# 改为"跑满预算就收工、如实报部分完成"，下一轮（Agent OS 每天多次触发 /
# 手动补跑）从陈旧度排序继续往前推——select_sync_universe 本就按陈旧度排，
# 续跑的推进方向是对的。与 data_quality_check_job 的 DEFAULT_MAX_RUNTIME_SEC
# （1800）取同一口径，避免两套预算常量漂移。
DEFAULT_MAX_RUNTIME_SEC = 1800
# 预算检查粒度：每 N 只查一次时钟。查时钟本身有开销（time.monotonic 很便宜，
# 但取系统时间在容器里偶尔不便宜），不需要每只都查。
# 粒度必须与"每只耗时"相称——超支窗口 = 粒度 × 单只耗时。实测全市场单只
# 约 1.7s（含限速 sleep + 同步 HTTP + 落库），若固定按 25 只检查，超支可达
# 42s；按 10 只检查则 ≤17s。故取 10（兼顾时钟开销与超支窗口）。
_BUDGET_CHECK_EVERY = 10


def update_gem_klines(**params):
    """
    更新K线数据

    Args:
        **params: 任务参数
            - days: 更新最近N天的数据（默认5天）
            - symbols: 指定股票代码列表（可选）
            - scope: 同步范围（2026-09-02 更新）
              * 'batch': 分批轮转（P0+P1 必同步 + 按陈旧度补充 batch_size 只）
              * 'priority': 仅核心股票（P0+P1，约 300 只）
              * 'all': 全市场按陈旧度排序（约 5500 只）
              * 'gem': 仅创业板
            - batch_size: scope='batch' 时，除 P0+P1 外补充的最旧股票数量（默认 500）
            - interval_seconds: 每只股票请求间隔秒数区间 (low, high)，
              默认 (0.3, 0.8) 随机抖动（防 WAF 封禁——2026-07-28 实测
              间隔 0.05s 跑约770只后被断流；连空 50 只会自适应休眠 30s）。
              interval_seconds=0 关闭（测试/小批量用）
            - pause: （已废弃别名）等价于 interval_seconds=(pause, pause)
            - max_runtime_sec: 单次运行的墙钟预算（秒，默认 1800）。到点即
              收工并如实报"部分完成"（budget_exhausted=True），下一轮续跑。
              传 0 或负数表示不限时（仅调试用）。

    Returns:
        dict: 执行结果
    """
    scope = params.get('scope', 'all')
    batch_size = params.get('batch_size', 500)
    max_runtime_sec = params.get('max_runtime_sec', DEFAULT_MAX_RUNTIME_SEC)
    try:
        # 必须用 float——int() 会把 0.3 这类小数截断成 0，而 0 的语义是
        # "不限时"，等于把调用方给的预算静默变成了"无限制"（2026-10-21
        # 自测时踩到：传 0.3 被读成 0，预算形同虚设）。
        max_runtime_sec = float(max_runtime_sec)
    except (TypeError, ValueError):
        max_runtime_sec = float(DEFAULT_MAX_RUNTIME_SEC)
    if max_runtime_sec <= 0:
        max_runtime_sec = 0.0  # 0 = 不限时（调试用）

    logger.info("="*70)
    logger.info(f"K线数据更新任务开始 (scope={scope}, batch_size={batch_size if scope == 'batch' else 'N/A'})")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*70)

    days = params.get('days', 5)
    specific_symbols = params.get('symbols', None)
    # 请求限速：每只股票之间的间隔秒数区间（防 WAF 封禁，2026-07-28）
    # interval_seconds=0 关闭（测试/小批量用）；pause 为废弃别名
    pause = params.get('pause', None)
    default_interval = (0.3, 0.8) if pause is None else (float(pause), float(pause))
    interval = params.get('interval_seconds', default_interval)

    kline_repo = KlineSyncRepository()

    try:
        # 获取股票列表（选股 SQL 在仓储层，含退市 / 名称 / 6 位裸码形状 / 指数占位行过滤）
        stocks = kline_repo.select_sync_universe(scope, specific_symbols, batch_size)
        total = len(stocks)
        logger.info(f"需要更新: {total}只股票")

        # 计算日期范围
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        logger.info(f"日期范围: {start_date} -> {end_date}")

        # stale 校验的基准日：最近一个"应当已有 EOD 数据"的交易日。
        # 盘中/早盘/非交易日跑任务时，当天本来就没有日K，不能拿今天当
        # 基准（否则全部误报 stale，2026-07-31 回填时 4364 只全误报）。
        # 规则：今天是交易日且已过 15:00 → 今天；否则 → 上一个交易日。
        # 2026-09-11（w-f4aa1f6a 步2）：改用 TradingDayGuard（原为只判周末，
        # 节假日会把基准日判错，仅影响 stale 计数不影响入库）
        from qs_ops.application.services.trading_day_guard import TradingDayGuard

        now = datetime.now()
        target_date = end_date
        if not (TradingDayGuard.is_trading_day(now.date()) and now.hour >= 15):
            d = now.date() - timedelta(days=1)
            for _ in range(30):  # 最长回溯 30 天（春节等长假）
                if TradingDayGuard.is_trading_day(d):
                    break
                d -= timedelta(days=1)
            target_date = d.strftime('%Y-%m-%d')

        # 初始化数据源管理器
        manager = DataProviderManager()

        success = 0
        failed = 0
        skipped = 0
        stale = 0  # 数据有效但未覆盖到目标日期（如 baostock 当日 EOD 未发布）
        consecutive_empty = 0
        # 墙钟预算（2026-10-21 w-36c3225e）：全市场 5277 只实测约 1.7s/只
        # ⇒ 单次约 2.5 小时。超预算即收工，如实报"部分完成"，
        # 下一轮按陈旧度排序继续往前推（select_sync_universe 本就按陈旧度排）。
        budget_exhausted = False
        attempted = 0
        deadline = time.monotonic() + max_runtime_sec if max_runtime_sec else None

        for i, (symbol, name) in enumerate(stocks, 1):
            # 预算检查：每 N 只查一次时钟，避免在热循环里反复取时。
            if deadline is not None and (i - 1) % _BUDGET_CHECK_EVERY == 0:
                if time.monotonic() > deadline:
                    budget_exhausted = True
                    logger.warning(
                        f"⏱ 达到墙钟预算 {max_runtime_sec}s，已处理 {i - 1}/{total} 只，"
                        f"本次收工（部分完成），下一轮继续"
                    )
                    break
            # 2026-09-11 (w-23c70356) 写入侧兜底：daily_klines 只存 6 位 A 股裸码。
            # 选股 SQL 已过滤，此处兜住显式 symbols 入参（如 '600000.SH' 测试残留）——
            # 它们曾写出 1,213 行伪 K 线（含 4 只已退市代码的 2026 年"行情"）。
            if not (len(str(symbol)) == 6 and str(symbol).isdigit()):
                skipped += 1
                logger.warning(f"[{i}/{total}] 跳过非标准代码: {symbol}")
                continue
            # 限速：首只之前不 sleep
            if i > 1 and interval and interval[1] > 0:
                time.sleep(random.uniform(*interval))
            attempted += 1
            try:
                # 使用多数据源获取数据（自动fallback：tencent → akshare）
                # 注意：manager.get_klines 返回 {'success', 'data', 'source'} 字典，
                # data 是 KlineData 对象列表，不是 DataFrame（2026-07-23 修复
                # "'dict' object has no attribute 'iterrows'" 契约错位）
                result = manager.get_klines(
                    symbol,
                    'daily',
                    start_date,
                    end_date,
                )
                klines = result.get('data') if result.get('success') else None

                if not klines:
                    skipped += 1
                    consecutive_empty += 1
                    if consecutive_empty >= 50:
                        # 数据源大概率被限流，休眠冷却后重试这批
                        logger.warning(
                            f"连续 {consecutive_empty} 只无数据，疑似数据源限流，休眠 30s")
                        time.sleep(30)
                        consecutive_empty = 0
                    logger.debug(f"[{i}/{total}] {symbol} - 无数据")
                    continue

                consecutive_empty = 0

                # 插入数据库（2026-09-13 w-32314d00，REQ-24e15d t4：裸 INSERT → 仓储 ORM upsert）
                # 走 daily_klines 的唯一写入口，顺带获得三道原先作业层没有的护栏：
                # 指数行剔除 / 缺 stocks 元数据自动补建 / market 不可推断的标的跳过。
                inserted = kline_repo.upsert_fetched_klines(symbol, klines)
                if inserted is None:
                    failed += 1
                    logger.warning(f"[{i}/{total}] {symbol} - 入库失败，本只计 failed")
                    continue

                # 目标日期校验：数据有效但只到更早日期时（如 baostock 当日
                # EOD 尚未发布），仍入库但计为 stale 而非 success——避免
                # 07-29 式假成功（报"成功5268只"实际仅355只有当日数据）。
                # 基准是 target_date（最近已收盘交易日），不是 end_date
                latest_date = max(str(k.date)[:10] for k in klines)
                if latest_date < target_date:
                    stale += 1
                    if stale <= 5 or stale % 500 == 0:
                        logger.warning(
                            f"[{i}/{total}] {symbol} - 数据仅到 {latest_date}，"
                            f"未覆盖基准日 {target_date}")
                else:
                    success += 1

                if i % 200 == 0:
                    logger.info(f"进度: [{i}/{total}] 成功{success} 失败{failed} 跳过{skipped}")

            except Exception as e:
                failed += 1
                logger.warning(f"[{i}/{total}] {symbol} - 失败: {str(e)[:50]}")


        # 封禁/故障降级检测：样本足够且成功率过低时标记（2026-07-28）
        processed = success + failed + skipped + stale
        provider_health = 'ok'
        if processed >= 20 and success < processed * 0.5:
            provider_health = 'degraded'
            logger.critical(
                f"⚠️ K线数据源疑似被封/故障: {processed}只仅{success}只成功，"
                f"请检查 provider 状态（WAF/IP封禁）")

        # 陈旧数据预警：大量股票未覆盖基准日（通常意味着首选源当日
        # EOD 未发布，需要晚些补跑），不算任务失败但必须可见（2026-07-30）
        if stale > 0:
            logger.warning(
                f"⚠️ {stale}只股票数据未覆盖基准日 {target_date}"
                f"（上游 EOD 未发布），建议稍后补跑")

        # 成交额完整性自检（2026-09-10 立）：本 INSERT 是 daily_klines 的唯一
        # 写入路径（原样落 float(k.amount)），上游 provider 不返回 amount 时会
        # 静默写 0——新浪日线接口只有 volume 无 amount，2026-09-02 起其成为主源
        # 后全库累积 185 万行 amount=0/NULL。在此对本次同步覆盖的基准日做一次
        # 自检，让"成交额丢失"在写入当日就可见，而不是几周后在因子/回测层发现。
        amount_missing = kline_repo.count_missing_amount(target_date)
        if amount_missing:
            logger.critical(
                f"⚠️ {target_date} 有 {amount_missing} 行有成交量但 amount 为 0/NULL "
                f"——数据源未提供成交额，请核查 provider 的 KlineData.amount 契约")

        # 成交额量级异常自检（2026-09-10 w-23c70356 立）：量纲（手/股）错误不破坏
        # amount/volume/close 自洽性，既有 VWAP 自洽校验看不见，只能按"当日额 vs
        # 自身近期中位额"的离群度发现。实测 2026-07~08 科创板 2,110 行 volume 被
        # 放大 100 倍（688008 单日 14,881 亿元）、指数伪行 949 万亿元。
        amount_scale_anomalies = kline_repo.detect_amount_scale_anomalies(target_date)
        if amount_scale_anomalies:
            top = ", ".join(f"{a['symbol']} ×{a['multiple']:.0f}" for a in amount_scale_anomalies[:5])
            logger.critical(
                f"⚠️ {target_date} 有 {len(amount_scale_anomalies)} 行成交额超该股近期中位额 "
                f"{AMOUNT_SCALE_THRESHOLD:.0f} 倍，疑似量纲（手/股）错误或极端放量，需独立源复核: {top}")

        # 成交量量纲截面自检（2026-09-10 w-23c70356 立）：与上一条互补，捕捉
        # "连续多日整体放大导致时序中位数被污染"的量纲错（实测 08-14~08-27
        # 连续 10 个交易日、每天固定 196 只科创板标的 ×100）。
        volume_unit_anomalies = kline_repo.detect_volume_unit_anomalies(target_date)
        if volume_unit_anomalies:
            top = ", ".join(f"{a['symbol']} ×{a['multiple']:.0f}" for a in volume_unit_anomalies[:5])
            logger.warning(
                f"⚠️ {target_date} 有 {len(volume_unit_anomalies)} 行成交量超同日同板块中位水平 "
                f"{VOLUME_CROSS_SECTION_THRESHOLD:.0f} 倍，疑似量纲（手/股）错误，需独立源复核: {top}")

        result = {
            'action': 'kline_update',
            'status': 'success',
            'scope': scope,
            'timestamp': datetime.now().isoformat(),
            'provider_health': provider_health,
            'total': total,
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'stale': stale,
            # 2026-10-21（w-36c3225e）：预算到点提前收工时如实标记，避免
            # "只跑了 1/4 就报 success" 被下游当成全量完成（假成功工厂）。
            'budget_exhausted': budget_exhausted,
            'attempted': attempted,
            'max_runtime_sec': max_runtime_sec,
            'amount_missing': amount_missing,
            'amount_scale_anomalies': amount_scale_anomalies[:20],
            'volume_unit_anomalies': volume_unit_anomalies[:20],
            'date_range': f"{start_date} -> {end_date}",
            'target_date': target_date,
            'message': (
                f'K线更新完成: 成功{success}只, 失败{failed}只, 跳过{skipped}只, '
                f'未覆盖基准日{stale}只'
                + (f'；预算到点部分完成（已处理 {attempted}/{total} 只）'
                   if budget_exhausted else '')
            )
        }

        logger.info("="*70)
        if budget_exhausted:
            logger.info(
                f"⏱ K线更新部分完成 (scope={scope}, 已处理 {attempted}/{total}, "
                f"预算 {max_runtime_sec}s) —— 下一轮续跑"
            )
        else:
            logger.info(f"✅ K线更新完成 (scope={scope})")
        logger.info(f"  成功: {success}只")
        logger.info(f"  失败: {failed}只")
        logger.info(f"  跳过: {skipped}只")
        logger.info(f"  未覆盖基准日({target_date}): {stale}只")
        logger.info(f"  成交额缺失(volume>0 且 amount<=0): {amount_missing} 行")
        logger.info(f"  成交额量级异常(>{AMOUNT_SCALE_THRESHOLD:.0f}×近期中位): {len(amount_scale_anomalies)} 行")
        logger.info(f"  成交量量纲异常(>{VOLUME_CROSS_SECTION_THRESHOLD:.0f}×同日同板块中位): {len(volume_unit_anomalies)} 行")
        logger.info("="*70)

        return result

    except Exception as e:
        logger.error(f"❌ K线更新失败: {e}")
        import traceback
        traceback.print_exc()

        return {
            'action': 'kline_update',
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'message': 'K线更新失败'
        }



# Job注册点 - scheduler会调用这个函数
def execute(**params):
    """Scheduler调用的入口函数"""
    return update_gem_klines(**params)


if __name__ == '__main__':
    # 测试执行
    result = update_gem_klines(days=5)
    print(f"\n执行结果: {result}")
