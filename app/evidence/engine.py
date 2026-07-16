from __future__ import annotations

import argparse
import json

import duckdb

from app.analytics.metrics import open_analytics_connection
from app.evidence.models import EvidenceResult
from app.evidence.registry import HANDLER_REGISTRY
from app.evidence.router import route_question


def answer_question_with_evidence(
    question: str,
    connection: duckdb.DuckDBPyConnection,
) -> EvidenceResult:
    """
    Route a business question and return deterministic evidence.
    """
    route = route_question(question)

    handler = HANDLER_REGISTRY[route.analysis_type]

    evidence = handler(
        question,
        connection,
    )

    evidence.methodology.setdefault(
        "router_rule",
        route.matched_rule,
    )

    return evidence


def main() -> None:
    """
    Run the evidence engine from the command line.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Ask a supported business question and receive deterministic evidence."
        )
    )

    parser.add_argument(
        "question",
        type=str,
        help="Natural-language business question.",
    )

    arguments = parser.parse_args()

    connection = open_analytics_connection()

    try:
        evidence = answer_question_with_evidence(
            arguments.question,
            connection,
        )

        print(
            json.dumps(
                evidence.model_dump(mode="json"),
                indent=2,
            )
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
