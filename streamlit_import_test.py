import faulthandler

faulthandler.enable(all_threads=True)

print("1. Starting", flush=True)

import streamlit as st

print("2. Streamlit imported", flush=True)

import pandas as pd

print("3. Pandas imported", flush=True)

import plotly.express as px

print("4. Plotly imported", flush=True)

from app.analytics.metrics import open_analytics_connection

print("5. Analytics imported", flush=True)

from app.evidence.engine import answer_question_with_evidence

print("6. Evidence engine imported", flush=True)

from app.evidence.models import AnalysisType, EvidenceResult

print("7. Evidence models imported", flush=True)

from app.llm.explainer import generate_grounded_explanation

print("8. LLM explainer imported", flush=True)

st.set_page_config(page_title="Import Test")
st.title("All imports passed")
st.write("The application modules loaded successfully.")
