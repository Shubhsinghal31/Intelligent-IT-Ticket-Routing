"""
Helpdesk AI — Streamlit frontend entry point.

This is the home page. It also serves as the login gate:
unauthenticated users see the login form here.
Authenticated users are redirected to the dashboard.
"""

import sys
from pathlib import Path

# Add project root (helpdesk-ai/) to sys.path so that "frontend" is importable
# as a package from any page. Must come before any "from frontend..." imports.
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from frontend.components.auth import get_role, get_user, logout, require_login

# =====================================================
# Page configuration — must be the FIRST Streamlit call
# =====================================================
st.set_page_config(
    page_title="Helpdesk AI",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =====================================================
# Authentication gate
# =====================================================
token = require_login()
user = get_user()
role = get_role()

# =====================================================
# Sidebar — shown on all pages once logged in
# =====================================================
with st.sidebar:
    st.markdown(f"### 👤 {user.get('full_name', 'User')}")
    st.markdown(f"**Role:** {role.title()}")
    st.markdown(f"**Email:** {user.get('email', '')}")
    st.divider()
    if st.button("🚪 Sign Out", use_container_width=True):
        logout()

# =====================================================
# Home page content
# =====================================================
st.title("🎫 Helpdesk AI")
st.markdown(f"Welcome back, **{user.get('full_name')}**! " "Use the sidebar to navigate.")

st.divider()

# ── Quick-navigation cards ────────────────────────────────────────────────────
# Streamlit 1.35 has no st.navigation/st.Page (added in 1.36), so there is no
# built-in way to hide a sidebar page entry per-role — the sidebar always
# lists every file in pages/. The workaround used throughout this app is an
# in-page role guard (see the top of pages/1_Dashboard.py): the link is
# reachable, but renders "Access denied" for the wrong role. These home-page
# cards are real navigation, not just static blurbs, so they use st.button +
# st.switch_page instead of st.info.
nav_cols = st.columns(4 if role == "admin" else 3)
col1, col2, col3 = nav_cols[0], nav_cols[1], nav_cols[2]

with col1:
    st.markdown("📋 **Tickets**")
    st.caption("View and manage support tickets")
    if st.button("Open Tickets", use_container_width=True, key="nav_tickets"):
        st.switch_page("pages/2_Tickets.py")

with col2:
    st.markdown("➕ **Create Ticket**")
    st.caption("Raise a new support request")
    if st.button("New Ticket", use_container_width=True, key="nav_create"):
        st.switch_page("pages/3_Create_Ticket.py")

with col3:
    if role in ("engineer", "admin"):
        st.markdown("📊 **Dashboard**")
        st.caption("View metrics and analytics")
        if st.button("Open Dashboard", use_container_width=True, key="nav_dashboard"):
            st.switch_page("pages/1_Dashboard.py")
    else:
        st.markdown("💬 **Comments**")
        st.caption("Open any ticket to add updates or comments")

if role == "admin":
    with nav_cols[3]:
        st.markdown("👥 **Users**")
        st.caption("Manage accounts and access")
        if st.button("Manage Users", use_container_width=True, key="nav_users"):
            st.switch_page("pages/5_Admin_Users.py")
