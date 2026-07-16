from __future__ import annotations

import re

from app.evidence.models import (
    AnalysisType,
    RouteDecision,
)


def _normalize_question(question: str) -> str:
    """
    Normalize a natural-language question for deterministic matching.
    """
    normalized = question.strip().lower()
    return re.sub(r"\s+", " ", normalized)


def _contains_any(
    text: str,
    terms: tuple[str, ...],
) -> bool:
    """
    Return whether the text contains at least one supplied term.
    """
    return any(term in text for term in terms)


def route_question(
    question: str,
) -> RouteDecision:
    """
    Map a natural-language business question to a supported analysis.

    More specific routes are checked before broader routes so an
    investigation request is not incorrectly treated as a basic trend.
    """
    normalized = _normalize_question(question)

    if not normalized:
        return RouteDecision(
            analysis_type=AnalysisType.UNSUPPORTED,
            matched_rule="empty_question",
            normalized_question=normalized,
        )

    revenue_terms = (
        "revenue",
        "sales",
        "money",
        "income",
    )

    investigation_terms = (
        "why",
        "what drove",
        "what caused",
        "driver",
        "drivers",
        "contributed",
        "contribution",
        "reason",
        "reasons",
    )

    change_terms = (
        "decline",
        "declined",
        "decrease",
        "decreased",
        "drop",
        "dropped",
        "fall",
        "fell",
        "increase",
        "increased",
        "growth",
        "change",
        "changed",
    )

    late_terms = (
        "late",
        "delayed",
        "delay",
    )

    on_time_terms = (
        "on time",
        "on-time",
        "ontime",
    )

    review_terms = (
        "review",
        "reviews",
        "rating",
        "ratings",
        "customer satisfaction",
    )

    geography_terms = (
        "state",
        "states",
        "region",
        "regions",
        "geography",
        "geographic",
    )

    delivery_terms = (
        "delivery",
        "late",
        "delay",
        "shipping",
        "fulfillment",
    )

    category_terms = (
        "category",
        "categories",
        "product category",
        "product categories",
    )

    trend_terms = (
        "month",
        "monthly",
        "trend",
        "growth",
        "over time",
        "changed",
        "change over time",
        "decline",
        "decrease",
        "increase",
    )

    overview_terms = (
        "kpi",
        "kpis",
        "key metrics",
        "business metrics",
        "overall metrics",
        "overview",
        "business overview",
        "summary of the business",
    )

    # Most specific revenue route: multi-analysis investigation.
    if (
        _contains_any(normalized, revenue_terms)
        and _contains_any(normalized, investigation_terms)
        and (
            _contains_any(normalized, change_terms)
            or "what drove" in normalized
            or "what caused" in normalized
        )
    ):
        return RouteDecision(
            analysis_type=(AnalysisType.REVENUE_CHANGE_INVESTIGATION),
            matched_rule=("question requests drivers of a revenue change"),
            normalized_question=normalized,
        )

    # Comparison of delivery timeliness and customer reviews.
    if _contains_any(normalized, late_terms) and (
        _contains_any(normalized, on_time_terms)
        or _contains_any(normalized, review_terms)
    ):
        return RouteDecision(
            analysis_type=AnalysisType.LATE_VS_ON_TIME,
            matched_rule=(
                "question compares late delivery with on-time delivery or reviews"
            ),
            normalized_question=normalized,
        )

    # Geographic delivery-performance route.
    if _contains_any(normalized, geography_terms) and _contains_any(
        normalized, delivery_terms
    ):
        return RouteDecision(
            analysis_type=AnalysisType.DELIVERY_BY_STATE,
            matched_rule=("question combines geography and delivery performance"),
            normalized_question=normalized,
        )

    # Revenue segmented by product category.
    if _contains_any(normalized, category_terms) and _contains_any(
        normalized, revenue_terms
    ):
        return RouteDecision(
            analysis_type=AnalysisType.REVENUE_BY_CATEGORY,
            matched_rule=("question combines product category and revenue"),
            normalized_question=normalized,
        )

    # Revenue segmented by geography.
    if _contains_any(normalized, geography_terms) and _contains_any(
        normalized, revenue_terms
    ):
        return RouteDecision(
            analysis_type=AnalysisType.REVENUE_BY_STATE,
            matched_rule=("question combines geography and revenue"),
            normalized_question=normalized,
        )

    # Basic time-series route.
    if _contains_any(normalized, revenue_terms) and _contains_any(
        normalized, trend_terms
    ):
        return RouteDecision(
            analysis_type=AnalysisType.MONTHLY_REVENUE_TREND,
            matched_rule=("question combines revenue and time-based change"),
            normalized_question=normalized,
        )

    # Overall business summary.
    if _contains_any(normalized, overview_terms):
        return RouteDecision(
            analysis_type=AnalysisType.CORE_KPIS,
            matched_rule=("question requests a business KPI overview"),
            normalized_question=normalized,
        )

    return RouteDecision(
        analysis_type=AnalysisType.UNSUPPORTED,
        matched_rule=("no supported deterministic route matched"),
        normalized_question=normalized,
    )
