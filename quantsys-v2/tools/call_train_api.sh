#!/bin/bash
# 直接调用训练API（后台运行，避免HTTP超时）

echo "=== 调用训练API（lightgbm，100股） ==="
echo "这将在后台运行，请通过日志监控进度"
echo ""

curl -X POST http://localhost:5001/api/ml/train \
  -H "Content-Type: application/json" \
  -d '{
    "model_type": "lightgbm",
    "start_date": "2025-09-04",
    "end_date": "2026-08-20",
    "symbols": ["600519","000001","600737","000002","600036","601318","600276","600887","601888","601398","600028","601939","601012","600016","600030","600048","601166","600050","600104","600115"],
    "test_size": 0.2
  }' \
  -m 600 \
  2>&1 | tee /tmp/train-api-call.log

echo ""
echo "完成时间: $(date)"
