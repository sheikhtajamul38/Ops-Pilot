import streamlit as st
import asyncio
import sys
import os

sys.path.append(os.path.dirname(__file__))
from agent.agent import (
    run_investigation,
    run_multi_service_investigation,
    save_resolution,
    draft_status_update,
)
from db.timeline import get_timeline, get_multi_service_timeline
from db.vector_store import get_pattern_summary

st.set_page_config(page_title="OpsPilot Local", page_icon="🔍", layout="wide")
st.title("OpsPilot Local")
st.caption("AI-powered incident investigation — 100% local, no paid APIs")

with st.sidebar:
    st.header("Services")
    st.markdown("- auth-service\n- payment-service\n- notification-service")
    st.divider()
    st.header("Investigation mode")
    mode = st.radio("Mode", ["Single service", "Multi-service"], label_visibility="collapsed")
    st.divider()
    st.header("Example queries")
    examples = [
        "Why is auth-service failing after the last deployment?",
        "Payment service is timing out, what happened?",
        "Have we seen Redis latency issues before?",
        "Why are both auth and payment services down?",
        "What changed across all services recently?",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state.query = ex
    st.divider()
    if "saved" not in st.session_state:
        st.session_state.saved = []
    st.header(f"Saved resolutions ({len(st.session_state.saved)})")
    for s in st.session_state.saved:
        st.success(s[:40])

if "history" not in st.session_state:
    st.session_state.history = []
if "query" not in st.session_state:
    st.session_state.query = ""
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "last_query" not in st.session_state:
    st.session_state.last_query = ""
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "chat"

tab1, tab2, tab3 = st.tabs(["Chat", "Timeline", "Pattern matching"])

with tab1:
    query = st.chat_input("Ask about an incident...")
    if not query and st.session_state.query:
        query = st.session_state.query
        st.session_state.query = ""

    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if query:
        with st.chat_message("user"):
            st.markdown(query)
        st.session_state.history.append({"role": "user", "content": query})

        with st.chat_message("assistant"):
            status_box = st.empty()
            steps = []

            def update_status(msg):
                steps.append(msg)
                status_box.info("\n\n".join(f"⚙️ {s}" for s in steps))

            with st.spinner("Investigating..."):
                if mode == "Multi-service":
                    result = asyncio.run(
                        run_multi_service_investigation(query, status_callback=update_status)
                    )
                    services_label = ", ".join(f"`{s}`" for s in result["services"])
                    st.markdown(f"**Services:** {services_label}")
                else:
                    result = asyncio.run(run_investigation(query, status_callback=update_status))
                    st.markdown(f"**Service:** `{result['service']}`")

            status_box.empty()
            st.markdown(f"**Tools used:** {', '.join(f'`{t}`' for t in result['tools_used'])}")
            st.divider()
            st.markdown(result["answer"])

            with st.expander("Raw evidence"):
                st.text(result["evidence"])

            st.session_state.last_result = result
            st.session_state.last_query = query

        st.session_state.history.append({"role": "assistant", "content": result["answer"]})

    if st.session_state.last_result:
        result = st.session_state.last_result
        query_saved = st.session_state.last_query
        st.divider()
        st.subheader("Actions")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("💾 Save resolution", use_container_width=True):
                with st.spinner("Saving..."):
                    svc = result.get("service") or result.get("services", ["unknown"])[0]
                    msg = asyncio.run(
                        save_resolution(
                            service=svc,
                            title=f"Investigation: {query_saved[:60]}",
                            symptoms=query_saved,
                            root_cause=result["answer"][:300],
                            resolution=result["answer"][:300],
                            tags=[svc, "auto-saved"],
                        )
                    )
                st.success(f"Saved! {msg}")
                st.session_state.saved.append(query_saved[:50])
                st.rerun()

        with col2:
            if st.button("💬 Draft Slack update", use_container_width=True):
                with st.spinner("Drafting..."):
                    svc = result.get("service") or result.get("services", ["unknown"])[0]
                    slack_msg = draft_status_update(query_saved, result["answer"], svc, "slack")
                st.session_state.history.append(
                    {"role": "assistant", "content": f"**Slack update:**\n\n{slack_msg}"}
                )
                st.rerun()

        with col3:
            if st.button("📧 Draft email update", use_container_width=True):
                with st.spinner("Drafting..."):
                    svc = result.get("service") or result.get("services", ["unknown"])[0]
                    email_msg = draft_status_update(query_saved, result["answer"], svc, "email")
                st.session_state.history.append(
                    {"role": "assistant", "content": f"**Email update:**\n\n{email_msg}"}
                )
                st.rerun()

with tab2:
    st.subheader("Event timeline")
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_services = st.multiselect(
            "Services",
            ["auth-service", "payment-service", "notification-service"],
            default=["auth-service"],
        )
    with col2:
        hours = st.selectbox("Time window", [6, 12, 24, 48, 72], index=2)

    if st.button("Load timeline", use_container_width=True):
        with st.spinner("Loading events..."):
            events = get_multi_service_timeline(selected_services, hours)

        if not events:
            st.info("No events found in this time window.")
        else:
            st.markdown(f"**{len(events)} events** across {len(selected_services)} service(s)")
            level_colors = {
                "ERROR": "🔴",
                "CRITICAL": "🚨",
                "WARN": "🟡",
                "INFO": "🟢",
                "deployment": "🚀",
                "incident": "⚠️",
            }
            for event in reversed(events):
                t = event["time"][:19].replace("T", " ")
                svc = event["service"]
                msg = event["message"]
                etype = event["type"]
                level = event["level"]

                if etype == "deployment":
                    icon = "🚀"
                    st.markdown(f"`{t}` {icon} **[DEPLOY]** `{svc}` — {msg}")
                elif etype == "incident":
                    icon = "⚠️"
                    st.markdown(f"`{t}` {icon} **[INCIDENT]** `{svc}` — {msg}")
                elif level == "ERROR" or level == "CRITICAL":
                    st.markdown(f"`{t}` 🔴 **[{level}]** `{svc}` — {msg}")
                elif level == "WARN":
                    st.markdown(f"`{t}` 🟡 **[WARN]** `{svc}` — {msg}")
                else:
                    st.markdown(f"`{t}` 🟢 **[INFO]** `{svc}` — {msg}")

with tab3:
    st.subheader("Pattern matching")
    st.caption("Find similar past incidents using semantic search")
    pattern_query = st.text_input(
        "Describe the issue", placeholder="e.g. database connection timeout after deployment"
    )

    if st.button("Find similar incidents", use_container_width=True):
        with st.spinner("Searching pattern history..."):
            summary = get_pattern_summary(pattern_query)
        st.markdown(summary)

    st.divider()
    st.caption(
        "How it works: your query is converted to a vector embedding using a local model, then compared against all saved incidents using cosine similarity. No data leaves your machine."
    )
