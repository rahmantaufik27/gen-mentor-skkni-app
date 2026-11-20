"""
Outgoing email (account verification + password reset links).

Settings come from backend/mail.ini (gitignored, same idea as db.ini) -
see mail.ini.example. Three states:

  - no mail.ini, or enabled = false : email features are OFF. Registration
    and login behave exactly as before (no verification required) and
    "Forgot password" says email isn't set up. This keeps the app usable
    until a mailbox exists.
  - backend = log  : emails are written to the backend log instead of being
    sent. For local testing without a mailbox.
  - backend = smtp : emails are sent through the configured SMTP server
    (e.g. smtp.gmail.com:587 with a Gmail app password).
"""

import configparser
import os
import smtplib
from email.message import EmailMessage

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mail.ini")


def _load() -> dict:
    parser = configparser.ConfigParser()
    if not os.path.exists(_CONFIG_PATH) or not parser.read(_CONFIG_PATH, encoding="utf-8") or not parser.has_section("mail"):
        return {"enabled": False}
    section = parser["mail"]
    return {
        "enabled": section.getboolean("enabled", fallback=False),
        "backend": section.get("backend", "smtp").strip().lower(),
        "host": section.get("host", "smtp.gmail.com").strip(),
        "port": section.getint("port", fallback=587),
        "username": section.get("username", "").strip(),
        "password": section.get("password", "").replace(" ", ""),
        "from_name": section.get("from_name", "GAMASKILL").strip(),
        "app_url": section.get("app_url", "http://localhost:8501").strip().rstrip("/"),
    }


def mail_enabled() -> bool:
    return bool(_load().get("enabled"))


def app_url() -> str:
    return _load().get("app_url", "http://localhost:8501")


def send_email(to_address: str, subject: str, body: str) -> None:
    """Send one plain-text email. Raises on failure so callers can report it."""
    cfg = _load()
    if not cfg.get("enabled"):
        raise RuntimeError("Email is not configured")

    if cfg["backend"] == "log":
        print(f"[mail:log] to={to_address} subject={subject}\n{body}\n[mail:log end]", flush=True)
        return

    message = EmailMessage()
    message["From"] = f'{cfg["from_name"]} <{cfg["username"]}>'
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
        server.starttls()
        server.login(cfg["username"], cfg["password"])
        server.send_message(message)
