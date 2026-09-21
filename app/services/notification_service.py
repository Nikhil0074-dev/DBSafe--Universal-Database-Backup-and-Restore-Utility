"""Optional e-mail notifications. Never raises: a mail problem must not fail a backup."""
import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

log = logging.getLogger("dbsafe")


def notifications_enabled():
    cfg = current_app.config
    return bool(cfg.get("SMTP_HOST") and cfg.get("NOTIFY_TO"))


def notify(event, subject, body):
    """Send a notification for *event*. Always logs it, e-mails it when configured."""
    log.info("NOTIFICATION [%s] %s", event, subject)
    if not notifications_enabled():
        return False
    cfg = current_app.config
    try:
        message = EmailMessage()
        message["Subject"] = f"[DBSafe] {subject}"
        message["From"] = cfg["NOTIFY_FROM"]
        recipients = [r.strip() for r in cfg["NOTIFY_TO"].split(",") if r.strip()]
        message["To"] = ", ".join(recipients)
        message.set_content(body)
        with smtplib.SMTP(cfg["SMTP_HOST"], int(cfg["SMTP_PORT"]), timeout=15) as smtp:
            if cfg.get("SMTP_USE_TLS"):
                smtp.starttls()
            if cfg.get("SMTP_USER"):
                smtp.login(cfg["SMTP_USER"], cfg.get("SMTP_PASSWORD") or "")
            smtp.send_message(message)
        return True
    except Exception as exc:
        log.warning("Could not send notification e-mail: %s", exc)
        return False
