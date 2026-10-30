"""
Outbound email primitive.

This is deliberately small and generic (send_email(to, subject, body)) —
the only current caller is AuthService's password-reset flow, so there's
no separate EmailService abstraction layer; composing the reset email's
subject/body lives in AuthService, right next to the workflow it belongs to.
If a second use case shows up (e.g. "ticket assigned to you" notifications),
that's the signal to extract a proper EmailService.

Zero new dependencies: smtplib and email.mime are both in the Python
standard library. No SendGrid/Mailgun/SES SDK needed for this project's
scale, and it keeps local dev working without any third-party account.

Dev-mode fallback: if SMTP isn't configured (the common case for local
development — nobody wants to set up a real mailbox mid-tutorial), the
email is logged instead of sent. This is a deliberate, visible fallback
(not a silent swallow) — the log line makes it obvious in development
that "sending" is actually just printing, and it's exactly what you'd
disable by setting SMTP_HOST in production.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

from backend.core.config import settings


def send_email(to: str, subject: str, body: str) -> None:
    """
    Send a plain-text email, or log it if SMTP isn't configured.

    Never raises on delivery failure — a broken mail server should not
    break the request that triggered the email (e.g. forgot-password
    always returns a generic success response regardless of whether the
    email actually goes out, both for security — see AuthService — and
    for resilience). Failures are logged loudly instead.
    """
    if not settings.SMTP_HOST:
        logger.info(
            f"[DEV MODE — no SMTP configured] Would send email\n"
            f"  to      : {to}\n"
            f"  subject : {subject}\n"
            f"  body    :\n{body}"
        )
        return

    message = MIMEMultipart()
    message["From"] = (
        settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME or "noreply@helpdesk-ai.local"
    )
    message["To"] = to
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
        logger.info(f"Email sent to {to}: {subject}")
    except Exception as e:
        # Intentionally broad: any SMTP failure (auth, connection, timeout)
        # should degrade to "log and move on", not surface as a 500 to
        # a user who just asked to reset their password.
        logger.error(f"Failed to send email to {to}: {type(e).__name__}: {e}")
