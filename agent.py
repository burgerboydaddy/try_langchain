#!/usr/bin/env python3
import argparse
import ast
import json
import operator
import os
from datetime import datetime, timezone
from typing import Callable, Dict
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

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

_WMO_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
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


def _fetch_json(url: str) -> dict:
    with urlopen(url, timeout=10) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _wmo_description(code: int | None) -> str:
    if code is None:
        return "Unknown"
    return _WMO_WEATHER_CODES.get(code, f"Unknown ({code})")


def _resolve_location(location: str) -> dict:
    query = urlencode({"name": location, "count": 1, "language": "en", "format": "json"})
    url = f"https://geocoding-api.open-meteo.com/v1/search?{query}"
    payload = _fetch_json(url)
    results = payload.get("results") or []
    if not results:
        raise ValueError(f"Location not found: {location}")
    top = results[0]
    city = top.get("name", location)
    country = top.get("country")
    display_name = f"{city}, {country}" if country else city
    return {
        "name": display_name,
        "latitude": top["latitude"],
        "longitude": top["longitude"],
    }


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


@tool
def current_weather(location: str) -> str:
    """Get the current weather for a location (metric units)."""
    try:
        resolved = _resolve_location(location)
        query = urlencode(
            {
                "latitude": resolved["latitude"],
                "longitude": resolved["longitude"],
                "current": "temperature_2m,wind_speed_10m,weather_code",
                "timezone": "auto",
            }
        )
        url = f"https://api.open-meteo.com/v1/forecast?{query}"
        payload = _fetch_json(url)
        current = payload.get("current", {})
        temp = current.get("temperature_2m")
        wind = current.get("wind_speed_10m")
        code = current.get("weather_code")
        time_value = current.get("time", "unknown")

        if temp is None or wind is None:
            raise ValueError("Weather data unavailable for the requested location.")

        description = _wmo_description(code)
        return (
            f"Current weather for {resolved['name']}:\n"
            f"- Time: {time_value}\n"
            f"- Condition: {description}\n"
            f"- Temperature: {temp}°C\n"
            f"- Wind: {wind} m/s"
        )
    except (ValueError, KeyError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return f"Error: {exc}"
    except Exception as exc:
        return f"Error: {exc}"


@tool
def weather_forecast(location: str) -> str:
    """Get hourly weather forecast for the next 24 hours for a location (metric units)."""
    try:
        resolved = _resolve_location(location)
        query = urlencode(
            {
                "latitude": resolved["latitude"],
                "longitude": resolved["longitude"],
                "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,weather_code",
                "forecast_hours": 24,
                "timezone": "auto",
            }
        )
        url = f"https://api.open-meteo.com/v1/forecast?{query}"
        payload = _fetch_json(url)
        hourly = payload.get("hourly", {})
        times = hourly.get("time") or []
        temperatures = hourly.get("temperature_2m") or []
        precipitations = hourly.get("precipitation_probability") or []
        winds = hourly.get("wind_speed_10m") or []
        codes = hourly.get("weather_code") or []

        count = min(len(times), len(temperatures), len(precipitations), len(winds), len(codes), 24)
        if count == 0:
            raise ValueError("Forecast data unavailable for the requested location.")

        lines = [f"Hourly forecast for {resolved['name']} (next {count} hours):"]
        for i in range(count):
            lines.append(
                f"- {times[i]}: {_wmo_description(codes[i])}, {temperatures[i]}°C, "
                f"precip {precipitations[i]}%, wind {winds[i]} m/s"
            )
        return "\n".join(lines)
    except (ValueError, KeyError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return f"Error: {exc}"
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

    tools = [utc_time, calculator, current_weather, weather_forecast]
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
