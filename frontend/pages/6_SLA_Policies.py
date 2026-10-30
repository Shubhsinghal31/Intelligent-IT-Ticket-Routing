"""
SLA Policies page — view (engineer/admin) and edit (admin only) the
response/resolution hour targets for each priority level.

Editing here only affects tickets created AFTER the change — sla_due_at is
computed once at ticket-creation time (see TicketService.create_ticket) and
is never retroactively recalculated. This page says so explicitly rather
than letting an admin assume a change instantly re-grades existing tickets.
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
st.set_page_config(page_title="SLA Policies | Helpdesk AI", page_icon="⏱", layout="wide")

# ── Auth gate ─────────────────────────────────────────────────────────────────
token = require_login()
user = get_user()
role = get_role()

# ── Role guard: engineers can view, employees cannot ──────────────────────────
if role not in ("engineer", "admin"):
    st.error("⛔ Access denied. This page is for engineers and admins only.")
    st.stop()

is_admin = role == "admin"

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 👤 {user.get('full_name', 'User')}")
    st.markdown(f"**Role:** {role.title()}")
    st.divider()
    if st.button("🚪 Sign Out", use_container_width=True):
        logout()

# ── Page header ───────────────────────────────────────────────────────────────
st.title("⏱ SLA Policies")
st.caption(
    "Response and resolution targets per priority level. "
    + ("Changes apply only to tickets created after saving." if is_admin else "View only.")
)

# ── Fetch policies ─────────────────────────────────────────────────────────────
try:
    policies = api_client.get_sla_policies(token)
except ValueError as e:
    st.error(str(e))
    st.stop()
except Exception:
    st.error("⚠️ Could not load SLA policies. Is the backend running?")
    st.stop()

if not policies:
    st.info("No SLA policies configured.")
    st.stop()

PRIORITY_BADGE = {
    "low": "🟢 Low",
    "medium": "🟡 Medium",
    "high": "🟠 High",
    "critical": "🔴 Critical",
}

st.divider()

# ── One card per policy ────────────────────────────────────────────────────────
# Admins get an editable form per policy; engineers get a read-only view.
# Splitting the render path (rather than disabling inputs) avoids showing
# controls that would just 403 on submit for a non-admin.
for policy in policies:
    label = PRIORITY_BADGE.get(policy["priority"], policy["priority"].title())

    with st.container(border=True):
        st.markdown(f"#### {label}")

        if is_admin:
            with st.form(f"policy_form_{policy['id']}"):
                col1, col2 = st.columns(2)
                with col1:
                    response_hours = st.number_input(
                        "Response time (hours)",
                        min_value=1,
                        max_value=720,
                        value=policy["response_time_hours"],
                        key=f"response_{policy['id']}",
                    )
                with col2:
                    resolution_hours = st.number_input(
                        "Resolution time (hours)",
                        min_value=1,
                        max_value=720,
                        value=policy["resolution_time_hours"],
                        key=f"resolution_{policy['id']}",
                    )
                description = st.text_input(
                    "Description",
                    value=policy.get("description") or "",
                    key=f"description_{policy['id']}",
                )
                saved = st.form_submit_button("Save")

            if saved:
                try:
                    api_client.update_sla_policy(
                        token,
                        policy["id"],
                        {
                            "response_time_hours": int(response_hours),
                            "resolution_time_hours": int(resolution_hours),
                            "description": description,
                        },
                    )
                    st.success(f"{label} policy updated.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        else:
            col1, col2 = st.columns(2)
            col1.metric("Response Time", f"{policy['response_time_hours']} hrs")
            col2.metric("Resolution Time", f"{policy['resolution_time_hours']} hrs")
            if policy.get("description"):
                st.caption(policy["description"])
