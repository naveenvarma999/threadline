# Threadline developer commands. Run `make help` for the list.
PY ?= python3
export MLFLOW_TRACKING_URI ?= sqlite:///$(CURDIR)/mlflow.db

.PHONY: help setup train train-hm test lint serve-inference serve-api seed web ops up down

help:           ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

setup:          ## Install Python packages (CPU) and frontend dependencies
	$(PY) -m pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
	$(PY) -m pip install -e "ml[train,dev]" -r services/inference/requirements.txt -r services/app_api/requirements.txt
	cd web/storefront && npm install
	cd web/ops-console && npm install

train:          ## Train on synthetic data (or real H&M if data/raw/hm has the CSVs), register + gate promotion
	$(PY) -m threadline.train --auto-promote

train-hm:       ## Train on the real H&M data in data/raw/hm
	$(PY) -m threadline.train --source hm --auto-promote

test:           ## Run every test suite
	cd ml && $(PY) -m pytest -q
	cd services/inference && $(PY) -m pytest -q
	cd services/app_api && $(PY) manage.py test

lint:           ## Lint Python
	ruff check ml services

serve-inference: ## Inference API on :8001, serving the registered champion
	cd services/inference && MODEL_URI=models:/threadline-recommender@champion uvicorn app.main:app --port 8001

seed:           ## Create the shop database and load the catalogue
	cd services/app_api && $(PY) manage.py migrate && $(PY) manage.py load_catalog --processed-dir ../../data/processed

serve-api:      ## Django API on :8000
	cd services/app_api && INFERENCE_URL=http://localhost:8001 $(PY) manage.py runserver 8000

web:            ## React storefront dev server on :5173
	cd web/storefront && npm run dev

ops:            ## Angular ops console dev server on :4200
	cd web/ops-console && npm start

up:             ## Full stack in Docker: infra, one training run, then the apps
	docker compose up -d --build postgres redis mlflow
	docker compose run --rm --build trainer
	docker compose up -d --build inference app_api storefront ops

down:           ## Stop the Docker stack
	docker compose down
