from langchain.agents import create_agent
from langchain_core.messages import BaseMessage
from langchain_aws import ChatBedrock
from langchain_ollama import ChatOllama

from src.app.tools import TOOLS


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

    return create_agent(
        model=llm,
        tools=TOOLS,
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


def invoke_agent(agent, user_input: str) -> str:
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
