#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  Demo Trigger Script
#  Simulates a realistic incident and fires the Kestra pipeline
# ─────────────────────────────────────────────────────────────────

set -e

KESTRA_URL="${KESTRA_URL:-http://localhost:8080}"
SERVICE_URL="${SERVICE_URL:-http://localhost:8000}"
NAMESPACE="ai.incident.response"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

print_banner() {
  echo ""
  echo -e "${BLUE}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}${BOLD}║   🚨 Autonomous AI Incident Response Orchestrator        ║${NC}"
  echo -e "${BLUE}${BOLD}║   Demo Trigger Script                                    ║${NC}"
  echo -e "${BLUE}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
  echo ""
}

check_services() {
  echo -e "${YELLOW}⏳ Checking services...${NC}"

  if ! curl -sf "$SERVICE_URL/health" > /dev/null 2>&1 && \
     ! curl -sf "$SERVICE_URL/" > /dev/null 2>&1; then
    echo -e "${RED}❌ Incident service not reachable at $SERVICE_URL${NC}"
    echo "   Run: docker compose up -d"
    exit 1
  fi
  echo -e "${GREEN}✅ Incident service is running${NC}"

  if ! curl -sf "$KESTRA_URL/api/v1/flows/search" > /dev/null 2>&1; then
    echo -e "${RED}❌ Kestra not reachable at $KESTRA_URL${NC}"
    echo "   Run: docker compose up -d"
    exit 1
  fi
  echo -e "${GREEN}✅ Kestra is running${NC}"
}

show_menu() {
  echo ""
  echo -e "${BOLD}Select a failure scenario to simulate:${NC}"
  echo ""
  echo "  1) database_connection_pool_exhausted  (CRITICAL)"
  echo "  2) memory_leak_oom                     (CRITICAL)"
  echo "  3) disk_io_saturation                  (CRITICAL)"
  echo "  4) downstream_api_timeout              (HIGH)"
  echo "  5) rate_limit_cascade                  (HIGH)"
  echo "  6) certificate_expiry                  (HIGH)"
  echo "  7) Random failure (pick one for me)"
  echo ""
  read -p "Enter choice [1-7]: " choice

  case $choice in
    1) FAILURE_TYPE="database_connection_pool_exhausted" ;;
    2) FAILURE_TYPE="memory_leak_oom" ;;
    3) FAILURE_TYPE="disk_io_saturation" ;;
    4) FAILURE_TYPE="downstream_api_timeout" ;;
    5) FAILURE_TYPE="rate_limit_cascade" ;;
    6) FAILURE_TYPE="certificate_expiry" ;;
    7) FAILURE_TYPE="" ;;
    *) echo "Invalid choice. Using random."; FAILURE_TYPE="" ;;
  esac
}

trigger_failure() {
  echo ""
  echo -e "${YELLOW}🔥 Triggering failure scenario...${NC}"

  if [ -n "$FAILURE_TYPE" ]; then
    RESPONSE=$(curl -sf -X POST "$SERVICE_URL/simulate-failure?failure_type=$FAILURE_TYPE")
  else
    RESPONSE=$(curl -sf -X POST "$SERVICE_URL/simulate-failure")
  fi

  INCIDENT_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('incident_id','INC-UNKNOWN'))" 2>/dev/null || echo "INC-UNKNOWN")
  ACTUAL_FAILURE=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('failure_type','unknown'))" 2>/dev/null || echo "unknown")
  COMPONENT=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('component','unknown'))" 2>/dev/null || echo "unknown")
  MESSAGE=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('description','Service failure'))" 2>/dev/null || echo "Service failure")

  echo -e "${RED}${BOLD}"
  echo "  🚨 INCIDENT TRIGGERED"
  echo "  ─────────────────────────────────────────"
  echo "  Incident ID  : $INCIDENT_ID"
  echo "  Failure Type : $ACTUAL_FAILURE"
  echo "  Component    : $COMPONENT"
  echo "  Description  : $MESSAGE"
  echo -e "${NC}"

  export INCIDENT_ID ACTUAL_FAILURE COMPONENT MESSAGE
}

fire_kestra_flow() {
  echo -e "${YELLOW}🎯 Firing Kestra master orchestration pipeline...${NC}"

  PAYLOAD=$(cat <<EOF
{
  "inputs": {
    "incident_id": "$INCIDENT_ID",
    "failure_type": "$ACTUAL_FAILURE",
    "component": "$COMPONENT",
    "error_message": "$MESSAGE",
    "http_code": "503",
    "service_url": "http://incident-service:8000"
  }
}
EOF
)

  EXEC_RESPONSE=$(curl -sf -X POST \
    "$KESTRA_URL/api/v1/executions/$NAMESPACE/master-incident-orchestration" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" 2>/dev/null || echo '{}')

  EXEC_ID=$(echo "$EXEC_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id','unknown'))" 2>/dev/null || echo "unknown")

  echo ""
  echo -e "${GREEN}${BOLD}🚀 PIPELINE FIRED SUCCESSFULLY!${NC}"
  echo ""
  echo -e "  ${BOLD}Execution ID:${NC} $EXEC_ID"
  echo ""
  echo -e "  ${BOLD}Watch live:${NC}"
  echo -e "  ${BLUE}$KESTRA_URL/ui/executions/$EXEC_ID${NC}"
  echo ""
  echo -e "  ${BOLD}Kestra Dashboard:${NC}"
  echo -e "  ${BLUE}$KESTRA_URL${NC}"
  echo ""
  echo -e "  ${BOLD}Incident Service:${NC}"
  echo -e "  ${BLUE}$SERVICE_URL/docs${NC}"
  echo ""
}

wait_and_show() {
  echo -e "${YELLOW}⏳ Waiting 5 seconds then showing pipeline status...${NC}"
  sleep 5

  echo ""
  echo -e "${BOLD}📊 Current service metrics:${NC}"
  curl -sf "$SERVICE_URL/metrics" | python3 -m json.tool 2>/dev/null | head -20 || true
  echo ""

  echo -e "${GREEN}${BOLD}✅ Demo running! Here's what to show:${NC}"
  echo ""
  echo "  1. 🌐 Open Kestra UI: $KESTRA_URL"
  echo "     → Flows → ai.incident.response"
  echo "     → Click 'master-incident-orchestration'"
  echo "     → Watch the execution graph animate in real-time"
  echo ""
  echo "  2. 📋 View execution logs in Kestra for each stage:"
  echo "     → Stage 1: Classification"
  echo "     → Stage 2: Log collection (parallel tasks)"
  echo "     → Stage 3: AI analysis (GPT-4o)"
  echo "     → Stage 4: Slack + GitHub (parallel)"
  echo "     → Stage 5: Report generation"
  echo ""
  echo "  3. 💬 Check Slack #incidents channel for the alert"
  echo "  4. 🐙 Check GitHub Issues for auto-created ticket"
  echo "  5. 📈 Check $SERVICE_URL/metrics for degraded metrics"
  echo ""
}

cleanup() {
  echo ""
  read -p "Resolve the incident? (y/n): " resolve
  if [[ "$resolve" =~ ^[Yy]$ ]]; then
    curl -sf -X POST "$SERVICE_URL/resolve-incident" > /dev/null
    echo -e "${GREEN}✅ Incident resolved — service restored to healthy state${NC}"
  fi
}

print_banner
check_services
show_menu
trigger_failure
fire_kestra_flow
wait_and_show
cleanup
