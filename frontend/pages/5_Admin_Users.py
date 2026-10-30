"""
Admin Users page — view the full user roster and activate/deactivate accounts.

Admin-only. Engineers can call GET /users too (they need it for the ticket
assignee picker — see pages/4_Ticket_Detail.py), but account management
(deactivate/activate) is restricted to admins at the API layer, so this
page is gated the same way here rather than showing controls that would
just 403 for an engineer.
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
st.set_page_config(page_title="Users | Helpdesk AI", page_icon="👥", layout="wide")

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

# ── Role guard: admin only ────────────────────────────────────────────────────
if role != "admin":
    st.error("⛔ Access denied. This page is for admins only.")
    st.stop()

# ── Page header ───────────────────────────────────────────────────────────────
st.title("👥 User Management")
st.caption("View the roster and manage account access.")

# ── Add User ──────────────────────────────────────────────────────────────────
# The only way to create an engineer or admin account — self-registration
# (the "Register" expander on the login page) always creates 'employee'
# accounts. See backend/services/user_service.py's create_user() docstring
# for why these are two separate code paths rather than one.
with st.expander("➕ Add User"):
    try:
        departments = api_client.list_departments(token)
    except ValueError as e:
        departments = []
        st.error(f"Could not load departments: {e}")

    dept_options = [None] + [d["id"] for d in departments]
    dept_labels = {None: "— None —"} | {d["id"]: d["name"] for d in departments}

    with st.form("add_user_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            new_full_name = st.text_input("Full name", key="new_user_full_name")
            new_email = st.text_input("Email", placeholder="you@company.com", key="new_user_email")
            new_username = st.text_input(
                "Username",
                placeholder="lowercase letters, numbers, underscores",
                key="new_user_username",
            )
        with col_b:
            new_password = st.text_input(
                "Password",
                type="password",
                key="new_user_password",
                help="At least 8 characters.",
            )
            new_role = st.selectbox("Role", ["employee", "engineer", "admin"], key="new_user_role")
            new_department_id = st.selectbox(
                "Department",
                options=dept_options,
                format_func=lambda did: dept_labels[did],
                key="new_user_department",
            )
        add_submitted = st.form_submit_button("Create account", use_container_width=True)

    if add_submitted:
        if not all([new_full_name, new_email, new_username, new_password]):
            st.error("Please fill in every field.")
        else:
            try:
                api_client.create_user(
                    token,
                    full_name=new_full_name,
                    email=new_email,
                    username=new_username,
                    password=new_password,
                    role=new_role,
                    department_id=new_department_id,
                )
                st.success(f"Account created for {new_full_name}.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception:
                st.error("⚠️ Could not reach the backend.")

st.divider()

# ── Filters row ───────────────────────────────────────────────────────────────
col_role, col_status, col_page = st.columns([2, 2, 1])

with col_role:
    role_options = ["All", "employee", "engineer", "admin"]
    selected_role = st.selectbox("Role", role_options)

with col_status:
    status_options = ["All", "Active", "Inactive"]
    selected_status = st.selectbox("Status", status_options)

with col_page:
    page = st.number_input("Page", min_value=1, value=1, step=1)

role_filter = None if selected_role == "All" else selected_role
is_active_filter = {"All": None, "Active": True, "Inactive": False}[selected_status]

# ── Fetch users ────────────────────────────────────────────────────────────────
try:
    result = api_client.list_users(
        token,
        page=page,
        page_size=20,
        role=role_filter,
        is_active=is_active_filter,
    )
    users = result.get("items", [])
    total = result.get("total", 0)
except ValueError as e:
    st.error(str(e))
    st.stop()
except Exception:
    st.error("⚠️ Could not load users. Is the backend running?")
    st.stop()

st.caption(f"Showing {len(users)} of {total} user(s)  |  Page {page}")

if not users:
    st.info("No users match the selected filters.")
    st.stop()

st.divider()

# ── Roster table ───────────────────────────────────────────────────────────────
# One row per user: identity, role/department, status, and a toggle action.
# The toggle button always shows the action available given the CURRENT
# status (Deactivate for active users, Activate for inactive ones) rather
# than a static label, so there is only ever one valid next action visible.
header_cols = st.columns([3, 2, 2, 2, 2])
for col, label in zip(
    header_cols, ["Name", "Role", "Department", "Status", "Action"], strict=False
):
    col.markdown(f"**{label}**")

for u in users:
    row = st.columns([3, 2, 2, 2, 2])
    row[0].write(f"{u['full_name']}  \n:gray[{u['email']}]")
    row[1].write(u["role"].title())
    row[2].write(u.get("department") or "—")
    row[3].write("🟢 Active" if u["is_active"] else "⚫ Inactive")

    is_self = u["id"] == user.get("id")
    with row[4]:
        if is_self:
            st.caption("This is you")
        elif u["is_active"]:
            if st.button("Deactivate", key=f"deactivate_{u['id']}", use_container_width=True):
                try:
                    api_client.deactivate_user(token, u["id"])
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        else:
            if st.button("Activate", key=f"activate_{u['id']}", use_container_width=True):
                try:
                    api_client.activate_user(token, u["id"])
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

st.divider()

if total > page * 20:
    st.info("There are more users. Increase the page number above to see them.")
