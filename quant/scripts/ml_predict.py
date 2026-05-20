#!/usr/bin/env python3
"""
ML预测脚本（HTTP 客户端版）

功能：
1. 通过 Flask API 批量获取所有股票的 ML 预测
2. 保存预测结果到 JSON 文件
3. 展示统计摘要

前置条件: Flask API 服务运行在 localhost:5001
"""

import os
import sys
import json
import logging
from datetime import datetime
import requests

API_BASE = "http://localhost:5001"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def check_api_health() -> bool:
    """检查 API 是否可用"""
    try:
        resp = requests.get(f"{API_BASE}/api/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if not data.get('model_loaded'):
                logger.error("❌ API 模型未加载")
                return False
            return True
        return False
    except requests.ConnectionError:
        logger.error(f"❌ 无法连接到 API 服务 ({API_BASE})")
        logger.info("   请先启动: python3 quant/api/server.py")
        return False


def get_all_symbols() -> list:
    """从 API 获取所有 A 股股票代码"""
    try:
        resp = requests.get(f"{API_BASE}/api/stocks/list", params={'market': 'A', 'has_data': True}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return [s['symbol'] for s in data.get('stocks', [])]
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        return []


def predict_batch(symbols: list) -> dict:
    """批量预测（通过 API）"""
    try:
        resp = requests.post(
            f"{API_BASE}/api/ml/predict-batch",
            json={'symbols': symbols},
            timeout=600  # 10分钟超时，批量预测可能较慢
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"批量预测失败: {e}")
        return {}


def save_predictions(predictions: list, date: str, output_path: str):
    """保存预测结果到 JSON 文件"""
    up_count = sum(1 for p in predictions if p['direction'] == 'UP')
    down_count = len(predictions) - up_count
    high_conf = sum(1 for p in predictions if p['confidence'] > 0.7)

    output = {
        'generated_at': datetime.now().isoformat(),
        'date': date,
        'summary': {
            'total': len(predictions),
            'up': up_count,
            'down': down_count,
            'high_confidence': high_conf
        },
        'predictions': predictions
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ 预测结果已保存到: {output_path}")


def main():
    logger.info("=" * 60)
    logger.info("ML预测任务开始 (HTTP API 模式)")
    logger.info("=" * 60)

    # 1. 检查 API 健康
    if not check_api_health():
        return

    # 2. 获取股票列表
    symbols = get_all_symbols()
    if not symbols:
        logger.error("❌ 无法获取股票列表")
        return

    logger.info(f"共 {len(symbols)} 只股票需要预测")

    # 3. 批量预测
    logger.info("开始批量预测...")
    result = predict_batch(symbols)

    if not result or 'predictions' not in result:
        logger.error("❌ 预测失败，无结果返回")
        return

    predictions = result['predictions']
    date = result.get('date', 'unknown')

    logger.info("")
    logger.info("=" * 60)
    logger.info("预测完成")
    logger.info(f"成功预测: {len(predictions)} 只股票")
    logger.info("=" * 60)

    # 4. 保存结果
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '.pi-invest'
    )
    output_path = os.path.join(output_dir, 'ml_predictions.json')
    save_predictions(predictions, date, output_path)

    # 5. 统计摘要
    up_predictions = [p for p in predictions if p['direction'] == 'UP']
    down_predictions = [p for p in predictions if p['direction'] == 'DOWN']
    high_confidence = [p for p in predictions if p['confidence'] > 0.7]

    logger.info(f"\n📊 预测统计:")
    logger.info(f"  总数: {len(predictions)}")
    if predictions:
        logger.info(f"  看涨: {len(up_predictions)} ({len(up_predictions)/len(predictions)*100:.1f}%)")
        logger.info(f"  看跌: {len(down_predictions)} ({len(down_predictions)/len(predictions)*100:.1f}%)")
    logger.info(f"  高置信度 (>0.7): {len(high_confidence)}")

    # Top 看涨
    if up_predictions:
        logger.info("\n📈 Top 10 看涨股票:")
        for i, pred in enumerate(up_predictions[:10], 1):
            logger.info(f"  {i}. {pred['symbol']} | "
                       f"概率: {pred['probability']:.2%} | "
                       f"置信度: {pred['confidence']:.2%}")

    # Top 看跌
    if down_predictions:
        logger.info("\n📉 Top 10 看跌股票:")
        down_sorted = sorted(down_predictions, key=lambda x: x['probability'])[:10]
        for i, pred in enumerate(down_sorted, 1):
            logger.info(f"  {i}. {pred['symbol']} | "
                       f"上涨概率: {pred['probability']:.2%} | "
                       f"置信度: {pred['confidence']:.2%}")


if __name__ == '__main__':
    main()
