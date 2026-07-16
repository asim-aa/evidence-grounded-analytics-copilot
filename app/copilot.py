from __future__ import annotations

import argparse

from app.analytics.metrics import (
    open_analytics_connection,
)
from app.evidence.engine import (
    answer_question_with_evidence,
)
from app.llm.explainer import (
    generate_grounded_explanation,
)


def main() -> None:
    """
    Run the full evidence-grounded copilot from the command line.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Ask a business question and receive an evidence-grounded explanation."
        )
    )

    parser.add_argument(
        "question",
        type=str,
        help="Natural-language business question.",
    )

    parser.add_argument(
        "--show-evidence",
        action="store_true",
        help=("Print the structured evidence object after the explanation."),
    )

    arguments = parser.parse_args()

    connection = open_analytics_connection()

    try:
        evidence = answer_question_with_evidence(
            arguments.question,
            connection,
        )

        explanation = generate_grounded_explanation(evidence)

        print(explanation)

        if arguments.show_evidence:
            print("\n--- Structured evidence ---\n")
            print(
                evidence.model_dump_json(
                    indent=2,
                )
            )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
