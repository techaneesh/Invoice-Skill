"""app.py — Streamlit chat UI for Invoice Agent POC."""

import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AI Agent with Invoice Skill",
    page_icon="🧾",
    layout="wide",
)

st.title("🧾 AI Agent with Invoice Skill (POC)")
st.caption("Ask natural-language questions about customers, products, and invoices.")

# Sidebar with demo questions and status
with st.sidebar:
    st.header("⚡ Quick Demo Questions")
    demo_questions = [
        "Show invoice INV-205.",
        "Show the latest invoice for customer CUST-101.",
        "Which customer does invoice INV-205 belong to?",
        "Which products are included in invoice INV-205?",
        "Show each product's quantity and price in invoice INV-205.",
        "Show all unpaid invoices.",
        "Show unpaid invoices above ₹10,000.",
        "Find invoices issued last month.",
        "Calculate the total value of unpaid invoices.",
        "Show all products in the electronics category.",
        "Find customer CUST-101's email.",
        "How many invoices does each customer have?",
    ]

    for q in demo_questions:
        if st.button(q, key=f"btn_{q}"):
            st.session_state["pending_prompt"] = q

    st.markdown("---")
    st.subheader("System Status")
    try:
        health_resp = requests.get(f"{API_URL}/health", timeout=3)
        if health_resp.status_code == 200:
            st.success("Backend: Connected 🟢")
            st.success("Database: Connected 🟢")
        else:
            st.warning("Backend: Connected 🟢 | DB: Unavailable 🟠")
    except Exception:
        st.error("Backend: Offline 🔴")

# Initialize chat message history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("badge"):
            st.caption(f"🏷️ Skill Used: **{msg['badge']}**")
        if msg.get("data"):
            st.dataframe(msg["data"], use_container_width=True)

# Determine user input (from chat_input or demo button click)
user_prompt = st.chat_input("Type your question here...")
if st.session_state.get("pending_prompt"):
    user_prompt = st.session_state.pop("pending_prompt")

if user_prompt:
    # 1. Render user message
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    # 2. Call backend API
    with st.chat_message("assistant"):
        with st.spinner("Analyzing request and executing query..."):
            try:
                resp = requests.post(
                    f"{API_URL}/api/chat",
                    json={"message": user_prompt, "session_id": "streamlit-session"},
                    timeout=30,
                )
                payload = resp.json()
            except Exception as e:
                payload = {
                    "status": "error",
                    "answer": f"Failed to connect to backend API: {e}",
                    "data": None,
                    "capability_used": None,
                }

        status = payload.get("status", "error")
        answer = payload.get("answer", "")
        data = payload.get("data")
        badge = payload.get("capability_used")

        # Render corresponding status view
        if status == "clarification_required":
            st.warning(f"⚠️ {answer}")
        elif status == "not_found":
            st.info(f"ℹ️ {answer}")
        elif status == "error":
            st.error(f"❌ {answer}")
            if payload.get("error"):
                with st.expander("Error details"):
                    st.code(payload["error"])
        else:
            st.markdown(answer)

        if badge:
            st.caption(f"🏷️ Skill Used: **{badge}**")

        if data:
            st.dataframe(data, use_container_width=True)

        # Append to message history
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
                "badge": badge,
                "data": data,
            }
        )
