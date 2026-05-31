"""
Performance Commentary Assistant -- web interface
=================================================

A small Streamlit front end for commentary_assistant.py. It reuses the exact
same engine (prompt + logic), so there is one source of truth: this file only
handles the screen.

Run it (NOT with `python` -- Streamlit apps launch with their own command):

    pip install streamlit anthropic
    streamlit run app.py

A browser tab opens automatically at http://localhost:8501
"""

import os
import streamlit as st

import commentary_assistant as ca

st.set_page_config(page_title="Performance Commentary Assistant", page_icon="📊")

st.title("Performance Commentary Assistant")
st.caption(
    "Drafts client-report performance commentary from attribution data. Every "
    "claim is tagged for how well the data supports it, and figures are never "
    "invented."
)

# --- Sidebar: report details, model, and API key ---------------------------
with st.sidebar:
    st.header("Report details")
    fund = st.text_input("Fund name", ca.FUND_NAME)
    benchmark = st.text_input("Benchmark", ca.BENCHMARK_NAME)
    period = st.text_input("Reporting period", ca.REPORTING_PERIOD)
    currency = st.text_input("Base currency", ca.BASE_CURRENCY)

    model = st.selectbox(
        "Model",
        ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5-20251001"],
        index=0,
    )

    st.divider()
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key:
        st.success("API key found in your environment.")
        api_key = None  # the engine will read it from the environment
    else:
        api_key = st.text_input(
            "Anthropic API key",
            type="password",
            help="Held in memory for this session only. Setting the "
            "ANTHROPIC_API_KEY environment variable is the safer option.",
        ) or None

# --- Data source ------------------------------------------------------------
use_sample = st.toggle("Use the built-in sample data", value=True)

uploaded = None
if not use_sample:
    uploaded = st.file_uploader("Upload an attribution CSV", type=["csv"])

# --- Macro layer ------------------------------------------------------------
use_macro = st.checkbox(
    "Add sourced market context (live web search)",
    value=False,
    help="Searches the web for market events in the reporting period and cites "
    "them. Costs a little more per run.",
)
if use_macro:
    st.info(
        "Market context is drawn from a live web search and cited. The fund's "
        "own figures stay data-only, and the tool won't claim a market event "
        "*caused* a result."
    )

# --- Generate ---------------------------------------------------------------
if st.button("Generate commentary", type="primary"):
    # 1. Resolve the data into a markdown table.
    try:
        if use_sample:
            data_table = ca.load_attribution(ca.DEFAULT_DATA)
        elif uploaded is None:
            st.error("Please upload a CSV, or switch the sample data back on.")
            st.stop()
        else:
            data_table = ca.load_attribution_from_text(
                uploaded.getvalue().decode("utf-8")
            )
    except Exception as e:
        st.error(f"Could not read the data: {e}")
        st.stop()

    # 2. Build the prompt with the chosen report context.
    system_prompt = ca.build_system_prompt(use_macro)
    user_message = ca.build_user_message(
        data_table, use_macro,
        fund=fund, benchmark=benchmark, period=period, currency=currency,
    )

    # 3. Call the engine.
    spinner_text = "Drafting commentary"
    spinner_text += " and searching for market context…" if use_macro else "…"
    with st.spinner(spinner_text):
        try:
            commentary, sources = ca.generate_commentary(
                system_prompt, user_message, model, use_macro, api_key=api_key
            )
        except RuntimeError as e:
            st.error(str(e))
            st.stop()

    # 4. Show the result.
    st.subheader("Draft commentary")
    st.markdown(commentary)

    if sources:
        st.subheader("Sources (from live web search)")
        for title, url in sources:
            st.markdown(f"- [{title or url}]({url})")

    st.download_button(
        "Download as Markdown", data=commentary, file_name="commentary.md"
    )

# --- Always-available preview of the data being used ------------------------
if use_sample:
    with st.expander("Show the sample attribution data"):
        try:
            st.markdown(ca.load_attribution(ca.DEFAULT_DATA))
        except Exception:
            st.write("Sample data not found next to the app.")
