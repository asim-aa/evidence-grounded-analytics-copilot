import faulthandler

faulthandler.enable(all_threads=True)

import streamlit as st

from app.analytics.metrics import open_analytics_connection
from app.evidence.engine import answer_question_with_evidence
from app.llm.explainer import generate_grounded_explanation


QUESTION = "Why did revenue decline in June 2018?"


st.set_page_config(
    page_title="Question Pipeline Test",
)

st.title("Question Pipeline Test")
st.write("This tests each stage without charts, tabs, or conversation history.")

if st.button("Run test question"):
    print("Q1. Button clicked", flush=True)

    connection = open_analytics_connection()

    try:
        evidence = answer_question_with_evidence(
            QUESTION,
            connection,
        )
    finally:
        connection.close()

    print("Q2. Evidence retrieved", flush=True)

    st.success("Evidence retrieved successfully.")
    st.write(evidence.summary)

    print("Q3. Evidence rendered", flush=True)

    explanation = generate_grounded_explanation(
        evidence
    )

    print("Q4. Explanation generated", flush=True)

    st.markdown(explanation)

    print("Q5. Explanation rendered", flush=True)

    st.success("Complete pipeline passed.")
