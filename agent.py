#!/usr/bin/env python3
import argparse
import ast
import operator
import os
from datetime import datetime, timezone
from typing import Callable, Dict

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langchain_aws import ChatBedrock
from langchain_ollama import ChatOllama


load_dotenv()


_ALLOWED_BIN_OPS: Dict[type, Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}

_ALLOWED_UNARY_OPS: Dict[type, Callable[[float], float]] = {
    ast.UAdd: lambda value: value,
    ast.USub: operator.neg,
}


def _safe_eval_math(expr: str) -> float:
    parsed = ast.parse(expr, mode="eval")

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BIN_OPS:
            return _ALLOWED_BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY_OPS:
            return _ALLOWED_UNARY_OPS[type(node.op)](_eval(node.operand))
        raise ValueError("Only numeric math expressions are supported.")

    return _eval(parsed)


@tool
def utc_time(_: str = "") -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(tz=timezone.utc).isoformat()


@tool
def calculator(expression: str) -> str:
    """Evaluate a numeric math expression (supports +, -, *, /, %, **, parentheses)."""
    try:
        result = _safe_eval_math(expression)
        if result.is_integer():
            return str(int(result))
        return str(result)
    except Exception as exc:
        return f"Error: {exc}"


def build_llm(provider: str, model: str, ollama_base_url: str, aws_region: str | None):
    if provider == "ollama":
        return ChatOllama(
            model=model,
            base_url=ollama_base_url,
            temperature=0,
        )

    if provider == "bedrock":
        return ChatBedrock(
            model_id=model,
            region_name=aws_region,
            model_kwargs={"temperature": 0},
        )

    raise ValueError(f"Unsupported provider: {provider}")


def build_agent(provider: str, model: str, ollama_base_url: str, aws_region: str | None, verbose: bool):
    llm = build_llm(
        provider=provider,
        model=model,
        ollama_base_url=ollama_base_url,
        aws_region=aws_region,
    )

    tools = [utc_time, calculator]
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt="You are a helpful assistant. Use tools when needed and keep answers concise.",
        debug=verbose,
    )


def _message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part).strip()
    return str(content)


def _invoke_agent(agent, user_input: str) -> str:
    result = agent.invoke({"messages": [{"role": "user", "content": user_input}]})

    if isinstance(result, dict):
        messages = result.get("messages")
        if isinstance(messages, list) and messages:
            for message in reversed(messages):
                if getattr(message, "type", None) == "ai":
                    text = _message_text(message)
                    if text:
                        return text

        if "output" in result and result["output"]:
            return str(result["output"])

    return str(result)


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
        print(_invoke_agent(agent, args.prompt))
        return

    print("Interactive mode. Type 'exit' to quit.")
    while True:
        user_input = input("You> ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue

        print(f"Agent> {_invoke_agent(agent, user_input)}")


if __name__ == "__main__":
    main()
