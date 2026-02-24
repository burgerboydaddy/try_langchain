#!/usr/bin/env python3
import argparse
import os

from dotenv import load_dotenv

from src.app.agent_runtime import build_agent, invoke_agent


load_dotenv()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Basic LangChain agent with Ollama/AWS Bedrock backends.")
    parser.add_argument(
        "--provider",
        choices=["ollama", "bedrock"],
        default=os.getenv("PROVIDER"),
        help="LLM provider to use.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("MODEL"),
        help="Model name / model ID for the selected provider.",
    )
    parser.add_argument(
        "--ollama-base-url",
        default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        help="Ollama base URL (used when --provider ollama).",
    )
    parser.add_argument(
        "--aws-region",
        default=os.getenv("AWS_REGION"),
        help="AWS region (used when --provider bedrock).",
    )
    parser.add_argument(
        "--prompt",
        help="Single-shot prompt. If omitted, starts interactive mode.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable LangChain verbose logs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.provider:
        raise ValueError("Provider is required. Use --provider or set PROVIDER in .env/environment.")
    if not args.model:
        raise ValueError("Model is required. Use --model or set MODEL in .env/environment.")

    if args.provider == "bedrock" and not args.aws_region:
        raise ValueError("--aws-region is required for bedrock (or set AWS_REGION).")

    agent = build_agent(
        provider=args.provider,
        model=args.model,
        ollama_base_url=args.ollama_base_url,
        aws_region=args.aws_region,
        verbose=args.verbose,
    )

    if args.prompt:
        print(invoke_agent(agent, args.prompt))
        return

    print("Interactive mode. Type 'exit' to quit.")
    while True:
        user_input = input("You> ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue

        print(f"Agent> {invoke_agent(agent, user_input)}")


if __name__ == "__main__":
    main()
