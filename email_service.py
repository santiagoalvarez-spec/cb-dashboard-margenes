"""
Servicio de envío de emails vía SMTP.
Soporta adjuntar un DataFrame como Excel.
"""
import io
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd

from email_db import log_email


def _build_message(smtp_config: dict, to_email: str, subject: str,
                    body_html: str, attachment_df: pd.DataFrame | None) -> MIMEMultipart:
    msg = MIMEMultipart("mixed")
    msg["From"] = f"{smtp_config.get('from_name', 'Dashboard Márgenes')} <{smtp_config['from_email']}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body_html, "html", "utf-8"))
    msg.attach(alt)

    if attachment_df is not None and not attachment_df.empty:
        buf = io.BytesIO()
        attachment_df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        part = MIMEBase("application", "octet-stream")
        part.set_payload(buf.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            'attachment; filename="reporte_margenes.xlsx"',
        )
        msg.attach(part)

    return msg


def send_single_email(
    smtp_config: dict,
    to_email: str,
    subject: str,
    body_html: str,
    attachment_df: pd.DataFrame | None = None,
) -> tuple[bool, str]:
    """Envía un email y registra el resultado en el log."""
    try:
        msg = _build_message(smtp_config, to_email, subject, body_html, attachment_df)
        host = smtp_config["host"]
        port = int(smtp_config["port"])
        use_ssl = smtp_config.get("use_ssl", False)

        if use_ssl:
            with smtplib.SMTP_SSL(host, port) as server:
                server.login(smtp_config["user"], smtp_config["password"])
                server.sendmail(smtp_config["from_email"], to_email, msg.as_string())
        else:
            with smtplib.SMTP(host, port) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_config["user"], smtp_config["password"])
                server.sendmail(smtp_config["from_email"], to_email, msg.as_string())

        log_email(to_email, subject, "enviado")
        return True, ""
    except Exception as exc:
        log_email(to_email, subject, "error", str(exc))
        return False, str(exc)


def send_bulk_emails(
    smtp_config: dict,
    contacts: list[tuple],
    subject: str,
    body_template: str,
    attachment_df: pd.DataFrame | None = None,
) -> list[dict]:
    """
    Envía emails a todos los contactos.
    body_template puede usar {name} y {company} como placeholders.
    contacts: lista de tuplas (id, name, email, company, active, created_at)
    """
    results = []
    for row in contacts:
        _, name, email, company, *_ = row
        body = (
            body_template
            .replace("{name}", name)
            .replace("{company}", company or "")
        )
        success, err = send_single_email(smtp_config, email, subject, body, attachment_df)
        results.append({"email": email, "name": name, "success": success, "error": err})
    return results
