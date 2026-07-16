from __future__ import annotations

import re

from app.evidence.models import (
    AnalysisType,
    RouteDecision,
)


def _normalize_question(question: str) -> str:
    """
    Normalize a natural-language question for rule matching.
    """
    normalized = question.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized


def route_question(
    question: str,
) -> RouteDecision:
    """
    Map a natural-language business question to a supported analysis.

    More specific analytical patterns are checked before broader ones.
    """
    normalized = _normalize_question(question)

    if not normalized:
        return RouteDecision(
            analysis_type=AnalysisType.UNSUPPORTED,
            matched_rule="empty_question",
            normalized_question=normalized,
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
        "rating",
        "customer satisfaction",
    )

    if any(term in normalized for term in late_terms) and (
        any(term in normalized for term in on_time_terms)
        or any(term in normalized for term in review_terms)
    ):
        return RouteDecision(
            analysis_type=AnalysisType.LATE_VS_ON_TIME,
            matched_rule=(
                "question compares late delivery with on-time delivery or reviews"
            ),
            normalized_question=normalized,
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

    if any(term in normalized for term in geography_terms) and any(
        term in normalized for term in delivery_terms
    ):
        return RouteDecision(
            analysis_type=AnalysisType.DELIVERY_BY_STATE,
            matched_rule=("question combines geography and delivery performance"),
            normalized_question=normalized,
        )

    category_terms = (
        "category",
        "categories",
        "product category",
        "product categories",
    )

    revenue_terms = (
        "revenue",
        "sales",
        "money",
        "income",
    )

    if any(term in normalized for term in category_terms) and any(
        term in normalized for term in revenue_terms
    ):
        return RouteDecision(
            analysis_type=AnalysisType.REVENUE_BY_CATEGORY,
            matched_rule=("question combines product category and revenue"),
            normalized_question=normalized,
        )

    if any(term in normalized for term in geography_terms) and any(
        term in normalized for term in revenue_terms
    ):
        return RouteDecision(
            analysis_type=AnalysisType.REVENUE_BY_STATE,
            matched_rule=("question combines geography and revenue"),
            normalized_question=normalized,
        )

    trend_terms = (
        "month",
        "monthly",
        "trend",
        "growth",
        "over time",
        "changed",
        "change over time",
    )

    if any(term in normalized for term in revenue_terms) and any(
        term in normalized for term in trend_terms
    ):
        return RouteDecision(
            analysis_type=AnalysisType.MONTHLY_REVENUE_TREND,
            matched_rule=("question combines revenue and time-based change"),
            normalized_question=normalized,
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

    if any(term in normalized for term in overview_terms):
        return RouteDecision(
            analysis_type=AnalysisType.CORE_KPIS,
            matched_rule="question requests a business KPI overview",
            normalized_question=normalized,
        )

    return RouteDecision(
        analysis_type=AnalysisType.UNSUPPORTED,
        matched_rule="no supported deterministic route matched",
        normalized_question=normalized,
    )
