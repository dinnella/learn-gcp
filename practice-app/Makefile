.PHONY: help up down logs seed test build push clean dev-shell

PROJECT_ID ?= local-dev
COMPOSE    := docker compose
APP_PORT   ?= 8080

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

up: ## Start full local stack (firestore emulator + fake-gcs + app)
	$(COMPOSE) up --build -d
	@echo "✔ App: http://localhost:$(APP_PORT)"
	@echo "  Firestore emulator: http://localhost:8085"
	@echo "  fake-gcs-server:   http://localhost:4443"
	@echo ""
	@echo "Run 'make seed' to load questions, then open the app."

down: ## Stop the local stack
	$(COMPOSE) down -v

logs: ## Tail logs from all services
	$(COMPOSE) logs -f --tail=100

seed: ## Load seed/questions.json into the Firestore emulator
	$(COMPOSE) exec app python -m app.seed_emulator

test: ## Run backend tests inside the app container
	$(COMPOSE) exec app pytest -q

build: ## Build the production container image locally
	docker build -t practice-app:local backend/

dev-shell: ## Open a shell in the running app container
	$(COMPOSE) exec app /bin/bash

# ---- production helpers ----

REGION  ?= us-central1
AR_REPO ?= apps
IMAGE   ?= practice-app
TAG     ?= $(shell git rev-parse --short HEAD)
IMAGE_URI = $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(AR_REPO)/$(IMAGE):$(TAG)

build-prod: ## Build production image with the AR-tagged URI
	docker build -t $(IMAGE_URI) backend/

push: build-prod ## Push the image to Artifact Registry (requires gcloud auth)
	gcloud auth configure-docker $(REGION)-docker.pkg.dev --quiet
	docker push $(IMAGE_URI)
	@echo "Pushed $(IMAGE_URI)"

seed-prod: ## Idempotently seed Firestore in your real project
	PROJECT_ID=$(PROJECT_ID) python backend/app/seed_emulator.py

clean:
	$(COMPOSE) down -v --rmi local
