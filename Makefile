.PHONY: help install test lint format docker-build docker-up docker-down k8s-deploy helm-lint run-api run-demo

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install package with all development & production extras
	pip install -e .[all,dev]

test: ## Run complete automated test suite
	python -m unittest discover -s tests -v

lint: ## Run code quality checks (Ruff & Mypy)
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

format: ## Auto-format code
	ruff format src/ tests/

docker-build: ## Build multi-stage production Docker image
	docker build -f deploy/docker/Dockerfile -t fandomwatch:latest .

docker-up: ## Start full stack via docker-compose (API, Postgres, Redis, Prometheus, Grafana)
	cd deploy && docker compose up -d

docker-down: ## Stop full docker-compose stack
	cd deploy && docker compose down -v

helm-lint: ## Validate and lint Helm chart
	helm lint deploy/helm/fandomwatch

k8s-deploy: ## Apply raw Kubernetes manifests to current context
	kubectl apply -f deploy/k8s/

run-api: ## Launch production FastAPI server locally
	fandomwatch api --host 0.0.0.0 --port 8000

run-demo: ## Launch demo CLI report
	fandomwatch report --demo --title "Steel Tide"
