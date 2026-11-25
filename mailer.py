"""Sends sign-in emails over SMTP, or prints them when running locally."""

import logging
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MailConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str
    starttls: bool


def mail_config_from_env() -> MailConfig | None:
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("MAIL_FROM", "").strip()
    if not host or not sender:
        return None
    return MailConfig(
        host=host,
        port=int(os.getenv("SMTP_PORT", "587")),
        user=os.getenv("SMTP_USER", "").strip(),
        password=os.getenv("SMTP_PASSWORD", ""),
        sender=sender,
        starttls=os.getenv("SMTP_STARTTLS", "1") != "0",
    )


def send_mail(cfg: MailConfig | None, to: str, subject: str, body: str, console: bool = False) -> None:
    """Send a plain-text email. Raises on SMTP failure."""
    if cfg is None:
        if not console:
            raise RuntimeError("Email is not configured")
        print(f"\n  ── Email to {to} ──\n  Subject: {subject}\n\n{body}", flush=True)
        return

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
    logger.info("Sent sign-in email to %s", to)
