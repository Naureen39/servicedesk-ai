.PHONY: setup data train migrate seed dev test lint e2e up down eval-retrieval \
        data-download data-catalog data-nhtsa data-intents data-synthetic data-load data-embed data-embed-intents \
        data-scheduling-reference

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

data: data-download data-catalog data-nhtsa data-intents data-synthetic data-load data-embed data-embed-intents data-scheduling-reference

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

data-embed-intents:
	$(PY) $(SCRIPTS)/embed_intents.py

data-scheduling-reference:
	$(PY) $(SCRIPTS)/build_scheduling_reference.py

train:
	cd $(BACKEND) && ../$(BACKEND_PY) scripts/train_intent_classifier.py

migrate:
	cd $(BACKEND) && ../$(BACKEND_PY) -m alembic upgrade head

seed:
	cd $(BACKEND) && ../$(BACKEND_PY) scripts/seed.py

dev:
	trap 'kill 0' EXIT; \
	(cd $(BACKEND) && ../$(BACKEND_PY) -m uvicorn app.main:app --reload) & \
	(cd frontend && npm run dev) & \
	wait

test:
	$(PY) -m pytest $(SCRIPTS)/tests -q
	cd $(BACKEND) && ../$(BACKEND_PY) -m pytest tests -q
	cd frontend && npm test

lint:
	$(PY) -m ruff check dataset/scripts
	$(BACKEND_PY) -m ruff check $(BACKEND)/app $(BACKEND)/tests $(BACKEND)/scripts
	cd frontend && npm run lint

e2e:
	cd frontend && npx playwright test

eval-retrieval:
	cd $(BACKEND) && ../$(BACKEND_PY) scripts/eval_retrieval.py

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down
