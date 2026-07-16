from __future__ import annotations

from collections.abc import Callable

from openai import OpenAI

from app.evidence.models import EvidenceResult
from app.llm.client import create_llm_client
from app.llm.config import (
    LLMSettings,
    load_llm_settings,
)
from app.llm.prompts import (
    SYSTEM_PROMPT,
    build_explanation_prompt,
)


TextGenerator = Callable[
    [
        str,
        str,
    ],
    str,
]


def _generate_with_openai_client(
    system_prompt: str,
    user_prompt: str,
    client: OpenAI,
    model: str,
) -> str:
    """
    Generate text through an OpenAI-compatible Chat Completions endpoint.
    """
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.0,
    )

    content = completion.choices[0].message.content

    if content is None or not content.strip():
        raise RuntimeError("The explanation model returned no text.")

    return content.strip()


def build_unsupported_explanation(
    evidence: EvidenceResult,
) -> str:
    """
    Return a deterministic refusal without calling an LLM.
    """
    warning_text = (
        evidence.warnings[0]
        if evidence.warnings
        else (
            "The current analytics engine does not contain evidence for this request."
        )
    )

    return (
        "Direct answer:\n"
        f"{evidence.summary}\n\n"
        "Key evidence:\n"
        "No supported analytical route produced evidence for "
        "this question.\n\n"
        "Business interpretation:\n"
        "A reliable answer cannot be produced from the currently "
        "available analyses.\n\n"
        "Limitations:\n"
        f"{warning_text}"
    )


def generate_grounded_explanation(
    evidence: EvidenceResult,
    *,
    text_generator: TextGenerator | None = None,
    client: OpenAI | None = None,
    settings: LLMSettings | None = None,
) -> str:
    """
    Generate a business explanation from verified evidence.

    A custom text_generator can be injected for testing, allowing the
    test suite to run without making external model requests.
    """
    if not evidence.supported:
        return build_unsupported_explanation(evidence)

    user_prompt = build_explanation_prompt(evidence)

    if text_generator is not None:
        explanation = text_generator(
            SYSTEM_PROMPT,
            user_prompt,
        )

        if not explanation.strip():
            raise RuntimeError("The injected text generator returned no text.")

        return explanation.strip()

    resolved_settings = settings if settings is not None else load_llm_settings()

    resolved_client = (
        client if client is not None else create_llm_client(resolved_settings)
    )

    return _generate_with_openai_client(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        client=resolved_client,
        model=resolved_settings.model,
    )
