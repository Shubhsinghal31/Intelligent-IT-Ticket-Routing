# Milestone 7–8 — Interview Preparation: Streamlit Frontend & Admin Dashboard

> **Project:** Helpdesk-AI Enterprise ITSM
> **Milestones:** 7 (user frontend) and 8 (admin dashboard, user management, SLA policies, heatmap)
> **Audience:** Technical interviews touching full-stack/frontend architecture

---

## Topics Covered

- Streamlit's rerun execution model and its implications
- Client/API separation (`api_client.py`)
- Session-state-based auth on a stateless-rerun framework
- Mirroring backend RBAC in UI without duplicating trust
- Data visualization choices (Plotly heatmap)

---

### Q1. Why Streamlit instead of React/Next.js for this project?

**Answer:** Streamlit lets a backend-focused build produce a working, presentable UI without a separate frontend build pipeline (webpack/vite, npm dependency tree, a separate deployment target) — every page is plain Python that re-runs top-to-bottom on each interaction. For a portfolio ITSM tool where the backend (auth, RBAC, ML, SLA engine) is the point being demonstrated, that trade is worth it.

**Tradeoff, stated plainly:** Streamlit reruns the *entire script* on every widget interaction (a button click, a text input change) — there's no fine-grained reactivity like React's virtual DOM diffing. This is fine for admin/internal tools with moderate traffic; it would not be the right choice for a consumer-facing, high-interaction product.

**Follow-up:** What would push you toward React here? → If the app needed complex client-side state (e.g. a drag-and-drop ticket board), real-time updates via websockets, or had to support many concurrent users per session with heavy interactivity — Streamlit's rerun model doesn't scale well to that shape of UI.

---

### Q2. How is login/auth state preserved across Streamlit's rerun-on-every-interaction model?

**Answer:** `st.session_state` — a dict that persists across reruns *within the same browser session* (backed by Streamlit's server-side session tracking). The JWT access/refresh tokens returned by `POST /auth/login` are stored there once, then read on every subsequent page render via `require_login()` (`frontend/components/auth.py`).

**Follow-up:** Where does that break down? → `session_state` doesn't survive a full page reload from a fresh browser tab/session — that's why `require_login()` also checks `st.query_params` for the password-reset deep link, since that flow explicitly *starts* from a fresh, unauthenticated page load.

---

### Q3. Why does every Streamlit page go through `api_client.py` instead of calling `requests` directly?

**Answer:** Single point of change for the API base URL, headers, and error handling. Every function in `api_client.py` builds the same `Authorization: Bearer <token>` header and funnels non-2xx responses through the same `_handle()`/`_handle_binary()`/`_handle_no_content()` helpers into a consistent `ValueError` the page layer catches. Without this, 15+ page files would each reimplement error parsing slightly differently, and changing the base URL for a new environment would mean a project-wide find/replace.

**Follow-up:** Why is this also a testability decision? → Because `api_client.py` is the only module that imports `requests`, it's the only seam that needs mocking to unit-test a page's *rendering logic* independent of a live backend — though this project's test suite focuses on the backend, this is the boundary that would make that mocking possible.

---

### Q4. How does the UI decide which buttons/actions to show without becoming a second source of truth for RBAC?

**Answer:** The frontend mirrors the backend's RBAC rules for *visibility only* — e.g. `4_Ticket_Detail.py` computes `can_resolve = is_staff and status in ("in_progress", "reopened")` to decide whether to render the "Mark Resolved" button. But the actual authorization decision is re-checked, independently, by `TicketService.resolve_ticket()` on the server. If the UI's mirrored logic ever drifted out of sync with the backend, the worst case is a button that's shown-but-rejected (annoying) or hidden-but-would-have-worked (also annoying) — never an unauthorized action actually succeeding, because the server never trusts the client's judgment.

**Follow-up:** Is duplicating this logic risky? → Yes — it's exactly the kind of duplication that drifts over time. The mitigation here is that the comment in `4_Ticket_Detail.py`'s module docstring explicitly says "mirrors backend RBAC exactly" as a flag for future maintainers to update both sides together.

---

### Q5. How does the SLA heatmap work, and why a heatmap for this data?

**Answer:** `GET /dashboard/heatmap` aggregates ticket counts by day-of-week × hour-of-day (via SQL `extract()` on `created_at`), and the frontend renders it as a Plotly heatmap. A heatmap is the right chart here because the question being answered is "when do we get slammed" — a 2D categorical grid (day × hour) with intensity as color communicates a *pattern across two dimensions simultaneously* far better than a bar chart, which can only show one dimension well.

**Follow-up:** What decision does this chart actually support? → Staffing — if Tuesdays 9–11am consistently light up, that's a signal to schedule more engineers during that window, which a raw ticket-count table wouldn't surface as clearly.
