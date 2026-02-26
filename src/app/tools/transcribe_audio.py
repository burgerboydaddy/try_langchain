import base64
import os
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool


def _build_llm(model_override: str | None = None):
    """Build an LLM instance from environment variables.

    Args:
        model_override: When provided, use this model name instead of the MODEL env var.
    """
    provider = os.getenv("PROVIDER", "bedrock")
    model = model_override or os.getenv("MODEL")

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=0,
        )

    if provider == "bedrock":
        from langchain_aws import ChatBedrock

        return ChatBedrock(
            model_id=model,
            region_name=os.getenv("AWS_REGION"),
            model_kwargs={"temperature": 0},
        )

    raise ValueError(f"Unsupported provider: {provider}")


def _whisper_transcribe(wav_path: Path, model_size: str) -> str:
    """Transcribe a WAV file locally using the openai-whisper library.

    Args:
        wav_path: Path to the .wav file.
        model_size: Whisper model size — one of: tiny, base, small, medium,
                    large, large-v2, large-v3.  Falls back to 'base' if blank.
    """
    import whisper  # lazy import — only loaded when Ollama provider is used

    size = model_size.strip() or "base"
    model = whisper.load_model(size)
    result = model.transcribe(str(wav_path), fp16=False)
    # print("Transcription: ", result["text"])
    return result["text"].strip()


@tool
def transcribe_audio(wav_file_path: str) -> str:
    """Transcribe a WAV audio file using the configured LLM and save the result as a
    Markdown file in the diary folder.  The saved document includes a header with the
    current date (e.g. 'Tuesday, February 24, 2026') and current time.

    Args:
        wav_file_path: Absolute or relative path to the .wav file to transcribe.

    Returns:
        The path to the saved Markdown transcript file, or an error message.
    """
    # --- validate input file ---
    wav_path = Path(wav_file_path).expanduser().resolve()
    if not wav_path.exists():
        return f"Error: file not found: {wav_file_path}"
    if wav_path.suffix.lower() != ".wav":
        return f"Error: expected a .wav file, got '{wav_path.suffix}'"
    # --- capture current date/time ---
    now = datetime.now()
    # "Tuesday, February 24, 2026"  (%-d strips the leading zero on Linux/macOS)
    date_str = now.strftime("%A, %B %-d, %Y")
    time_str = now.strftime("%H:%M:%S")
    file_stem = now.strftime("%Y-%m-%dT%H%M%S")

    # Step 1: transcribe audio locally with openai-whisper.
    # TRANSCRIPT_MODEL selects the whisper model size (tiny/base/small/medium/large).
    whisper_size = os.getenv("TRANSCRIPT_MODEL", "base")
    raw_text = _whisper_transcribe(wav_path, whisper_size)
    print(f"Raw transcript:\n{raw_text}\n")
    # Step 2: convert raw transcript to clean Markdown with MARKDOWN_MODEL
    md_prompt = (
        "Convert this text into clean Markdown. "
        "Do not translate or change any of the content; only fix grammar and formatting. "
        "Text is in English, but may contain grammar mistakes, filler words, and disfluencies. "
        "Return only the transcribed and grammar-corrected content with no additional commentary or analysis.\n\n"
        
        f"{raw_text}"
    )
    # --- call the LLM(s) ---
    provider = os.getenv("PROVIDER", "bedrock").lower()
    if provider == "ollama":
        markdown_model = os.getenv("MARKDOWN_MODEL") or os.getenv("MODEL")    
        llm_markdown = _build_llm(model_override=markdown_model)

        md_response = llm_markdown.invoke([HumanMessage(content=md_prompt)])
        body = (
            md_response.content
            if isinstance(md_response.content, str)
            else str(md_response.content)
        ).strip()

    else:
        llm = _build_llm()

        response = llm.invoke([HumanMessage(content=md_prompt)])
        body = (
            response.content
            if isinstance(response.content, str)
            else str(response.content)
        ).strip()

    # --- build Markdown document ---
    markdown = (
        f"# Captain's Log: {date_str}\n\n"
        f"*This log was automatically transcribed from an audio recording on {date_str} at {time_str}.*\n\n"
        f"\n\n"
        f"{body}\n"
    )

    # --- save to diary/ at the project root ---
    # src/app/tools/transcribe_audio.py  →  parents[3] = project root
    diary_dir = Path(__file__).parents[3] / "diary"
    diary_dir.mkdir(parents=True, exist_ok=True)

    output_path = diary_dir / f"{file_stem}.md"
    output_path.write_text(markdown, encoding="utf-8")

    return f"Transcript saved to: {output_path}"
