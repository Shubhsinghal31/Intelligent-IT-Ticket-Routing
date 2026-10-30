"""
Create Ticket page — lets any authenticated user raise a new support ticket.

Priority is chosen by the reporter (defaults to Medium). Department is
intentionally NOT a form field: the backend's ML service predicts it from
the title/description text (see ml/service.py + TicketService.create_ticket).
Asking the reporter to guess a department defeats the purpose of the
"Department Prediction" module and risks a wrong manual choice overriding
a better ML one.
"""

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from frontend import api_client
from frontend.components.auth import get_role, get_user, logout, require_login

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Create Ticket | Helpdesk AI", page_icon="➕", layout="wide")

# ── Auth gate ─────────────────────────────────────────────────────────────────
token = require_login()
user = get_user()
role = get_role()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 👤 {user.get('full_name', 'User')}")
    st.markdown(f"**Role:** {role.title()}")
    st.divider()
    if st.button("🚪 Sign Out", use_container_width=True):
        logout()

# ── Page header ───────────────────────────────────────────────────────────────
st.title("➕ Create Ticket")
st.caption("Describe the issue — our AI will route it to the right team and flag its priority.")

# ── Success state ─────────────────────────────────────────────────────────────
# After a successful submit we store the created ticket in session_state and
# render a confirmation panel instead of the form. This survives the rerun
# that st.form triggers on submit, and lets the user choose their next action
# (view the ticket or create another) without losing the result.
if "last_created_ticket" in st.session_state:
    ticket = st.session_state["last_created_ticket"]

    st.success(f"✅ Ticket **{ticket['ticket_number']}** created successfully!")

    col1, col2, col3 = st.columns(3)
    col1.metric("Priority", ticket["priority"].title())

    dept = ticket.get("department")
    col2.metric("Department", dept["name"] if dept else "Pending")

    sla_prob = ticket.get("predicted_sla_breach_prob")
    col3.metric(
        "Predicted SLA Breach Risk",
        f"{float(sla_prob) * 100:.0f}%" if sla_prob is not None else "—",
    )

    res_hours = ticket.get("predicted_resolution_hours")
    if res_hours is not None:
        st.info(f"⏱ Estimated resolution time: **{float(res_hours):.1f} hours**")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📋 View in Tickets", use_container_width=True):
            del st.session_state["last_created_ticket"]
            st.switch_page("pages/2_Tickets.py")
    with col_b:
        if st.button("➕ Create Another", use_container_width=True):
            del st.session_state["last_created_ticket"]
            st.rerun()

    st.stop()

# ── Ticket form ───────────────────────────────────────────────────────────────
# st.form batches all inputs and only reruns the script once, on submit —
# without it, every keystroke in the text_area would trigger a full rerun.
with st.form("create_ticket_form", clear_on_submit=False):
    title = st.text_input(
        "Title",
        placeholder="e.g. VPN disconnects every 10 minutes",
        max_chars=255,
        help="A short summary (min. 5 characters).",
    )

    description = st.text_area(
        "Description",
        placeholder="Include what you were doing, what happened, and any error messages.",
        height=180,
        help="Detailed explanation (min. 20 characters). The more detail, the better the AI routing.",
    )

    priority = st.selectbox(
        "Priority",
        options=["low", "medium", "high", "critical"],
        index=1,  # default: medium
        format_func=lambda p: p.title(),
        help="How urgent is this issue? The AI separately estimates SLA risk regardless of what you pick.",
    )

    submitted = st.form_submit_button("🚀 Submit Ticket", use_container_width=True)

# ── Client-side validation + submit ───────────────────────────────────────────
# These checks mirror backend/schemas/ticket.py::TicketCreate (min_length=5 / 20).
# They exist purely for fast feedback — the backend re-validates regardless,
# so there is no security reliance on this client-side check.
if submitted:
    errors = []
    if len(title.strip()) < 5:
        errors.append("Title must be at least 5 characters.")
    if len(description.strip()) < 20:
        errors.append("Description must be at least 20 characters.")

    if errors:
        for err in errors:
            st.error(err)
    else:
        payload = {
            "title": title.strip(),
            "description": description.strip(),
            "priority": priority,
        }
        with st.spinner("Submitting ticket and running AI predictions..."):
            try:
                created = api_client.create_ticket(token, payload)
                st.session_state["last_created_ticket"] = created
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception:
                st.error("⚠️ Could not reach the backend. Is the FastAPI server running?")
