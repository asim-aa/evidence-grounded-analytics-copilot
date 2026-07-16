from __future__ import annotations

from collections.abc import Callable

import duckdb

from app.evidence.handlers import (
    handle_core_kpis,
    handle_delivery_by_state,
    handle_late_vs_on_time,
    handle_monthly_revenue_trend,
    handle_revenue_by_category,
    handle_revenue_by_state,
    handle_unsupported_question,
)
from app.evidence.models import (
    AnalysisType,
    EvidenceResult,
)


EvidenceHandler = Callable[
    [
        str,
        duckdb.DuckDBPyConnection,
    ],
    EvidenceResult,
]


HANDLER_REGISTRY: dict[
    AnalysisType,
    EvidenceHandler,
] = {
    AnalysisType.CORE_KPIS: handle_core_kpis,
    AnalysisType.MONTHLY_REVENUE_TREND: (handle_monthly_revenue_trend),
    AnalysisType.REVENUE_BY_CATEGORY: (handle_revenue_by_category),
    AnalysisType.REVENUE_BY_STATE: handle_revenue_by_state,
    AnalysisType.DELIVERY_BY_STATE: handle_delivery_by_state,
    AnalysisType.LATE_VS_ON_TIME: handle_late_vs_on_time,
    AnalysisType.UNSUPPORTED: handle_unsupported_question,
}
