#!/bin/sh
# ─────────────────────────────────────────────────────────
#  Auto-loads all Kestra flows on startup
# ─────────────────────────────────────────────────────────

KESTRA_URL="http://kestra:8080"
FLOWS_DIR="/flows"

echo "⏳ Waiting for Kestra to be ready..."
until curl -sf "${KESTRA_URL}/api/v1/flows/search" > /dev/null 2>&1; do
  sleep 5
  echo "  still waiting..."
done

echo "✅ Kestra is ready. Loading flows..."

for flow_file in "${FLOWS_DIR}"/*.yml; do
  echo "  📦 Loading: $(basename "$flow_file")"
  curl -s -X POST \
    "${KESTRA_URL}/api/v1/flows/import" \
    -H "Content-Type: application/x-yaml" \
    --data-binary "@${flow_file}" \
    > /dev/null 2>&1
  echo "     ✓ Loaded $(basename "$flow_file")"
done

echo ""
echo "🚀 All flows loaded! Open http://localhost:8080 to see the Kestra UI."
echo ""
echo "   Quick demo:"
echo "   1. Open http://localhost:8080"
echo "   2. Go to Flows → ai-incident-response"
echo "   3. Trigger: master-incident-orchestration"
echo "   4. Watch the full incident response pipeline run!"
