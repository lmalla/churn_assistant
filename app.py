import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agent import run_agent

st.set_page_config(
    page_title="Churn Analytics Assistant",
    page_icon="📉",
    layout="wide",
)

st.title("📉 AI Churn Analytics Assistant")
st.caption("Powered by Claude + DuckDB + Chroma · Ask anything about user churn")

EXAMPLES = [
    "What are the top churn reasons by plan type?",
    "Which users are most likely to churn?",
    "Summarize churn patterns for high-spend users.",
    "Which features are associated with retention?",
    "Give me SQL-backed evidence for churn drivers.",
    "Find users with low feature usage who haven't churned yet — retention risk?",
    "Compare login frequency between churned and retained users by plan.",
]

with st.sidebar:
    st.subheader("Example Questions")
    for q in EXAMPLES:
        if st.button(q, use_container_width=True):
            st.session_state["question"] = q

    st.divider()
    st.markdown("**Stack**")
    st.markdown("- LLM: Claude Haiku\n- DB: DuckDB\n- Vectors: Chroma\n- Embeddings: all-MiniLM-L6-v2")

if "history" not in st.session_state:
    st.session_state["history"] = []

question = st.text_input(
    "Ask a churn question:",
    value=st.session_state.get("question", ""),
    placeholder="e.g. What plan has the highest churn rate?",
    key="input",
)

col1, col2 = st.columns([1, 8])
with col1:
    ask = st.button("Ask", type="primary")
with col2:
    if st.button("Clear history"):
        st.session_state["history"] = []
        st.rerun()

if ask and question.strip():
    with st.spinner("Thinking..."):
        answer = run_agent(question.strip())
    st.session_state["history"].append((question.strip(), answer))
    if "question" in st.session_state:
        del st.session_state["question"]

for q, a in reversed(st.session_state["history"]):
    with st.expander(f"Q: {q}", expanded=True):
        st.markdown(a)
