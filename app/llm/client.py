from __future__ import annotations

from openai import OpenAI

from app.llm.config import (
    LLMSettings,
    load_llm_settings,
)


def create_llm_client(
    settings: LLMSettings | None = None,
) -> OpenAI:
    """
    Create a client for an OpenAI-compatible model endpoint.
    """
    resolved_settings = settings if settings is not None else load_llm_settings()

    return OpenAI(
        base_url=resolved_settings.base_url,
        api_key=resolved_settings.api_key,
        timeout=resolved_settings.timeout_seconds,
    )
