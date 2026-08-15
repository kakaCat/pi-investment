#!/bin/bash
# Agent OS Scheduler Integration Test Script
# Tests the complete flow: registration -> trigger -> execution

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
AGENT_OS_URL="${AGENT_OS_URL:-http://localhost:8080}"
WEBHOOK_URL="${WEBHOOK_URL:-http://localhost:3002}"
AGENT_OWNER="${AGENT_OWNER:-fin-agent}"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Agent OS Scheduler Integration Test${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Step 1: Check Agent OS health
echo -e "${YELLOW}[1/6] Checking Agent OS health...${NC}"
if ! curl -sf "${AGENT_OS_URL}/health" > /dev/null; then
  echo -e "${RED}✗ Agent OS is not running at ${AGENT_OS_URL}${NC}"
  echo -e "${YELLOW}  Please start Agent OS first:${NC}"
  echo -e "${YELLOW}    cd agent-os && ./scripts/deploy.sh${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Agent OS is running${NC}"
echo ""

# Step 2: Check webhook endpoint health
echo -e "${YELLOW}[2/6] Checking webhook endpoint...${NC}"
if ! curl -sf "${WEBHOOK_URL}/api/health" > /dev/null 2>&1; then
  echo -e "${RED}✗ Webhook endpoint is not accessible at ${WEBHOOK_URL}${NC}"
  echo -e "${YELLOW}  Please start agent-ts first:${NC}"
  echo -e "${YELLOW}    cd agent-ts && npm run dev${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Webhook endpoint is accessible${NC}"
echo ""

# Step 3: List existing tasks
echo -e "${YELLOW}[3/6] Listing existing tasks...${NC}"
TASKS_JSON=$(curl -s "${AGENT_OS_URL}/api/v1/scheduler/tasks?owner=${AGENT_OWNER}")
TASK_COUNT=$(echo "$TASKS_JSON" | jq '. | length' 2>/dev/null || echo "0")
echo -e "  Found ${TASK_COUNT} registered tasks"

if [ "$TASK_COUNT" -gt 0 ]; then
  echo "$TASKS_JSON" | jq -r '.[] | "  - \(.name) (\(.cron))"' 2>/dev/null || echo "  (Error parsing tasks)"
fi
echo ""

# Step 4: Register a test task
echo -e "${YELLOW}[4/6] Registering test task...${NC}"
TEST_TASK_NAME="test_task_$(date +%s)"
TEST_PAYLOAD=$(cat <<EOF
{
  "name": "${TEST_TASK_NAME}",
  "owner": "${AGENT_OWNER}",
  "enabled": true,
  "cron": "0 */5 * * * *",
  "webhook_url": "${WEBHOOK_URL}/api/webhook/agent-os/trigger",
  "payload": {
    "kind": "agent_turn",
    "message": "Test scheduled task execution"
  },
  "timeout": 300,
  "retry_count": 1
}
EOF
)

REGISTER_RESPONSE=$(curl -s -X POST "${AGENT_OS_URL}/api/v1/scheduler/tasks" \
  -H "Content-Type: application/json" \
  -d "$TEST_PAYLOAD")

TASK_ID=$(echo "$REGISTER_RESPONSE" | jq -r '.id' 2>/dev/null)

if [ -z "$TASK_ID" ] || [ "$TASK_ID" = "null" ]; then
  echo -e "${RED}✗ Failed to register test task${NC}"
  echo -e "  Response: $REGISTER_RESPONSE"
  exit 1
fi

echo -e "${GREEN}✓ Test task registered${NC}"
echo -e "  Task ID: ${TASK_ID}"
echo -e "  Task Name: ${TEST_TASK_NAME}"
echo ""

# Step 5: Manually trigger the task
echo -e "${YELLOW}[5/6] Manually triggering test task...${NC}"
TRIGGER_RESPONSE=$(curl -s -X POST "${AGENT_OS_URL}/api/v1/scheduler/tasks/${TASK_ID}/trigger")
EXECUTION_ID=$(echo "$TRIGGER_RESPONSE" | jq -r '.execution_id' 2>/dev/null)

if [ -z "$EXECUTION_ID" ] || [ "$EXECUTION_ID" = "null" ]; then
  echo -e "${RED}✗ Failed to trigger test task${NC}"
  echo -e "  Response: $TRIGGER_RESPONSE"
  curl -s -X DELETE "${AGENT_OS_URL}/api/v1/scheduler/tasks/${TASK_ID}" > /dev/null
  exit 1
fi

echo -e "${GREEN}✓ Test task triggered${NC}"
echo -e "  Execution ID: ${EXECUTION_ID}"
echo ""

# Step 6: Wait for execution to complete and check status
echo -e "${YELLOW}[6/6] Waiting for execution to complete...${NC}"
MAX_WAIT=30
WAIT_COUNT=0

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
  EXECUTION_STATUS=$(curl -s "${AGENT_OS_URL}/api/v1/scheduler/executions/${EXECUTION_ID}" | jq -r '.status' 2>/dev/null)

  if [ "$EXECUTION_STATUS" = "completed" ]; then
    echo -e "${GREEN}✓ Execution completed successfully${NC}"
    break
  elif [ "$EXECUTION_STATUS" = "failed" ]; then
    echo -e "${RED}✗ Execution failed${NC}"
    ERROR_MSG=$(curl -s "${AGENT_OS_URL}/api/v1/scheduler/executions/${EXECUTION_ID}" | jq -r '.error' 2>/dev/null)
    echo -e "  Error: ${ERROR_MSG}"
    curl -s -X DELETE "${AGENT_OS_URL}/api/v1/scheduler/tasks/${TASK_ID}" > /dev/null
    exit 1
  elif [ "$EXECUTION_STATUS" = "running" ]; then
    echo -n "."
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
  else
    echo -e "${RED}✗ Unknown execution status: ${EXECUTION_STATUS}${NC}"
    curl -s -X DELETE "${AGENT_OS_URL}/api/v1/scheduler/tasks/${TASK_ID}" > /dev/null
    exit 1
  fi
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
  echo -e "${RED}✗ Execution timed out after ${MAX_WAIT} seconds${NC}"
  curl -s -X DELETE "${AGENT_OS_URL}/api/v1/scheduler/tasks/${TASK_ID}" > /dev/null
  exit 1
fi

echo ""

# Cleanup: Delete test task
echo -e "${YELLOW}Cleaning up test task...${NC}"
curl -s -X DELETE "${AGENT_OS_URL}/api/v1/scheduler/tasks/${TASK_ID}" > /dev/null
echo -e "${GREEN}✓ Test task deleted${NC}"
echo ""

# Summary
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ All integration tests passed!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "Test Summary:"
echo -e "  • Agent OS: ${GREEN}✓${NC} Running"
echo -e "  • Webhook: ${GREEN}✓${NC} Accessible"
echo -e "  • Task Registration: ${GREEN}✓${NC} Success"
echo -e "  • Task Trigger: ${GREEN}✓${NC} Success"
echo -e "  • Task Execution: ${GREEN}✓${NC} Completed"
echo ""
