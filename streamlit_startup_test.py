import faulthandler

faulthandler.enable(all_threads=True)

import streamlit as st

import app.streamlit_app as ui


print("A. Module imported", flush=True)

st.set_page_config(
    page_title="Startup Test",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

print("B. Page config rendered", flush=True)

ui.inject_custom_styles()

print("C. Custom styles rendered", flush=True)

ui.initialize_session_state()

print("D. Session state initialized", flush=True)

selected_question = ui.render_sidebar()

print(
    f"E. Sidebar rendered: {selected_question!r}",
    flush=True,
)

ui.render_hero()

print("F. Hero rendered", flush=True)

if not st.session_state.messages:
    ui.render_empty_state()

print("G. Empty state rendered", flush=True)

for message in st.session_state.messages:
    ui.render_message(message)

print("H. Stored messages rendered", flush=True)

typed_question = st.chat_input(
    "Ask a business question..."
)

print(
    f"I. Chat input rendered: {typed_question!r}",
    flush=True,
)

st.write("Startup test reached the end successfully.")

print("J. Script completed", flush=True)
