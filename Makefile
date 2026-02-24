SHELL := /bin/bash
PYTHON := python3
VENV := .venv
VENV_PY := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
APP := main.py

.PHONY: help venv install setup check check-mcp run run-ollama run-bedrock

help:
	@echo "Targets:"
	@echo "  make setup        - Create venv and install dependencies"
	@echo "  make check        - Syntax-check main.py and src modules"
	@echo "  make check-mcp    - Validate MCP endpoint and list MCP tools"
	@echo "  make run          - Run agent (uses .env values)"
	@echo "  make run-ollama   - Run with Ollama provider"
	@echo "  make run-bedrock  - Run with Bedrock provider"
	@echo ""
	@echo "Optional vars:"
	@echo "  PROMPT='your prompt'"
	@echo "  MODEL='model-name-or-id'"
	@echo "  OLLAMA_BASE_URL='http://host:11434'"
	@echo "  AWS_REGION='us-west-2'"
	@echo "  MCP_SERVER_URL='http://host:port/mcp'"

venv:
	$(PYTHON) -m venv $(VENV)

install: venv
	$(VENV_PIP) install -r requirements.txt

setup: install
	@test -f .env || cp .env.example .env
	@echo "Setup complete. Edit .env if needed."

check:
	$(VENV_PY) -m py_compile $(APP) src/app/agent_runtime.py src/app/tools/*.py

check-mcp:
	@if [ -z "$$MCP_SERVER_URL" ]; then \
		echo "MCP_SERVER_URL is required (example: MCP_SERVER_URL=http://localhost:8000/mcp make check-mcp)"; \
		exit 1; \
	fi
	@MCP_SERVER_URL="$$MCP_SERVER_URL" $(VENV_PY) - <<-'PY'
	import asyncio
	import os
	import sys

	from fastmcp import Client


	async def main() -> int:
		server_url = os.environ["MCP_SERVER_URL"]
		try:
			async with Client(server_url, timeout=10) as client:
				tools = await client.list_tools()
		except Exception as exc:
			print(f"MCP check failed: {exc}")
			return 1

		names = [getattr(tool, "name", str(tool)) for tool in tools]
		print(f"Connected to MCP server: {server_url}")
		print(f"Tools available: {len(names)}")
		for name in names:
			print(f"- {name}")
		return 0


	sys.exit(asyncio.run(main()))
	PY

run:
	$(VENV_PY) $(APP) $(if $(PROMPT),--prompt "$(PROMPT)",)

run-ollama:
	PROVIDER=ollama MODEL="$(MODEL)" OLLAMA_BASE_URL="$(OLLAMA_BASE_URL)" \
	$(VENV_PY) $(APP) $(if $(PROMPT),--prompt "$(PROMPT)",)

run-bedrock:
	PROVIDER=bedrock MODEL="$(MODEL)" AWS_REGION="$(AWS_REGION)" \
	$(VENV_PY) $(APP) $(if $(PROMPT),--prompt "$(PROMPT)",)
