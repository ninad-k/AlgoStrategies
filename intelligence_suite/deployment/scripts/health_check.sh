#!/usr/bin/env bash
# Intelligence Suite — Health Check Script
# ===========================================
# Checks all service endpoints and reports status.
# Usage: ./health_check.sh [host]

set -euo pipefail

HOST="${1:-localhost}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

check_endpoint() {
    local name="$1"
    local url="$2"
    local expected="${3:-200}"

    printf "  %-30s " "$name"

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "$url" 2>/dev/null || echo "000")

    if [ "$HTTP_CODE" = "$expected" ]; then
        echo -e "${GREEN}OK${NC} (HTTP $HTTP_CODE)"
        PASS=$((PASS + 1))
    elif [ "$HTTP_CODE" = "000" ]; then
        echo -e "${RED}UNREACHABLE${NC}"
        FAIL=$((FAIL + 1))
    else
        echo -e "${YELLOW}UNEXPECTED${NC} (HTTP $HTTP_CODE, expected $expected)"
        FAIL=$((FAIL + 1))
    fi
}

echo "============================================"
echo " Intelligence Suite — Health Check"
echo " Host: $HOST"
echo " Time: $(date -Iseconds)"
echo "============================================"
echo ""

echo "Main Trading Engine (port 8060):"
check_endpoint "Health" "http://$HOST:8060/api/health"
check_endpoint "API Docs" "http://$HOST:8060/docs"
echo ""

echo "Heatmap Dashboard (port 8061):"
check_endpoint "Health" "http://$HOST:8061/api/health"
check_endpoint "Portfolio API" "http://$HOST:8061/api/portfolio"
check_endpoint "VaR API" "http://$HOST:8061/api/var"
check_endpoint "Stress API" "http://$HOST:8061/api/stress"
check_endpoint "Heatmap API" "http://$HOST:8061/api/heatmap"
check_endpoint "Dashboard UI" "http://$HOST:8061/"
echo ""

echo "Multi-Account Aggregator (port 8062):"
check_endpoint "Health" "http://$HOST:8062/api/health"
check_endpoint "Accounts API" "http://$HOST:8062/api/accounts"
check_endpoint "Positions API" "http://$HOST:8062/api/positions"
check_endpoint "PnL API" "http://$HOST:8062/api/pnl"
check_endpoint "Allocations API" "http://$HOST:8062/api/allocations"
check_endpoint "Dashboard UI" "http://$HOST:8062/"
echo ""

echo "Infrastructure:"
check_endpoint "Redis" "http://$HOST:6379" "000"  # Redis doesn't speak HTTP; check connectivity
# Redis check via redis-cli if available
if command -v redis-cli &> /dev/null; then
    printf "  %-30s " "Redis PING"
    REDIS_PONG=$(redis-cli -h "$HOST" ping 2>/dev/null || echo "FAIL")
    if [ "$REDIS_PONG" = "PONG" ]; then
        echo -e "${GREEN}PONG${NC}"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}FAIL${NC}"
        FAIL=$((FAIL + 1))
    fi
fi
echo ""

echo "============================================"
TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
    echo -e " Result: ${GREEN}ALL CHECKS PASSED${NC} ($PASS/$TOTAL)"
else
    echo -e " Result: ${RED}$FAIL FAILED${NC}, ${GREEN}$PASS PASSED${NC} ($TOTAL total)"
fi
echo "============================================"

exit "$FAIL"
