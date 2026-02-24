# Basic LangChain Agent (Ollama + AWS Bedrock)

This project provides a minimal Python agent built with LangChain.

## Features

- Select provider: `ollama` or `bedrock`
- Select model via `--model`
- Basic tools included:
  - `utc_time`
  - `calculator`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

The app loads `.env` automatically (`python-dotenv`). CLI flags still override `.env` values.

## Run with Ollama (local network)

Set your Ollama endpoint/model in `.env` (or pass as CLI args):

```bash
export OLLAMA_BASE_URL="http://<ollama-host>:11434"
export PROVIDER="ollama"
export MODEL="llama3.1"
python agent.py --prompt "What time is it in UTC?"
```

Interactive mode:

```bash
python agent.py
```

## Run with AWS Bedrock

Ensure AWS credentials are configured (env vars, profile, or IAM role) and set region:

```bash
export AWS_REGION="us-east-1"
export PROVIDER="bedrock"
export MODEL="anthropic.claude-3-5-sonnet-20240620-v1:0"
python agent.py --prompt "Calculate (24*7)-5"
```

Interactive mode:

```bash
python agent.py
```

You can always override `.env` values from CLI, for example:

```bash
python agent.py --provider ollama --model qwen2.5:7b --ollama-base-url http://192.168.1.50:11434
```

## Notes

- Bedrock model IDs vary by region/account access.
- Ollama model names depend on models pulled into your Ollama instance.
