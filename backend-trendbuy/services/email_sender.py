import asyncio
import logging
import os
import smtplib
from decimal import Decimal
from email.mime.text import MIMEText

from services.notifier import discount_summary, format_price_es


logger = logging.getLogger(__name__)

# Generic SMTP, not a specific vendor SDK - same "user supplies their own
# credentials in .env" pattern as TELEGRAM_BOT_TOKEN/EXPO_ACCESS_TOKEN, works
# with a Gmail app password, or any real provider's SMTP relay (Mailgun,
# Brevo, SES...) without locking this project into one vendor's API.
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM") or SMTP_USER or "no-reply@trendbuy.local"


def _send_sync(to_email: str, subject: str, body: str) -> bool:
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        logger.warning(
            "SMTP not configured (SMTP_HOST/SMTP_USER/SMTP_PASSWORD missing) - email to %s not sent: %s",
            to_email,
            subject,
        )
        return False

    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to_email], message.as_string())
        return True
    except Exception as exc:
        logger.exception("Failed to send email to %s: %s", to_email, exc)
        return False


async def send_email(to_email: str, subject: str, body: str) -> bool:
    # smtplib is blocking I/O - offloaded so it never stalls the FastAPI
    # event loop (called from a request handler) or the Celery async task.
    return await asyncio.to_thread(_send_sync, to_email, subject, body)


async def send_magic_link_email(to_email: str, confirm_url: str) -> bool:
    subject = "Tu enlace de acceso a TrendBuy"
    body = (
        "Hola,\n\n"
        "Pulsa este enlace para iniciar sesión en TrendBuy (caduca en 15 minutos "
        "y solo funciona una vez):\n\n"
        f"{confirm_url}\n\n"
        "Si no has pedido este enlace, puedes ignorar este correo con tranquilidad.\n"
    )
    return await send_email(to_email, subject, body)


async def send_deal_alert_email(
    to_email: str,
    product_name: str,
    old_price: Decimal,
    new_price: Decimal,
    url: str,
    unsubscribe_url: str,
) -> bool:
    savings, percent = discount_summary(old_price, new_price)
    subject = f"Baja un {percent}%: {product_name[:80]}"
    body = (
        f"{product_name}\n\n"
        f"Antes: {format_price_es(old_price)} €\n"
        f"Ahora: {format_price_es(new_price)} €\n"
        f"Ahorras {format_price_es(savings)} € (-{percent}%)\n\n"
        f"Ver oferta: {url}\n\n"
        "Recibes esto porque tienes este producto o categoría en tus favoritos de TrendBuy.\n"
        f"Darse de baja de estos avisos: {unsubscribe_url}\n"
    )
    return await send_email(to_email, subject, body)
