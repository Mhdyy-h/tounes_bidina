"""
Real email delivery for hotel/stakeholder hazard notifications, via standard
SMTP (Python's stdlib smtplib - no new dependency, no third-party service
lock-in). Gated behind environment variables the user must supply themselves -
same pattern as every other credential in this project (FIRMS_API_KEY,
EARTHDATA_USERNAME/PASSWORD): SMTP_HOST, SMTP_PORT, SMTP_USERNAME,
SMTP_PASSWORD, SMTP_FROM_EMAIL.

If not configured, or if the send itself fails, the notification is logged
instead of silently dropped - callers always get an honest {"sent": bool, ...}
back, never a fabricated "sent successfully" when nothing was actually sent.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(
        os.getenv("SMTP_HOST") and os.getenv("SMTP_USERNAME") and os.getenv("SMTP_PASSWORD")
    )


def send_notification_email(to_email: str, subject: str, body: str) -> dict:
    """Returns {"sent": bool, "method": "smtp"|"log_only", "detail": str}."""
    if not is_configured():
        logger.warning(
            "SMTP not configured - notification logged instead of sent. To=%s Subject=%s Body=%s",
            to_email, subject, body,
        )
        return {
            "sent": False,
            "method": "log_only",
            "detail": "SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD not set - logged instead of "
            "sent. See README for setup instructions.",
        }

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL", username)

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(username, password)
            server.sendmail(from_email, [to_email], msg.as_string())
        return {"sent": True, "method": "smtp", "detail": f"Sent via {host}:{port}"}
    except Exception as exc:
        logger.warning("SMTP send failed (%s) - notification logged instead of sent", exc)
        return {"sent": False, "method": "log_only", "detail": f"SMTP send failed: {exc}"}
