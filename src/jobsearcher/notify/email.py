"""Gmail SMTP for the digest (ARCHITECTURE §11). Sends to the user's own address only."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from jobsearcher.config import env

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
TIMEOUT_S = 30


class EmailNotConfigured(RuntimeError):
    pass


def send_email(subject: str, text: str, html: str | None = None, *, smtp_factory=None) -> None:
    """Send to GMAIL_ADDRESS from GMAIL_ADDRESS. `smtp_factory` is replaced in tests."""
    e = env()
    if not e.gmail_address or not e.gmail_app_password:
        raise EmailNotConfigured("GMAIL_ADDRESS og GMAIL_APP_PASSWORD mangler i .env; digesten ble ikke sendt.")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Jobbsøk <{e.gmail_address}>"
    msg["To"] = e.gmail_address
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    factory = smtp_factory or smtplib.SMTP_SSL  # looked up per call, so tests can block it
    with factory(SMTP_HOST, SMTP_PORT, timeout=TIMEOUT_S) as smtp:
        smtp.login(e.gmail_address, e.gmail_app_password.replace(" ", ""))
        smtp.send_message(msg)
