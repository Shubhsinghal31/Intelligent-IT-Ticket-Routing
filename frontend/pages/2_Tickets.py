"""
Tickets list page — filterable, paginated table of all tickets.
All roles can access this page; employees see only their own tickets
(enforced by the backend).
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
st.set_page_config(page_title="Tickets | Helpdesk AI", page_icon="📋", layout="wide")

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
st.title("📋 Tickets")

# ── Filters row ───────────────────────────────────────────────────────────────
# Status and priority dropdowns let the user narrow results.
# "All" sends no filter to the API.
col_status, col_priority, col_page = st.columns([2, 2, 1])

with col_status:
    status_options = ["All", "open", "in_progress", "resolved", "closed", "reopened"]
    selected_status = st.selectbox("Status", status_options)

with col_priority:
    priority_options = ["All", "low", "medium", "high", "critical"]
    selected_priority = st.selectbox("Priority", priority_options)

with col_page:
    page = st.number_input("Page", min_value=1, value=1, step=1)

# Convert "All" → None (API ignores None filters)
status_filter = None if selected_status == "All" else selected_status
priority_filter = None if selected_priority == "All" else selected_priority

# ── Fetch tickets ─────────────────────────────────────────────────────────────
try:
    result = api_client.list_tickets(
        token,
        page=page,
        page_size=20,
        status=status_filter,
        priority=priority_filter,
    )
    tickets = result.get("items", [])
    total = result.get("total", 0)
except ValueError as e:
    st.error(str(e))
    st.stop()
except Exception:
    st.error("⚠️ Could not load tickets. Is the backend running?")
    st.stop()

# ── Summary line ──────────────────────────────────────────────────────────────
st.caption(f"Showing {len(tickets)} of {total} ticket(s)  |  Page {page}")

if not tickets:
    st.info("No tickets match the selected filters.")
    st.stop()

# ── Priority badge helper ─────────────────────────────────────────────────────
PRIORITY_BADGE = {
    "low": "🟢 Low",
    "medium": "🟡 Medium",
    "high": "🟠 High",
    "critical": "🔴 Critical",
}

STATUS_BADGE = {
    "open": "🟡 Open",
    "in_progress": "🔵 In Progress",
    "resolved": "🟢 Resolved",
    "closed": "⚫ Closed",
    "reopened": "🔁 Reopened",
}

# ── Ticket cards ──────────────────────────────────────────────────────────────
# Each ticket is rendered as an expander so the user can preview without
# leaving the page. Clicking "View Detail" navigates to the detail page.
for ticket in tickets:
    priority_label = PRIORITY_BADGE.get(ticket.get("priority", ""), ticket.get("priority", ""))
    status_label = STATUS_BADGE.get(ticket.get("status", ""), ticket.get("status", ""))

    header = f"#{ticket['id']}  {ticket['title']}  |  {priority_label}  |  {status_label}"

    with st.expander(header):
        col_left, col_right = st.columns([3, 1])

        with col_left:
            st.markdown(f"**Description:** {ticket.get('description', '—')[:300]}")
            dept = ticket.get("department") or "Unassigned"
            assignee = ticket.get("assignee") or "Unassigned"
            st.markdown(f"**Department:** {dept}  |  **Assignee:** {assignee}")
            created = ticket.get("created_at", "")[:10]  # YYYY-MM-DD
            st.markdown(f"**Created:** {created}")

        with col_right:
            # Store selected ticket ID in session state so the detail page can read it.
            if st.button("🔍 View Detail", key=f"view_{ticket['id']}"):
                st.session_state["selected_ticket_id"] = ticket["id"]
                st.switch_page("pages/4_Ticket_Detail.py")

st.divider()

# ── Pagination hint ───────────────────────────────────────────────────────────
if total > page * 20:
    st.info("There are more tickets. Increase the page number above to see them.")
