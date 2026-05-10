# ─────────────────────────────────────────────────────────────────
#  Autonomous AI Incident Response Orchestrator
#  Makefile — common operations
# ─────────────────────────────────────────────────────────────────

.PHONY: help up down logs demo test trigger clean reset status

# Default target
help: ## Show this help
	@echo ""
	@echo "  🚨 AI Incident Response Orchestrator"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""

up: ## Start all services (docker compose up -d)
	@echo "🚀 Starting services..."
	cp -n .env.example .env 2>/dev/null || true
	docker compose up -d
	@echo ""
	@echo "  Kestra UI      → http://localhost:8080"
	@echo "  Incident API   → http://localhost:8000/docs"
	@echo ""

down: ## Stop all services
	docker compose down

logs: ## Tail logs from all services
	docker compose logs -f --tail=50

kestra-logs: ## Tail Kestra logs only
	docker compose logs -f kestra --tail=100

service-logs: ## Tail incident service logs only
	docker compose logs -f incident-service --tail=50

demo: ## Run the interactive demo trigger script
	@bash scripts/trigger-demo.sh

test: ## Run integration checks
	@python3 scripts/test-integrations.py

trigger: ## Trigger a random incident via API
	@echo "🔥 Triggering random incident..."
	@curl -sf -X POST http://localhost:8000/simulate-failure | python3 -m json.tool
	@echo ""
	@echo "Now fire the Kestra pipeline:"
	@echo "  Open: http://localhost:8080"

trigger-critical: ## Trigger a CRITICAL database failure
	@curl -sf -X POST "http://localhost:8000/simulate-failure?failure_type=database_connection_pool_exhausted" | python3 -m json.tool

trigger-oom: ## Trigger a CRITICAL OOM failure
	@curl -sf -X POST "http://localhost:8000/simulate-failure?failure_type=memory_leak_oom" | python3 -m json.tool

resolve: ## Resolve active incident
	@curl -sf -X POST http://localhost:8000/resolve-incident | python3 -m json.tool

status: ## Show current service status
	@echo "=== Incident Service ===" && curl -sf http://localhost:8000/status | python3 -m json.tool || true
	@echo "=== Metrics ===" && curl -sf http://localhost:8000/metrics | python3 -m json.tool || true

health: ## Check health of incident service
	@curl -sf http://localhost:8000/health | python3 -m json.tool || \
		curl -sf http://localhost:8000/status | python3 -c "import sys,json; d=json.load(sys.stdin); print('Status:', d['state'].get('failure_type','none'))"

load-flows: ## Reload all Kestra flows
	@echo "📦 Loading flows into Kestra..."
	@for f in kestra/flows/*.yml; do \
		echo "  Loading $$f..."; \
		curl -sf -X POST http://localhost:8080/api/v1/flows/import \
			-H "Content-Type: application/x-yaml" \
			--data-binary "@$$f" > /dev/null && echo "  ✓ $$f" || echo "  ✗ $$f (Kestra not ready yet?)"; \
	done

clean: ## Remove all Docker volumes (WARNING: deletes data)
	docker compose down -v
	docker volume rm ai-incident-postgres-data ai-incident-kestra-storage ai-incident-kestra-tmp 2>/dev/null || true

reset: clean up ## Full reset — removes all data and restarts

open: ## Open Kestra UI in browser (macOS/Linux)
	open http://localhost:8080 2>/dev/null || xdg-open http://localhost:8080 2>/dev/null || echo "Open: http://localhost:8080"
