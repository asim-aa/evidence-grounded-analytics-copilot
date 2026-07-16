from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class LLMSettings:
    """
    Configuration for an OpenAI-compatible language-model endpoint.
    """

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 60.0


def load_llm_settings() -> LLMSettings:
    """
    Load LLM configuration from environment variables.

    Required variables:
        LLM_BASE_URL
        LLM_API_KEY
        LLM_MODEL
    """
    load_dotenv()

    base_url = os.getenv("LLM_BASE_URL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()

    missing_variables = [
        variable_name
        for variable_name, value in (
            ("LLM_BASE_URL", base_url),
            ("LLM_API_KEY", api_key),
            ("LLM_MODEL", model),
        )
        if not value
    ]

    if missing_variables:
        missing_text = ", ".join(missing_variables)

        raise RuntimeError(
            f"Missing required LLM environment variables: {missing_text}"
        )

    timeout_text = os.getenv(
        "LLM_TIMEOUT_SECONDS",
        "60",
    ).strip()

    try:
        timeout_seconds = float(timeout_text)
    except ValueError as error:
        raise RuntimeError("LLM_TIMEOUT_SECONDS must be numeric.") from error

    if timeout_seconds <= 0:
        raise RuntimeError("LLM_TIMEOUT_SECONDS must be greater than zero.")

    return LLMSettings(
        base_url=base_url.rstrip("/"),
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
    )
