#!/bin/bash
# Test quantsys-v2 API endpoints used by agent-ts

echo "=== Testing quantsys-v2 API Endpoints ==="
echo ""

BASE_URL="http://127.0.0.1:5001"

echo "1. Testing Portfolio API (simulation account):"
curl -s "$BASE_URL/api/simulation/accounts/default" | jq -c '{success, data: {cash, positions_count, total_value}}'
echo ""

echo "2. Testing Pools API:"
curl -s "$BASE_URL/api/pools" | jq -c '{success, count: (.data | length)}'
echo ""

echo "3. Testing Market Overview API:"
curl -s "$BASE_URL/api/market/overview" | jq -c 'if .success then {success, data: "OK"} else . end'
echo ""

echo "4. Testing Old Portfolio API (for comparison):"
curl -s "$BASE_URL/api/portfolio" | jq -c '{success, holdings_count: (.data.holdings | length)}'
echo ""

echo "=== All tests completed ==="
