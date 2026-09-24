.PHONY: setup data train migrate seed dev test lint e2e up down \
        data-download data-catalog data-nhtsa data-intents data-synthetic data-load data-embed

PY := .venv/Scripts/python.exe
SCRIPTS := dataset/scripts
BACKEND := backend
BACKEND_PY := $(BACKEND)/.venv/Scripts/python.exe

setup:
	python -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e .
	python -m venv $(BACKEND)/.venv
	$(BACKEND_PY) -m pip install --upgrade pip
	$(BACKEND_PY) -m pip install -e "$(BACKEND)[dev]"

data: data-download data-catalog data-nhtsa data-intents data-synthetic data-load data-embed

data-download:
	$(PY) $(SCRIPTS)/download.py

data-catalog:
	$(PY) $(SCRIPTS)/build_catalog.py

data-nhtsa:
	$(PY) $(SCRIPTS)/build_nhtsa.py

data-intents:
	$(PY) $(SCRIPTS)/build_intents.py

data-synthetic:
	$(PY) $(SCRIPTS)/generate_synthetic.py

data-load:
	$(PY) $(SCRIPTS)/load_db.py

data-embed:
	$(PY) $(SCRIPTS)/embed_kb.py

train:
	@echo "Phase 4: intent classifier training (not yet implemented)"

migrate:
	cd $(BACKEND) && ../$(BACKEND_PY) -m alembic upgrade head

seed:
	cd $(BACKEND) && ../$(BACKEND_PY) scripts/seed.py

dev:
	cd $(BACKEND) && ../$(BACKEND_PY) -m uvicorn app.main:app --reload
	@echo "Phase 0: frontend dev server (not yet implemented)"

test:
	$(PY) -m pytest $(SCRIPTS)/tests -q
	cd $(BACKEND) && ../$(BACKEND_PY) -m pytest tests -q

lint:
	$(PY) -m ruff check dataset/scripts
	$(BACKEND_PY) -m ruff check $(BACKEND)/app $(BACKEND)/tests $(BACKEND)/scripts

e2e:
	@echo "Phase 9: Playwright E2E suite (not yet implemented)"

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down
