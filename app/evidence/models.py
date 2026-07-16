from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AnalysisType(StrEnum):
    """
    Supported deterministic analysis routes.
    """

    CORE_KPIS = "core_kpis"
    MONTHLY_REVENUE_TREND = "monthly_revenue_trend"
    REVENUE_BY_CATEGORY = "revenue_by_category"
    REVENUE_BY_STATE = "revenue_by_state"
    DELIVERY_BY_STATE = "delivery_by_state"
    LATE_VS_ON_TIME = "late_vs_on_time"
    UNSUPPORTED = "unsupported"


class RouteDecision(BaseModel):
    """
    Result returned by the deterministic question router.
    """

    analysis_type: AnalysisType
    matched_rule: str
    normalized_question: str


class EvidenceResult(BaseModel):
    """
    Standardized evidence returned by every analysis handler.
    """

    question: str
    analysis_type: AnalysisType
    supported: bool = True

    summary: str

    metrics: dict[str, Any] = Field(default_factory=dict)

    supporting_rows: list[dict[str, Any]] = Field(default_factory=list)

    methodology: dict[str, Any] = Field(default_factory=dict)

    warnings: list[str] = Field(default_factory=list)
