from app.evidence.models import (
    AnalysisType,
    EvidenceResult,
)
from app.llm.explainer import (
    build_unsupported_explanation,
    generate_grounded_explanation,
)
from app.llm.prompts import (
    SYSTEM_PROMPT,
    build_explanation_prompt,
)


def create_supported_evidence() -> EvidenceResult:
    """
    Create a compact evidence object for explanation tests.
    """
    return EvidenceResult(
        question="Why did revenue decline?",
        analysis_type=(AnalysisType.REVENUE_CHANGE_INVESTIGATION),
        supported=True,
        summary=(
            "Revenue declined because order volume and "
            "average order value both decreased."
        ),
        metrics={
            "revenue_change_percentage": -13.19,
            "order_count_change_percentage": -10.11,
            "average_order_value_change_percentage": -3.42,
        },
        supporting_rows=[
            {
                "product_category": "watches_gifts",
                "change_amount": -36987.10,
            }
        ],
        methodology={
            "revenue_metric": "SUM(item_price)",
        },
        warnings=[("The analysis is descriptive and does not establish causation.")],
    )


def test_explanation_prompt_contains_verified_evidence() -> None:
    evidence = create_supported_evidence()

    prompt = build_explanation_prompt(evidence)

    assert evidence.question in prompt
    assert "-13.19" in prompt
    assert "watches_gifts" in prompt
    assert "SUM(item_price)" in prompt
    assert "does not establish causation" in prompt


def test_system_prompt_contains_grounding_rules() -> None:
    assert "Use only facts" in SYSTEM_PROMPT
    assert "Never invent numbers" in SYSTEM_PROMPT
    assert "Never claim causation" in SYSTEM_PROMPT
    assert "[metric:<metric_key>]" in SYSTEM_PROMPT


def test_injected_generator_returns_explanation() -> None:
    evidence = create_supported_evidence()

    captured_prompts: dict[str, str] = {}

    def fake_generator(
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        captured_prompts["system"] = system_prompt
        captured_prompts["user"] = user_prompt

        return (
            "Direct answer:\n"
            "Revenue declined 13.19%. "
            "[metric:revenue_change_percentage]"
        )

    explanation = generate_grounded_explanation(
        evidence,
        text_generator=fake_generator,
    )

    assert "Revenue declined 13.19%" in explanation
    assert "[metric:revenue_change_percentage]" in explanation

    assert captured_prompts["system"] == SYSTEM_PROMPT
    assert evidence.question in captured_prompts["user"]


def test_empty_generator_response_raises_error() -> None:
    evidence = create_supported_evidence()

    def empty_generator(
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        del system_prompt
        del user_prompt
        return "   "

    try:
        generate_grounded_explanation(
            evidence,
            text_generator=empty_generator,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected RuntimeError for an empty response.")


def test_unsupported_evidence_does_not_call_model() -> None:
    evidence = EvidenceResult(
        question="Predict next year's revenue.",
        analysis_type=AnalysisType.UNSUPPORTED,
        supported=False,
        summary=("This question is not supported by the current analytics engine."),
        warnings=["Forecasting is not currently supported."],
    )

    generator_was_called = False

    def forbidden_generator(
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        nonlocal generator_was_called
        generator_was_called = True

        del system_prompt
        del user_prompt

        return "This should not be returned."

    explanation = generate_grounded_explanation(
        evidence,
        text_generator=forbidden_generator,
    )

    assert generator_was_called is False
    assert "not supported" in explanation
    assert "Forecasting is not currently supported" in explanation


def test_deterministic_unsupported_explanation() -> None:
    evidence = EvidenceResult(
        question="Predict customer churn.",
        analysis_type=AnalysisType.UNSUPPORTED,
        supported=False,
        summary="No supported evidence is available.",
        warnings=["Customer churn is not currently modeled."],
    )

    explanation = build_unsupported_explanation(evidence)

    assert "No supported evidence is available" in explanation
    assert "Customer churn is not currently modeled" in explanation
