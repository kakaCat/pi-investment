#!/bin/bash
# Test async Codex workflow

echo "Testing async Codex workflow..."

# 1. Submit async task
echo -e "\n1. Submitting async task..."
TASK_ID=$(curl -s -X POST http://localhost:8765/task/async \
  -H "Content-Type: application/json" \
  -d '{"prompt":"测试任务","workdir":"'$(pwd)'"}' | jq -r .taskId)

echo "Task ID: $TASK_ID"

# 2. Check status
echo -e "\n2. Checking task status..."
sleep 2
curl -s http://localhost:8765/result/async/$TASK_ID | jq

# 3. List all async results
echo -e "\n3. Listing all completed tasks..."
curl -s http://localhost:8765/results/async | jq

# 4. Check notification file
echo -e "\n4. Checking notification file..."
ls -lh bridge/codex/notifications/

echo -e "\n✅ Test complete"
