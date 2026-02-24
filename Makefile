SHELL := /bin/bash
PYTHON := python3
VENV := .venv
VENV_PY := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
APP := agent.py

.PHONY: help venv install setup check run run-ollama run-bedrock

help:
	@echo "Targets:"
	@echo "  make setup        - Create venv and install dependencies"
	@echo "  make check        - Syntax-check agent.py"
	@echo "  make run          - Run agent (uses .env values)"
	@echo "  make run-ollama   - Run with Ollama provider"
	@echo "  make run-bedrock  - Run with Bedrock provider"
	@echo ""
	@echo "Optional vars:"
	@echo "  PROMPT='your prompt'"
	@echo "  MODEL='model-name-or-id'"
	@echo "  OLLAMA_BASE_URL='http://host:11434'"
	@echo "  AWS_REGION='us-west-2'"

venv:
	$(PYTHON) -m venv $(VENV)

install: venv
	$(VENV_PIP) install -r requirements.txt

setup: install
	@test -f .env || cp .env.example .env
	@echo "Setup complete. Edit .env if needed."

check:
	$(VENV_PY) -m py_compile $(APP)

run:
	$(VENV_PY) $(APP) $(if $(PROMPT),--prompt "$(PROMPT)",)

run-ollama:
	PROVIDER=ollama MODEL="$(MODEL)" OLLAMA_BASE_URL="$(OLLAMA_BASE_URL)" \
	$(VENV_PY) $(APP) $(if $(PROMPT),--prompt "$(PROMPT)",)

run-bedrock:
	PROVIDER=bedrock MODEL="$(MODEL)" AWS_REGION="$(AWS_REGION)" \
	$(VENV_PY) $(APP) $(if $(PROMPT),--prompt "$(PROMPT)",)
