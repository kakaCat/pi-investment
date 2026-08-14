#!/bin/bash
# Test script for WP-6: Feishu Driver

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 WP-6: Feishu Driver Test Suite"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0

# Helper functions
pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
}

test_section() {
    echo ""
    echo "─────────────────────────────────────────────────────────"
    echo "📋 $1"
    echo "─────────────────────────────────────────────────────────"
}

# Check environment
test_section "Environment Setup"

if [ -z "$FEISHU_WEBHOOK_URL" ]; then
    fail "FEISHU_WEBHOOK_URL not set"
    echo "  Please set: export FEISHU_WEBHOOK_URL='https://open.feishu.cn/open-apis/bot/v2/hook/YOUR-KEY'"
    exit 1
else
    pass "FEISHU_WEBHOOK_URL is set"
fi

# Navigate to feishu-driver directory
cd drivers/feishu-driver || {
    fail "drivers/feishu-driver directory not found"
    exit 1
}

pass "Found feishu-driver directory"

# Check Python
if ! command -v python3 &> /dev/null; then
    fail "python3 not found"
    exit 1
fi
pass "python3 found: $(python3 --version)"

# Install dependencies
test_section "Install Dependencies"

if pip3 install -q -r requirements.txt; then
    pass "Dependencies installed"
else
    fail "Failed to install dependencies"
    exit 1
fi

# Test 1: CLI Help
test_section "Test 1: CLI Help"

if python3 main.py --help &> /dev/null; then
    pass "CLI help works"
else
    fail "CLI help failed"
fi

# Test 2: Send command help
if python3 main.py send --help &> /dev/null; then
    pass "Send command help works"
else
    fail "Send command help failed"
fi

# Test 3: Test notification (Python CLI)
test_section "Test 2: Python CLI - Test Notification"

if python3 main.py test --title "WP-6 Test"; then
    pass "Test notification sent via Python CLI"
    warn "Check Feishu to verify message received"
else
    fail "Test notification failed"
fi

# Test 4: Send to user (Python CLI)
test_section "Test 3: Python CLI - Send to User"

if python3 main.py send --user yunpeng --title "WP-6 User Test" --message "Testing user notification from feishu-driver"; then
    pass "User notification sent via Python CLI"
    warn "Check Feishu to verify message received"
else
    fail "User notification failed"
fi

# Test 5: Markdown support
test_section "Test 4: Python CLI - Markdown Support"

if python3 main.py send --user yunpeng --title "Markdown Test" --message "**Bold** *Italic* \`code\` [link](https://example.com)"; then
    pass "Markdown notification sent"
    warn "Check Feishu to verify Markdown formatting"
else
    fail "Markdown notification failed"
fi

# Test 6: Different colors
test_section "Test 5: Python CLI - Color Support"

for color in blue green red orange; do
    if python3 main.py send --user yunpeng --title "Color: $color" --message "Testing $color color" --color "$color"; then
        pass "Sent notification with color: $color"
    else
        fail "Failed to send notification with color: $color"
    fi
    sleep 1
done

# Test 7: Error handling - missing parameters
test_section "Test 6: Error Handling"

if python3 main.py send --user yunpeng --title "Test" 2>&1 | grep -q "Error"; then
    pass "Error handling works for missing --message"
else
    fail "Error handling not working properly"
fi

# Test 8: Error handling - invalid user
if python3 main.py send --user invalid_user --title "Test" --message "Test" 2>&1 | grep -q "Error"; then
    pass "Error handling works for invalid user"
else
    fail "Error handling not working for invalid user"
fi

# Test 9: Build agent-os
test_section "Test 7: Build agent-os"

cd ../.. || exit 1

if go build -o bin/agent-os ./cmd/agent-os; then
    pass "agent-os built successfully"
else
    fail "Failed to build agent-os"
    exit 1
fi

# Test 10: agent-os notify help
test_section "Test 8: Go CLI - Notify Command"

if ./bin/agent-os notify --help &> /dev/null; then
    pass "agent-os notify command available"
else
    fail "agent-os notify command not available"
fi

if ./bin/agent-os notify send --help &> /dev/null; then
    pass "agent-os notify send command available"
else
    fail "agent-os notify send command not available"
fi

# Test 11: agent-os notify send
test_section "Test 9: Go CLI - Send Notification"

if ./bin/agent-os notify send --user yunpeng --title "WP-6 Go CLI Test" --message "Testing from agent-os CLI"; then
    pass "Notification sent via agent-os CLI"
    warn "Check Feishu to verify message received"
else
    fail "Failed to send notification via agent-os CLI"
fi

# Test 12: agent-os notify test
test_section "Test 10: Go CLI - Test Command"

if ./bin/agent-os notify test --title "WP-6 Integration Test"; then
    pass "Test command works via agent-os CLI"
else
    fail "Test command failed via agent-os CLI"
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Test Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "Passed: ${GREEN}${PASS_COUNT}${NC}"
echo -e "Failed: ${RED}${FAIL_COUNT}${NC}"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Verify messages in Feishu"
    echo "  2. Review WP-6-COMPLETION.md"
    echo "  3. Merge to main"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
