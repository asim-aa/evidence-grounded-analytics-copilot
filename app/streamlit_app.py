from __future__ import annotations

import re
from typing import Any, Literal
import pandas as pd
import plotly.express as px
import streamlit as st
from app.analytics.metrics import open_analytics_connection
from app.evidence.engine import answer_question_with_evidence
from app.evidence.models import AnalysisType, EvidenceResult
from app.llm.explainer import generate_grounded_explanation

EXAMPLE_QUESTIONS = (
    "Why did revenue decline in June 2018?",
    "What drove the largest revenue decline?",
    "Which product categories generate the most revenue?",
    "Which states generate the most revenue?",
    "Which states have the worst delivery performance?",
    "How do late deliveries affect customer review scores?",
    "Give me an overview of the main business KPIs.",
)

DeltaColor = Literal[
    "normal",
    "inverse",
    "off",
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "violet",
    "gray",
    "grey",
    "primary",
]


FOLLOW_UP_PREFIXES = (
    "what about",
    "how about",
    "and what",
    "and the",
    "what caused",
    "what drove",
    "why is that",
    "why did that",
    "compared with that",
    "for that",
    "in that case",
)

FOLLOW_UP_PRONOUNS = {
    "that",
    "those",
    "them",
    "it",
}

TOPIC_FRAGMENTS = {
    "state",
    "states",
    "the state",
    "the states",
    "category",
    "categories",
    "product category",
    "product categories",
    "orders",
    "order count",
    "order volume",
    "aov",
    "average order value",
    "delivery",
    "delivery performance",
    "reviews",
    "review score",
    "review scores",
}

MONTH_PATTERN = re.compile(
    r"\b(?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\s+\d{4}\b|"
    r"\b\d{4}-\d{2}\b",
    re.IGNORECASE,
)


def inject_custom_styles() -> None:
    """
    Add application-specific visual styling.

    Streamlit still controls the layout and widgets. The CSS only
    improves spacing, typography, cards, badges, and chat presentation.
    """
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1320px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        [data-testid="stSidebar"] {
            border-right: 1px solid rgba(148, 163, 184, 0.18);
        }

        [data-testid="stSidebar"] .block-container {
            padding-top: 1.5rem;
        }

        .hero-card {
            position: relative;
            overflow: hidden;
            padding: 2.2rem 2.4rem;
            margin-bottom: 1.5rem;
            border: 1px solid rgba(167, 139, 250, 0.30);
            border-radius: 24px;
            background:
                radial-gradient(
                    circle at top right,
                    rgba(139, 92, 246, 0.28),
                    transparent 38%
                ),
                linear-gradient(
                    135deg,
                    rgba(30, 41, 72, 0.96),
                    rgba(15, 23, 42, 0.96)
                );
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.24);
        }

        .hero-title {
            margin: 0;
            font-size: clamp(2rem, 4vw, 3.6rem);
            font-weight: 800;
            line-height: 1.08;
            letter-spacing: -0.04em;
            background: linear-gradient(
                90deg,
                #F8FAFC,
                #C4B5FD,
                #7DD3FC
            );
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero-subtitle {
            max-width: 850px;
            margin-top: 1rem;
            margin-bottom: 1.2rem;
            color: #CBD5E1;
            font-size: 1.05rem;
            line-height: 1.7;
        }

        .badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            padding: 0.42rem 0.72rem;
            border: 1px solid rgba(167, 139, 250, 0.30);
            border-radius: 999px;
            background: rgba(139, 92, 246, 0.13);
            color: #DDD6FE;
            font-size: 0.82rem;
            font-weight: 700;
        }

        .supported-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            width: fit-content;
            margin-bottom: 0.9rem;
            padding: 0.38rem 0.68rem;
            border: 1px solid rgba(52, 211, 153, 0.34);
            border-radius: 999px;
            background: rgba(16, 185, 129, 0.14);
            color: #A7F3D0;
            font-size: 0.80rem;
            font-weight: 750;
        }

        .unsupported-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            width: fit-content;
            margin-bottom: 0.9rem;
            padding: 0.38rem 0.68rem;
            border: 1px solid rgba(248, 113, 113, 0.34);
            border-radius: 999px;
            background: rgba(239, 68, 68, 0.14);
            color: #FECACA;
            font-size: 0.80rem;
            font-weight: 750;
        }

        .section-eyebrow {
            margin-bottom: 0.25rem;
            color: #A78BFA;
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .section-heading {
            margin-top: 0;
            margin-bottom: 0.9rem;
            color: #F8FAFC;
            font-size: 1.35rem;
            font-weight: 800;
        }

        .answer-card {
            padding: 1.35rem 1.45rem;
            border: 1px solid rgba(96, 165, 250, 0.22);
            border-radius: 18px;
            background:
                linear-gradient(
                    135deg,
                    rgba(30, 41, 59, 0.86),
                    rgba(17, 24, 39, 0.92)
                );
            box-shadow: 0 12px 35px rgba(0, 0, 0, 0.16);
        }

        [data-testid="stMetric"] {
            min-height: 132px;
            padding: 1.05rem 1.1rem;
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 18px;
            background:
                linear-gradient(
                    145deg,
                    rgba(30, 41, 59, 0.92),
                    rgba(17, 24, 39, 0.92)
                );
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.17);
        }

        [data-testid="stMetricLabel"] {
            color: #94A3B8;
            font-weight: 700;
        }

        [data-testid="stMetricValue"] {
            color: #F8FAFC;
            font-weight: 850;
        }

        [data-testid="stChatMessage"] {
            padding: 1rem 1.1rem;
            border: 1px solid rgba(148, 163, 184, 0.12);
            border-radius: 20px;
            background: rgba(15, 23, 42, 0.48);
        }

        [data-testid="stDataFrame"] {
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 16px;
            overflow: hidden;
        }

        button[kind="secondary"] {
            border: 1px solid rgba(167, 139, 250, 0.24);
            background: rgba(139, 92, 246, 0.08);
        }

        button[kind="secondary"]:hover {
            border-color: rgba(167, 139, 250, 0.70);
            background: rgba(139, 92, 246, 0.18);
        }

        div[data-baseweb="tab-list"] {
            gap: 0.55rem;
        }

        button[data-baseweb="tab"] {
            border-radius: 12px;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .sidebar-brand {
            padding: 1rem;
            margin-bottom: 1.2rem;
            border: 1px solid rgba(167, 139, 250, 0.22);
            border-radius: 18px;
            background: rgba(139, 92, 246, 0.09);
        }

        .sidebar-title {
            margin: 0;
            color: #F8FAFC;
            font-size: 1.1rem;
            font-weight: 850;
        }

        .sidebar-copy {
            margin-top: 0.5rem;
            margin-bottom: 0;
            color: #94A3B8;
            font-size: 0.86rem;
            line-height: 1.55;
        }

        .footer-note {
            margin-top: 1.5rem;
            color: #64748B;
            font-size: 0.78rem;
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_session_state() -> None:
    """
    Initialize chat history for the current browser session.
    """
    if "messages" not in st.session_state:
        st.session_state.messages = []


def recent_topic_history(
    limit: int = 2,
) -> list[tuple[str, str]]:
    """
    Return the most recent (resolved question, analysis_type) pairs.

    Uses the resolved (post-rewrite) form of each prior question, so a
    chain of follow-ups builds on the standalone version of each turn
    rather than on raw follow-up phrasing like "what about that". Only
    turns that produced evidence are included, so an earlier failed or
    unsupported turn does not confuse later rewrites.
    """
    history: list[tuple[str, str]] = []
    pending_question: str | None = None

    for message in st.session_state.messages:
        if message["role"] == "user":
            pending_question = str(
                message.get("resolved_question") or message["content"]
            )
            continue

        if message["role"] == "assistant" and pending_question is not None:
            evidence_data = message.get("evidence")

            if evidence_data and evidence_data.get("supported") is True:
                analysis_type = str(
                    evidence_data.get(
                        "analysis_type",
                        "unsupported",
                    )
                )

                history.append(
                    (
                        pending_question,
                        analysis_type,
                    )
                )

            pending_question = None

    return history[-limit:]


def needs_context_resolution(
    question: str,
) -> bool:
    """
    Return True only when a question clearly depends on earlier context.

    Complete standalone questions bypass context resolution and go
    directly to the deterministic evidence pipeline.
    """
    normalized_question = " ".join(question.strip().lower().split())
    normalized_without_punctuation = normalized_question.strip(" ?.!,:;")

    if not normalized_without_punctuation:
        return False

    if normalized_without_punctuation in TOPIC_FRAGMENTS:
        return True

    if any(normalized_question.startswith(prefix) for prefix in FOLLOW_UP_PREFIXES):
        return True

    tokens = set(
        re.findall(
            r"[a-z0-9]+",
            normalized_question,
        )
    )

    return bool(tokens & FOLLOW_UP_PRONOUNS) and len(tokens) <= 12


def _extract_month_reference(
    question: str,
) -> str | None:
    """
    Extract a named month/year or YYYY-MM reference from a question.
    """
    match = MONTH_PATTERN.search(question)

    return match.group(0) if match else None


def resolve_follow_up_question(
    question: str,
    history: list[tuple[str, str]],
) -> str:
    """
    Resolve common follow-ups without making a second LLM call.

    This preserves the original stable request path: one deterministic
    evidence query followed by one grounded explanation call.
    """
    cleaned_question = question.strip()

    if not history or not needs_context_resolution(cleaned_question):
        return cleaned_question

    previous_question, previous_analysis_type = history[-1]
    previous_question = previous_question.strip().rstrip(" ?.!")

    normalized_question = cleaned_question.lower()
    month_reference = _extract_month_reference(
        cleaned_question
    ) or _extract_month_reference(previous_question)

    revenue_change_context = (
        previous_analysis_type == AnalysisType.REVENUE_CHANGE_INVESTIGATION.value
        or (
            "revenue" in previous_question.lower()
            and any(
                word in previous_question.lower()
                for word in ("decline", "change", "decrease", "drop")
            )
        )
    )

    if "state" in normalized_question:
        if revenue_change_context and month_reference:
            return (
                "Which states contributed most to the revenue "
                f"change in {month_reference}?"
            )

        return "Which states generate the most revenue?"

    if any(
        term in normalized_question for term in ("category", "categories", "product")
    ):
        if revenue_change_context and month_reference:
            return (
                "Which product categories contributed most to the "
                f"revenue change in {month_reference}?"
            )

        return "Which product categories generate the most revenue?"

    if any(
        term in normalized_question
        for term in ("average order value", "aov", "order value")
    ):
        if revenue_change_context and month_reference:
            return (
                "How much did average order value contribute to the "
                f"revenue change in {month_reference}?"
            )

        return f"{previous_question}. Focus on average order value."

    if any(term in normalized_question for term in ("order", "orders", "volume")):
        if revenue_change_context and month_reference:
            return (
                "How much did order count contribute to the revenue "
                f"change in {month_reference}?"
            )

        return f"{previous_question}. Focus on order volume."

    if any(term in normalized_question for term in ("delivery", "late", "shipping")):
        return f"{previous_question}. Focus on delivery performance."

    if any(
        term in normalized_question for term in ("review", "reviews", "rating", "score")
    ):
        return f"{previous_question}. Focus on customer review scores."

    if month_reference:
        if "revenue" in previous_question.lower():
            return f"What drove the revenue change in {month_reference}?"

        return f"{previous_question} for {month_reference}?"

    if any(
        phrase in normalized_question
        for phrase in (
            "what caused",
            "what drove",
            "why is that",
            "why did that",
            "why did it",
        )
    ):
        return f"What drove the result described by this question: {previous_question}?"

    # Unknown follow-ups are left untouched rather than inventing context.
    return cleaned_question


def retrieve_evidence(
    question: str,
) -> EvidenceResult:
    """
    Run deterministic routing and evidence retrieval.
    """
    connection = open_analytics_connection()

    try:
        return answer_question_with_evidence(
            question,
            connection,
        )
    finally:
        connection.close()


def run_copilot(
    question: str,
) -> tuple[EvidenceResult, str]:
    """
    Execute the complete copilot pipeline.
    """
    evidence = retrieve_evidence(question)

    explanation = generate_grounded_explanation(evidence)

    return evidence, explanation


def format_currency(value: Any) -> str:
    """
    Format a value as compact currency.
    """
    numeric_value = float(value)
    absolute_value = abs(numeric_value)

    if absolute_value >= 1_000_000:
        return f"${numeric_value / 1_000_000:,.2f}M"

    if absolute_value >= 1_000:
        return f"${numeric_value / 1_000:,.1f}K"

    return f"${numeric_value:,.2f}"


def format_integer(value: Any) -> str:
    """
    Format a value as an integer.
    """
    return f"{int(value):,}"


def format_percentage(value: Any) -> str:
    """
    Format a value as a percentage.
    """
    return f"{float(value):,.2f}%"


def format_decimal(value: Any) -> str:
    """
    Format a value to two decimal places.
    """
    return f"{float(value):,.2f}"


def metric_card(
    column: Any,
    label: str,
    value: str,
    *,
    delta: str | None = None,
    help_text: str | None = None,
    delta_color: DeltaColor = "normal",
) -> None:
    """
    Render one metric card inside a supplied Streamlit column.
    """
    with column:
        st.metric(
            label=label,
            value=value,
            delta=delta,
            help=help_text,
            delta_color=delta_color,
            border=True,
        )


def render_metric_cards(
    evidence: EvidenceResult,
) -> None:
    """
    Render analysis-specific headline metrics.
    """
    metrics = evidence.metrics

    if not metrics:
        return

    analysis_type = evidence.analysis_type

    if analysis_type == AnalysisType.CORE_KPIS:
        columns = st.columns(5)

        metric_card(
            columns[0],
            "💰 Item revenue",
            format_currency(metrics["item_revenue"]),
            help_text="Item revenue excluding freight.",
        )

        metric_card(
            columns[1],
            "🛒 Orders",
            format_integer(metrics["order_count"]),
            help_text="Distinct marketplace orders.",
        )

        metric_card(
            columns[2],
            "🧾 Avg. order value",
            format_currency(metrics["average_order_value"]),
        )

        metric_card(
            columns[3],
            "🚚 Late delivery",
            format_percentage(metrics["late_delivery_rate_percentage"]),
            delta_color="inverse",
        )

        metric_card(
            columns[4],
            "⭐ Review score",
            format_decimal(metrics["average_review_score"]),
        )

    elif analysis_type == AnalysisType.REVENUE_CHANGE_INVESTIGATION:
        columns = st.columns(4)

        metric_card(
            columns[0],
            "📉 Revenue change",
            format_percentage(metrics["revenue_change_percentage"]),
            delta=format_currency(metrics["revenue_change_amount"]),
            delta_color="normal",
        )

        metric_card(
            columns[1],
            "🛒 Order change",
            format_percentage(metrics["order_count_change_percentage"]),
            delta=(f"{format_integer(metrics['current_order_count'])} current orders"),
        )

        metric_card(
            columns[2],
            "🧾 AOV change",
            format_percentage(metrics["average_order_value_change_percentage"]),
            delta=format_currency(metrics["current_average_order_value"]),
        )

        metric_card(
            columns[3],
            "🔍 Larger movement",
            str(metrics["larger_relative_component"]).title(),
            help_text=(
                "The component with the larger relative month-over-month change."
            ),
        )

    elif analysis_type == AnalysisType.REVENUE_BY_CATEGORY:
        columns = st.columns(4)

        metric_card(
            columns[0],
            "🏆 Leading category",
            str(metrics["leading_category"])
            .replace(
                "_",
                " ",
            )
            .title(),
        )

        metric_card(
            columns[1],
            "💰 Category revenue",
            format_currency(metrics["leading_category_revenue"]),
        )

        metric_card(
            columns[2],
            "📊 Revenue share",
            format_percentage(metrics["leading_category_revenue_share_percentage"]),
        )

        metric_card(
            columns[3],
            "🛒 Category orders",
            format_integer(metrics["leading_category_order_count"]),
        )

    elif analysis_type == AnalysisType.REVENUE_BY_STATE:
        columns = st.columns(4)

        metric_card(
            columns[0],
            "🏆 Leading state",
            str(metrics["leading_state"]),
        )

        metric_card(
            columns[1],
            "💰 State revenue",
            format_currency(metrics["leading_state_revenue"]),
        )

        metric_card(
            columns[2],
            "📊 Revenue share",
            format_percentage(metrics["leading_state_revenue_share_percentage"]),
        )

        metric_card(
            columns[3],
            "🛒 State orders",
            format_integer(metrics["leading_state_order_count"]),
        )

    elif analysis_type == AnalysisType.DELIVERY_BY_STATE:
        columns = st.columns(4)

        metric_card(
            columns[0],
            "⚠️ Highest late-rate state",
            str(metrics["highest_late_delivery_state"]),
        )

        metric_card(
            columns[1],
            "🚚 Late-delivery rate",
            format_percentage(metrics["late_delivery_rate_percentage"]),
            delta_color="inverse",
        )

        metric_card(
            columns[2],
            "⏱️ Avg. delivery time",
            f"{format_decimal(metrics['average_delivery_days'])} days",
        )

        metric_card(
            columns[3],
            "⭐ Avg. review score",
            format_decimal(metrics["average_review_score"]),
        )

    elif analysis_type == AnalysisType.LATE_VS_ON_TIME:
        columns = st.columns(4)

        metric_card(
            columns[0],
            "⭐ Late-order score",
            format_decimal(metrics["late_average_review_score"]),
        )

        metric_card(
            columns[1],
            "⭐ On-time score",
            format_decimal(metrics["on_time_average_review_score"]),
        )

        metric_card(
            columns[2],
            "📏 Review gap",
            format_decimal(metrics["review_score_gap"]),
            delta="On-time advantage",
        )

        metric_card(
            columns[3],
            "🚚 Late orders",
            format_integer(metrics["late_order_count"]),
        )

    elif analysis_type == AnalysisType.MONTHLY_REVENUE_TREND:
        columns = st.columns(4)

        metric_card(
            columns[0],
            "📅 Latest month",
            str(metrics["latest_complete_month"]),
        )

        metric_card(
            columns[1],
            "💰 Latest revenue",
            format_currency(metrics["latest_item_revenue"]),
        )

        metric_card(
            columns[2],
            "📉 Monthly change",
            format_percentage(metrics["month_over_month_growth_percentage"]),
        )

        metric_card(
            columns[3],
            "📅 Previous month",
            str(metrics["previous_complete_month"]),
        )


def prepare_evidence_dataframe(
    evidence: EvidenceResult,
) -> pd.DataFrame:
    """
    Convert supporting rows into a presentation-friendly dataframe.
    """
    dataframe = pd.DataFrame(evidence.supporting_rows)

    if dataframe.empty:
        return dataframe

    dataframe.index = pd.RangeIndex(
        start=1,
        stop=len(dataframe) + 1,
        name="Evidence row",
    )

    return dataframe


def render_chart(
    evidence: EvidenceResult,
) -> None:
    """
    Render one chart appropriate for the selected analysis route.
    """
    dataframe = prepare_evidence_dataframe(evidence)

    if dataframe.empty:
        return

    analysis_type = evidence.analysis_type

    if analysis_type == AnalysisType.REVENUE_BY_CATEGORY:
        chart_data = dataframe.head(10).copy()

        chart_data["product_category"] = (
            chart_data["product_category"].astype(str).str.replace("_", " ").str.title()
        )

        figure = px.bar(
            chart_data.sort_values(
                "item_revenue",
                ascending=True,
            ),
            x="item_revenue",
            y="product_category",
            orientation="h",
            title="Top product categories by item revenue",
            labels={
                "item_revenue": "Item revenue",
                "product_category": "Product category",
            },
            text_auto=True,
        )
        figure.update_traces(
            texttemplate="%{x:.3s}",
            textposition="outside",
        )

    elif analysis_type == AnalysisType.REVENUE_BY_STATE:
        chart_data = dataframe.head(10).copy()

        figure = px.bar(
            chart_data,
            x="customer_state",
            y="item_revenue",
            title="Top customer states by item revenue",
            labels={
                "customer_state": "Customer state",
                "item_revenue": "Item revenue",
            },
            text_auto=True,
        )
        figure.update_traces(
            texttemplate="%{y:.3s}",
            textposition="outside",
        )

    elif analysis_type == AnalysisType.DELIVERY_BY_STATE:
        chart_data = dataframe.head(10).copy()

        figure = px.bar(
            chart_data.sort_values(
                "late_delivery_rate_percentage",
                ascending=True,
            ),
            x="late_delivery_rate_percentage",
            y="customer_state",
            orientation="h",
            title="States with the highest late-delivery rates",
            labels={
                "customer_state": "Customer state",
                "late_delivery_rate_percentage": ("Late-delivery rate (%)"),
            },
            text_auto=True,
        )
        figure.update_traces(
            texttemplate="%{x:.2f}%",
            textposition="outside",
        )

    elif analysis_type == AnalysisType.LATE_VS_ON_TIME:
        chart_data = dataframe.copy()

        figure = px.bar(
            chart_data,
            x="delivery_status",
            y="average_review_score",
            title="Average review score by delivery status",
            labels={
                "delivery_status": "Delivery status",
                "average_review_score": "Average review score",
            },
            text_auto=True,
        )
        figure.update_traces(
            texttemplate="%{y:.2f}",
            textposition="outside",
        )

    elif analysis_type == AnalysisType.MONTHLY_REVENUE_TREND:
        chart_data = dataframe.copy()

        chart_data["purchase_month_start"] = pd.to_datetime(
            chart_data["purchase_month_start"]
        )

        figure = px.line(
            chart_data,
            x="purchase_month_start",
            y="item_revenue",
            markers=True,
            title="Complete-month item revenue trend",
            labels={
                "purchase_month_start": "Month",
                "item_revenue": "Item revenue",
            },
        )

    elif analysis_type == AnalysisType.REVENUE_CHANGE_INVESTIGATION:
        category_data = dataframe[
            dataframe["evidence_scope"] == "category_change"
        ].copy()

        if category_data.empty:
            return

        category_data["product_category"] = (
            category_data["product_category"]
            .astype(str)
            .str.replace("_", " ")
            .str.title()
        )

        figure = px.bar(
            category_data.sort_values(
                "change_amount",
                ascending=True,
            ),
            x="change_amount",
            y="product_category",
            orientation="h",
            title="Largest category contributors to revenue change",
            labels={
                "change_amount": "Revenue change",
                "product_category": "Product category",
            },
            text_auto=True,
        )
        figure.update_traces(
            texttemplate="%{x:,.0f}",
            textposition="outside",
        )

    else:
        return

    figure.update_layout(
        height=430,
        margin={
            "l": 10,
            "r": 10,
            "t": 60,
            "b": 10,
        },
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={
            "color": "#CBD5E1",
        },
        title={
            "font": {
                "size": 20,
                "color": "#F8FAFC",
            }
        },
        xaxis={
            "gridcolor": "rgba(148,163,184,0.14)",
        },
        yaxis={
            "gridcolor": "rgba(148,163,184,0.08)",
        },
    )

    figure.update_traces(
        marker_color="#8B5CF6",
        marker_line_color="#C4B5FD",
        marker_line_width=1,
    )

    st.plotly_chart(
        figure,
        width="stretch",
        config={
            "displayModeBar": False,
        },
    )


def render_supporting_rows(
    evidence: EvidenceResult,
) -> None:
    """
    Display supporting evidence as an interactive table.
    """
    dataframe = prepare_evidence_dataframe(evidence)

    if dataframe.empty:
        st.info(
            "No supporting rows were returned for this answer.",
            icon="ℹ️",
        )
        return

    st.dataframe(
        dataframe,
        width="stretch",
        hide_index=False,
        height=min(
            520,
            90 + (len(dataframe) * 36),
        ),
    )


def render_methodology(
    evidence: EvidenceResult,
) -> None:
    """
    Display methodology and analytical warnings.
    """
    st.markdown("#### 🧪 Methodology")

    if evidence.methodology:
        for key, value in evidence.methodology.items():
            readable_key = key.replace("_", " ").title()

            st.markdown(f"**{readable_key}**  \n`{value}`")
    else:
        st.info(
            "No methodology metadata was returned.",
            icon="ℹ️",
        )

    st.markdown("#### ⚠️ Limitations")

    if evidence.warnings:
        for warning in evidence.warnings:
            st.warning(
                warning,
                icon="⚠️",
            )
    else:
        st.success(
            "No analytical warnings were returned.",
            icon="✅",
        )


_INTERNAL_REFERENCE_PATTERN = re.compile(
    r"`*(?:"
    r"【\s*(?:metric|row|warning|method):[^】]+】"
    r"|"
    r"\[\s*(?:metric|row|warning|method):[^\]]+\]"
    r")`*",
    re.IGNORECASE,
)


def prepare_explanation_markdown(
    explanation: str,
) -> str:
    """
    Prepare a grounded explanation for user-facing display.

    Internal evidence references remain available during generation
    and auditing but are removed from the visible narrative.
    """
    formatted = _INTERNAL_REFERENCE_PATTERN.sub(
        "",
        explanation,
    )

    # Clean up spacing left behind after removing references.
    formatted = re.sub(
        r"[ \t]+([,.;:!?])",
        r"\1",
        formatted,
    )
    formatted = re.sub(
        r"[ \t]{2,}",
        " ",
        formatted,
    )
    formatted = re.sub(
        r"\n{3,}",
        "\n\n",
        formatted,
    )

    # Put each answer section heading on its own line.
    section_headings = (
        "Direct answer",
        "Key evidence",
        "Business interpretation",
        "Limitations",
    )

    for heading in section_headings:
        formatted = re.sub(
            (
                rf"(?im)^[ \t]*"
                rf"(?:#{{1,6}}[ \t]*)?"
                rf"(?:\*\*)?"
                rf"{re.escape(heading)}"
                rf"(?:\*\*)?"
                rf"[ \t]*:?[ \t]*"
            ),
            f"**{heading}**\n\n",
            formatted,
        )

    # Remove excessive blank lines created during normalization.
    formatted = re.sub(
        r"\n{3,}",
        "\n\n",
        formatted,
    )

    # Prevent currency values from being interpreted as LaTeX.
    return re.sub(
        r"(?<!\\)\$",
        r"\\$",
        formatted,
    )


def render_answer(
    explanation: str,
    evidence: EvidenceResult,
) -> None:
    """
    Render a grounded analytical answer with deterministic metrics,
    visual evidence, and inspectable methodology.
    """
    badge_class = "supported-badge" if evidence.supported else "unsupported-badge"

    badge_text = (
        "● Evidence-backed analysis" if evidence.supported else "● Unsupported analysis"
    )

    st.markdown(
        f'<div class="{badge_class}">{badge_text}</div>',
        unsafe_allow_html=True,
    )

    if evidence.supported:
        render_metric_cards(evidence)

    with st.container(border=True):
        st.markdown(prepare_explanation_markdown(explanation))

    if evidence.supported:
        st.markdown("### 📊 Visual evidence")
        render_chart(evidence)

    with st.expander(
        "View evidence and methodology",
        expanded=False,
    ):
        st.markdown("#### Evidence summary")
        st.write(evidence.summary)

        st.markdown("#### Summary metrics")

        if evidence.metrics:
            st.json(evidence.metrics)
        else:
            st.info("No summary metrics were returned.")

        st.markdown("#### Supporting evidence")

        if evidence.supporting_rows:
            for row_number, row in enumerate(
                evidence.supporting_rows,
                start=1,
            ):
                st.markdown(f"**Evidence row {row_number}**")
                st.json(row)
        else:
            st.info("No supporting rows were returned.")

        st.markdown("#### Methodology")

        if evidence.methodology:
            st.json(evidence.methodology)
        else:
            st.info("No methodology metadata was returned.")

        st.markdown("#### Limitations")

        if evidence.warnings:
            for warning in evidence.warnings:
                st.warning(warning)
        else:
            st.success("No analytical warnings were returned.")


def render_message(
    message: dict[str, Any],
) -> None:
    """
    Render one stored chat message.
    """
    role = str(message["role"])

    with st.chat_message(role):
        if role == "user":
            st.markdown(message["content"])
            return

        evidence_data = message.get("evidence")

        if evidence_data:
            evidence = EvidenceResult.model_validate(evidence_data)

            interpreted_question = message.get("interpreted_question")

            if interpreted_question:
                st.caption(f"🧭 Interpreted as: *{interpreted_question}*")

            render_answer(
                explanation=str(message["content"]),
                evidence=evidence,
            )
        else:
            st.markdown(message["content"])


def process_question(
    question: str,
) -> None:
    """
    Process, display, and store one user question.

    Contextual follow-ups are resolved deterministically. Standalone
    questions bypass context resolution and use the original pipeline.
    """
    cleaned_question = question.strip()

    if not cleaned_question:
        return

    history = recent_topic_history(limit=2)

    routed_question = resolve_follow_up_question(
        cleaned_question,
        history,
    )
    question_was_rewritten = routed_question != cleaned_question

    user_message = {
        "role": "user",
        "content": cleaned_question,
        "resolved_question": routed_question,
    }

    with st.chat_message("user"):
        st.markdown(cleaned_question)

    with st.chat_message("assistant"):
        try:
            with st.status(
                "Starting analysis...",
                expanded=True,
            ) as status:
                st.write("🔎 Routing the business question...")

                if question_was_rewritten:
                    st.write(f"🧭 Interpreting as: *{routed_question}*")

                evidence = retrieve_evidence(routed_question)

                st.write("📊 Gathering deterministic evidence...")

                if evidence.supported:
                    st.write("🤖 Generating a grounded explanation...")
                else:
                    st.write("🛡️ Preparing a safe unsupported response...")

                explanation = generate_grounded_explanation(evidence)

                status.update(
                    label="Analysis complete",
                    state="complete",
                    expanded=False,
                )

        except FileNotFoundError as error:
            error_message = "The analytical database is unavailable."
            st.error(
                error_message,
                icon="🗄️",
            )
            st.code(str(error))

            st.session_state.messages.extend(
                [
                    user_message,
                    {
                        "role": "assistant",
                        "content": error_message,
                    },
                ]
            )
            return

        except RuntimeError as error:
            error_message = "The copilot could not complete the request."
            st.error(
                error_message,
                icon="⚠️",
            )
            st.code(str(error))

            st.session_state.messages.extend(
                [
                    user_message,
                    {
                        "role": "assistant",
                        "content": error_message,
                    },
                ]
            )
            return

        except Exception as error:
            error_message = "An unexpected error occurred."
            st.error(
                error_message,
                icon="🚨",
            )
            st.code(f"{type(error).__name__}: {error}")

            st.session_state.messages.extend(
                [
                    user_message,
                    {
                        "role": "assistant",
                        "content": error_message,
                    },
                ]
            )
            return

        if question_was_rewritten:
            st.caption(f"🧭 Interpreted as: *{routed_question}*")

        render_answer(
            explanation=explanation,
            evidence=evidence,
        )

    assistant_message = {
        "role": "assistant",
        "content": explanation,
        "evidence": evidence.model_dump(mode="json"),
        "interpreted_question": (routed_question if question_was_rewritten else None),
    }

    st.session_state.messages.extend(
        [
            user_message,
            assistant_message,
        ]
    )


def render_sidebar() -> str | None:
    """
    Render branding, quick questions, and session controls.
    """
    selected_question: str | None = None

    with st.sidebar:
        sidebar_html = (
            '<div class="sidebar-brand">'
            '<p class="sidebar-title">Evidence-First BI</p>'
            '<p class="sidebar-copy">'
            "Deterministic analytics combined with "
            "grounded AI explanations."
            "</p>"
            "</div>"
        )

        st.markdown(
            sidebar_html,
            unsafe_allow_html=True,
        )

        st.markdown("### ⚡ Quick questions")

        for index, question in enumerate(EXAMPLE_QUESTIONS):
            if st.button(
                question,
                key=f"example_question_{index}",
                width="stretch",
            ):
                selected_question = question

        st.divider()

        st.markdown("### 🧱 Architecture")

        st.markdown(
            """
            - ✅ Validated DuckDB warehouse
            - ✅ Semantic metric definitions
            - ✅ Deterministic evidence retrieval
            - ✅ Constrained LLM explanations
            - ✅ Inspectable methodology
            """
        )

        st.divider()

        if st.button(
            "🗑️ Clear conversation",
            width="stretch",
        ):
            st.session_state.messages = []
            st.rerun()

        st.caption(
            "The LLM communicates verified evidence. "
            "It does not calculate the underlying metrics."
        )

    return selected_question


def render_hero() -> None:
    """
    Render the application hero section.

    The HTML is built as one continuous block so Streamlit renders it
    correctly instead of interpreting parts of it as Markdown code.
    """
    hero_html = (
        '<div class="hero-card">'
        '<h1 class="hero-title">'
        'Grounded<span style="color:#c4b5fd;">IQ</span>'
        "</h1>"
        '<h3 style="margin-top:0.75rem; color:#E2E8F0;">'
        "Business intelligence you can verify."
        "</h3>"
        '<p class="hero-subtitle">'
        "Ask business questions in natural language. "
        "GroundedIQ runs deterministic analytics, retrieves validated "
        "evidence, and uses a constrained language model to explain "
        "the results."
        "</p>"
        '<div class="badge-row">'
        '<span class="badge">✓ Deterministic analytics</span>'
        '<span class="badge">✓ Evidence-backed answers</span>'
        '<span class="badge">✓ Explainable methodology</span>'
        '<span class="badge">✓ Safe refusals</span>'
        "</div>"
        "</div>"
    )

    st.markdown(
        hero_html,
        unsafe_allow_html=True,
    )


def render_empty_state() -> None:
    """
    Display the initial empty-state content.
    """
    st.markdown("### Start with a business question")

    first_column, second_column, third_column = st.columns(3)

    with first_column:
        with st.container(border=True):
            st.markdown("#### 📉 Investigate change")
            st.caption(
                "Decompose revenue movements into volume, "
                "order value, category, and geography."
            )

    with second_column:
        with st.container(border=True):
            st.markdown("#### 🚚 Diagnose operations")
            st.caption(
                "Compare delivery performance, delay severity, "
                "and customer review outcomes."
            )

    with third_column:
        with st.container(border=True):
            st.markdown("#### 💰 Explore performance")
            st.caption(
                "Review marketplace KPIs, leading categories, "
                "states, and monthly trends."
            )


def main() -> None:
    """
    Render the complete Streamlit copilot.
    """
    st.set_page_config(
        page_title="GroundedIQ",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    inject_custom_styles()
    initialize_session_state()

    selected_question = render_sidebar()

    render_hero()

    if not st.session_state.messages:
        render_empty_state()

    for message in st.session_state.messages:
        render_message(message)

    typed_question = st.chat_input(
        "Ask a business question about revenue, delivery, or reviews..."
    )

    question_to_process = typed_question if typed_question else selected_question

    if question_to_process:
        process_question(question_to_process)

    st.markdown(
        """
        <p class="footer-note">
            Built with DuckDB, Python, Streamlit, Plotly,
            deterministic evidence retrieval, and a grounded LLM.
        </p>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
