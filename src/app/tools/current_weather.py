import asyncio
import json
import os
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from langchain_core.tools import tool

try:
    from fastmcp import Client as FastMCPClient
except Exception:
    FastMCPClient = None


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


def _fetch_json(url: str) -> dict:
    with urlopen(url, timeout=10) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


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


def _mcp_server_url() -> str | None:
    value = os.getenv("MCP_SERVER_URL", "").strip()
    return value or None


def _extract_mcp_result_text(result) -> str:
    if getattr(result, "structured_content", None):
        return json.dumps(result.structured_content, ensure_ascii=False)

    content = getattr(result, "content", None) or []
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
        else:
            parts.append(str(block))

    if parts:
        return "\n".join(parts)

    data = getattr(result, "data", None)
    if data is None:
        return ""
    if isinstance(data, (dict, list)):
        return json.dumps(data, ensure_ascii=False)
    return str(data)


async def _call_mcp_tool_async(tool_name: str, args: dict) -> str:
    if FastMCPClient is None:
        raise RuntimeError("FastMCP client not installed. Install dependencies from requirements.txt.")

    server_url = _mcp_server_url()
    if not server_url:
        raise RuntimeError("MCP_SERVER_URL is not configured.")

    timeout = float(os.getenv("MCP_TIMEOUT_SECONDS", "20"))
    async with FastMCPClient(server_url, timeout=timeout) as client:
        result = await client.call_tool(tool_name, arguments=args)

    text = _extract_mcp_result_text(result).strip()
    if not text:
        raise RuntimeError(f"MCP tool '{tool_name}' returned empty output.")
    return text


def _call_mcp_tool(tool_name: str, args: dict) -> str:
    return asyncio.run(_call_mcp_tool_async(tool_name, args))


def _wmo_description(code: int | None) -> str:
    if code is None:
        return "Unknown"
    return _WMO_WEATHER_CODES.get(code, f"Unknown ({code})")


@tool
def current_weather(location: str) -> str:
    """Get the current weather for a location (metric units)."""
    try:
        server_url = _mcp_server_url()
        if server_url:
            remote_tool = os.getenv("MCP_WEATHER_CURRENT_TOOL", "current_weather").strip() or "current_weather"
            return _call_mcp_tool(remote_tool, {"location": location})

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
