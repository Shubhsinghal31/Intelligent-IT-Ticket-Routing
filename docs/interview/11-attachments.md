# Gap Fill — Interview Preparation: Ticket Attachments

> **Project:** Helpdesk-AI Enterprise ITSM
> **Feature:** File upload/list/download on tickets, local disk storage
> **Audience:** Technical interviews touching file-upload security

---

## Topics Covered

- Path traversal prevention via generated filenames
- Storage-backend portability (relative paths)
- Authenticated streaming vs. static file mounts
- Allowlist vs. denylist for MIME types
- Ephemeral storage as a documented, deliberate limitation

---

### Q1. Why is the on-disk filename a fresh UUID instead of the client's uploaded filename?

**Answer:** Two independent problems, one fix. **Path traversal:** a filename like `../../etc/passwd` or `..\..\Windows\System32\config` must never reach the filesystem layer as-is — generating the on-disk name entirely server-side (never derived from client input) sidesteps the whole class of attack rather than trying to sanitize every possible malicious string (a losing game — sanitization allowlists are easy to get subtly wrong). **Collisions:** two users uploading `screenshot.png` to the same ticket would otherwise silently overwrite each other on disk. `uuid.uuid4().hex` solves both. The client's original filename is preserved separately in `Attachment.file_name`, purely for display/download purposes — it never touches path resolution.

**Follow-up:** Is sanitizing the original filename ever necessary then? → Not for path safety (since it's never used as a path), but it's still returned to the client in `Content-Disposition: attachment; filename="..."` on download — a filename containing certain characters could theoretically cause issues in some browsers/HTTP clients. A hardened version might strip control characters from the *displayed* filename even though it's already safe path-wise.

---

### Q2. Why is `Attachment.file_path` stored relative to a configurable root, rather than an absolute path?

**Answer:** Portability of the storage backend. `file_path` values look like `42/3f9a...e2.png` — no dependency on where `uploads/attachments/` actually lives on disk. This is deliberately what makes migrating to S3-compatible object storage later a *one-file change* (`AttachmentService`): the relative path doubles as an S3 key unchanged, since S3 keys are also just relative strings. If paths were absolute, every stored row would need a data migration to strip the old filesystem prefix before the storage backend could change.

**Follow-up:** What has to change in `AttachmentService` specifically to move to S3? → `full_path.write_bytes(content)` becomes an S3 `put_object` call, `full_path.read_bytes()` becomes a `get_object`, and `settings.attachments_storage_full_path` becomes an S3 client + bucket name — but `Attachment.file_path`'s *value* for every existing row stays valid.

---

### Q3. Why does attachment download go through an authenticated FastAPI endpoint instead of a `StaticFiles` mount?

**Answer:** A static mount serves whatever's on disk to whoever has the URL — no awareness of RBAC. Anyone who guessed or leaked an attachment's URL could download another user's ticket attachment, bypassing the entire "employees only see their own tickets" rule the rest of the API enforces. `GET /tickets/{id}/attachments/{attachment_id}/download` re-runs the exact same view-permission check (`_assert_can_view`) as every other ticket-scoped endpoint before streaming the file back — access to the file is exactly as protected as access to the ticket it belongs to.

**Follow-up:** Isn't a static mount simpler/faster? → Slightly, for the "faster" claim (a reverse proxy serving static files can be more efficient than a Python process streaming bytes), but that's the wrong axis to optimize on when the actual requirement is "don't leak other users' files." `backend/main.py` deliberately has no `StaticFiles` mount at all — confirmed while designing this feature specifically to avoid that shortcut.

---

### Q4. Why an allowlist of MIME types instead of a denylist (block `.exe`, `.sh`, etc.)?

**Answer:** An allowlist only needs to be "safe by inclusion" — every entry has been deliberately decided to be fine. A denylist needs to anticipate every dangerous type in advance, and is trivially incomplete (new dangerous extensions, double extensions like `file.jpg.exe`, MIME-type spoofing). `settings.ATTACHMENTS_ALLOWED_MIME_TYPES` explicitly lists images, PDF, plain text/CSV, Office docs, and zip — deliberately excluding anything executable or browser-renderable-as-script (`.exe`, `.sh`, `.js`, `.html`, and notably `.svg`, since SVG files can embed `<script>` tags).

**Follow-up:** What's the operational cost of an allowlist? → Every legitimate new file type a user wants to upload requires a deliberate code change to extend the list — more friction than a denylist, but that friction is the point: it forces an explicit decision instead of defaulting to "allow unless proven dangerous."

---

### Q5. What's the known limitation with storing attachments on local disk, and why wasn't it fixed immediately?

**Answer:** Render's filesystem is ephemeral — wiped on every redeploy. Files uploaded to a `Render`-hosted instance of this app would be lost the next time the service redeploys, which happens on every code push. This is documented explicitly in `backend/core/config.py`'s comment on `ATTACHMENTS_STORAGE_PATH` and in `docs/architecture/system-architecture.md`'s deployment diagram, rather than being silently left as a surprise. It wasn't fixed immediately because local disk was the explicit, deliberate choice for this stage (simpler to build and test, no cloud credentials/bucket setup needed) — the relative-path design (Q2) means the S3 migration is a scoped, well-understood follow-up for Milestone 14, not a rewrite.

**Follow-up:** Why document a known limitation instead of just fixing it now? → Scope discipline — building S3 support now would mean setting up cloud credentials, a bucket, IAM policy, and testing infrastructure before attachments could be demoed at all. Shipping the working local-disk version first, with the limitation explicit and the migration path already designed for, is the pragmatic incremental choice — and is itself a good interview answer about prioritization.
