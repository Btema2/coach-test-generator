"""Sends sign-in emails through Brevo's HTTPS API or SMTP, or prints them when running locally.

Render's free plan blocks outbound SMTP ports (25, 465, 587), so production there uses
BREVO_API_KEY, which goes out over HTTPS (port 443).
"""

import logging
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr

import requests

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


@dataclass(frozen=True)
class MailConfig:
    sender: str
    host: str = ""
    port: int = 587
    user: str = ""
    password: str = ""
    starttls: bool = True
    brevo_api_key: str = ""


def mail_config_from_env() -> MailConfig | None:
    sender = os.getenv("MAIL_FROM", "").strip()
    if not sender:
        return None
    api_key = os.getenv("BREVO_API_KEY", "").strip()
    if api_key:
        return MailConfig(sender=sender, brevo_api_key=api_key)
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        return None
    return MailConfig(
        sender=sender,
        host=host,
        port=int(os.getenv("SMTP_PORT", "587")),
        user=os.getenv("SMTP_USER", "").strip(),
        password=os.getenv("SMTP_PASSWORD", ""),
        starttls=os.getenv("SMTP_STARTTLS", "1") != "0",
    )


def send_mail(cfg: MailConfig | None, to: str, subject: str, body: str, console: bool = False) -> None:
    """Send a plain-text email. Raises if it could not be sent."""
    if cfg is None:
        if not console:
            raise RuntimeError("Email is not configured")
        print(f"\n  ── Email to {to} ──\n  Subject: {subject}\n\n{body}", flush=True)
        return

    if cfg.brevo_api_key:
        _send_brevo(cfg, to, subject, body)
    else:
        _send_smtp(cfg, to, subject, body)
    logger.info("Sent sign-in email to %s", to)


def _send_brevo(cfg: MailConfig, to: str, subject: str, body: str) -> None:
    name, address = parseaddr(cfg.sender)
    sender = {"email": address}
    if name:
        sender["name"] = name
    resp = requests.post(
        BREVO_API_URL,
        json={"sender": sender, "to": [{"email": to}], "subject": subject, "textContent": body},
        headers={"api-key": cfg.brevo_api_key, "accept": "application/json"},
        timeout=15,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Brevo refused the email ({resp.status_code}): {resp.text[:300]}")


def _send_smtp(cfg: MailConfig, to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = cfg.sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    if cfg.port == 465:
        server = smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=15, context=context)
    else:
        server = smtplib.SMTP(cfg.host, cfg.port, timeout=15)
    with server:
        if cfg.port != 465 and cfg.starttls:
            server.starttls(context=context)
        if cfg.user:
            server.login(cfg.user, cfg.password)
        server.send_message(msg)
