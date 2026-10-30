"""
Reports page — export tickets as CSV, Excel, or PDF.

Engineer/admin only, matching the backend (a report is an org-wide view
across all tickets, unlike GET /tickets which restricts employees to
their own). No department filter here — same reasoning as the Create
Ticket page: there is no GET /departments endpoint yet, so hardcoding
department IDs into a picker would be fragile. Status/priority/date-range
cover the common report use cases without it.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from frontend import api_client
from frontend.components.auth import get_role, get_user, logout, require_login

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Reports | Helpdesk AI", page_icon="🗂", layout="wide")

# ── Auth gate ─────────────────────────────────────────────────────────────────
token = require_login()
user = get_user()
role = get_role()

# ── Role guard: engineers/admins only ─────────────────────────────────────────
if role not in ("engineer", "admin"):
    st.error("⛔ Access denied. This page is for engineers and admins only.")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 👤 {user.get('full_name', 'User')}")
    st.markdown(f"**Role:** {role.title()}")
    st.divider()
    if st.button("🚪 Sign Out", use_container_width=True):
        logout()

# ── Page header ───────────────────────────────────────────────────────────────
st.title("🗂 Reports")
st.caption("Export a snapshot of tickets as CSV, Excel, or PDF.")

# ── Filters ───────────────────────────────────────────────────────────────────
col_status, col_priority = st.columns(2)

with col_status:
    status_options = ["All", "open", "in_progress", "resolved", "closed", "reopened"]
    selected_status = st.selectbox("Status", status_options)

with col_priority:
    priority_options = ["All", "low", "medium", "high", "critical"]
    selected_priority = st.selectbox("Priority", priority_options)

# Date range is opt-in — most reports are "everything", not a narrow window.
# Showing two live date_input widgets by default would silently scope every
# report unless the user thought to widen them.
use_date_range = st.checkbox("Filter by date range")
date_from = date_to = None
if use_date_range:
    col_from, col_to = st.columns(2)
    with col_from:
        date_from = st.date_input("From", value=date.today() - timedelta(days=30))
    with col_to:
        date_to = st.date_input("To", value=date.today())

status_filter = None if selected_status == "All" else selected_status
priority_filter = None if selected_priority == "All" else selected_priority

st.divider()

# ── Generate ──────────────────────────────────────────────────────────────────
# st.download_button needs its bytes ready at render time — it can't call an
# API on click the way st.button can. So "Generate" fetches all three formats
# up front and stashes them in session_state; the download buttons below just
# hand back bytes that are already in memory.
if st.button("📊 Generate Report", use_container_width=True):
    with st.spinner("Generating report..."):
        try:
            common_kwargs = {
                "status": status_filter,
                "priority": priority_filter,
                "date_from": str(date_from) if date_from else None,
                "date_to": str(date_to) if date_to else None,
            }
            st.session_state["report_files"] = {
                "csv": api_client.export_tickets_report(token, "csv", **common_kwargs),
                "excel": api_client.export_tickets_report(token, "excel", **common_kwargs),
                "pdf": api_client.export_tickets_report(token, "pdf", **common_kwargs),
            }
            st.success("Report generated. Choose a format below to download.")
        except ValueError as e:
            st.error(str(e))
            st.session_state.pop("report_files", None)
        except Exception:
            st.error("⚠️ Could not reach the backend. Is the FastAPI server running?")
            st.session_state.pop("report_files", None)

# ── Download buttons ────────────────────────────────────────────────────────────
if "report_files" in st.session_state:
    files = st.session_state["report_files"]
    st.divider()
    col_csv, col_excel, col_pdf = st.columns(3)

    with col_csv:
        st.download_button(
            "⬇ Download CSV",
            data=files["csv"],
            file_name="tickets_report.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_excel:
        st.download_button(
            "⬇ Download Excel",
            data=files["excel"],
            file_name="tickets_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with col_pdf:
        st.download_button(
            "⬇ Download PDF",
            data=files["pdf"],
            file_name="tickets_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
