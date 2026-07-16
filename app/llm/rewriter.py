
from __future__ import annotations

from collections.abc import Callable

from openai import OpenAI
import logging
from app.llm.client import create_llm_client
from app.llm.config import (
    LLMSettings,
    load_llm_settings,
)
LOGGER = logging.getLogger(__name__)

RewriteGenerator = Callable[
    [
        str,
        str,
    ],
    str,
]


REWRITE_SYSTEM_PROMPT = (
    "You rewrite a business analyst's follow-up question into a single, "
    "fully standalone question, using the conversation history for "
    "context.\n\n"
    "Rules:\n"
    "- Resolve pronouns, ellipsis, and implicit topics "
    "(e.g. 'what about last quarter', 'why is that', 'what caused it', "
    "'and for orders') into an explicit question that stands on its own.\n"
    "- Preserve and reuse the topic vocabulary already present in the "
    "conversation (words like revenue, sales, delivery, late, state, "
    "region, category, review, rating, trend, month) whenever the "
    "follow-up is continuing that same topic.\n"
    "- Do not invent facts, numbers, filters, or entities the user did "
    "not imply. If the user asks about a specific named entity (a "
    "state, a product, a month) that was not part of the supported "
    "analyses, keep that detail in the rewritten question rather than "
    "dropping it -- do not silently generalize it away.\n"
    "- If the question is already standalone and unambiguous, return it "
    "unchanged.\n"
    "- Return only the rewritten question as plain text. No preamble, "
    "no quotation marks, no explanation."
)


def _build_user_prompt(
    question: str,
    history: list[tuple[str, str]],
) -> str:
    """
    Build the rewrite prompt from recent question/topic history.
    """
    if not history:
        return f"New question: {question}"

    history_lines = "\n".join(
        f'- Prior question: "{prior_question}" (matched analysis: {prior_topic})'
        for prior_question, prior_topic in history
    )

    return (
        f"Conversation so far:\n{history_lines}\n\n"
        f'Follow-up question: "{question}"\n\n'
        "Rewrite the follow-up question as a single standalone question."
    )


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
        raise RuntimeError("The rewrite model returned no text.")

    return content.strip()


def rewrite_question_with_context(
    question: str,
    history: list[tuple[str, str]],
    *,
    text_generator: RewriteGenerator | None = None,
    client: OpenAI | None = None,
    settings: LLMSettings | None = None,
) -> str:
    """
    Resolve a follow-up question into a standalone question using recent
    conversation history, before it reaches the deterministic router.

    This never raises. Any failure (missing credentials, network error,
    empty response) falls back to the original question unchanged, so a
    rewrite problem can never block the deterministic evidence pipeline.
    A custom text_generator can be injected for testing.
    """
    cleaned_question = question.strip()

    if not cleaned_question or not history:
        return cleaned_question

    user_prompt = _build_user_prompt(
        cleaned_question,
        history,
    )

    try:
        if text_generator is not None:
            rewritten = text_generator(
                REWRITE_SYSTEM_PROMPT,
                user_prompt,
            )
        else:
            resolved_settings = (
                settings if settings is not None else load_llm_settings()
            )

            resolved_client = (
                client if client is not None else create_llm_client(resolved_settings)
            )

            rewritten = _generate_with_openai_client(
                system_prompt=REWRITE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                client=resolved_client,
                model=resolved_settings.model,
            )
    except Exception:
        LOGGER.exception(
        "Question rewriting failed; using the original question."
        )
        return cleaned_question

    rewritten = rewritten.strip().strip('"').strip()

    return rewritten if rewritten else cleaned_question

