"""Envío del resumen por mail (Gmail gratis con 'contraseña de aplicación')."""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def enviar(asunto: str, html_cuerpo: str, adjuntos: list[Path]) -> bool:
    usuario = os.environ.get("GMAIL_USER")
    clave = os.environ.get("GMAIL_APP_PASSWORD")
    destino = os.environ.get("REPORT_TO") or usuario
    if not (usuario and clave):
        print("   ⚠ Falta GMAIL_USER / GMAIL_APP_PASSWORD: no se envía mail (los PDF quedan en salida/).")
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = asunto, usuario, destino
    msg.set_content("Tu cliente de correo no muestra HTML. Los reportes van adjuntos.")
    msg.add_alternative(html_cuerpo, subtype="html")
    total = 0
    for ruta in adjuntos:
        datos = ruta.read_bytes()
        total += len(datos)
        if total > 22 * 1024 * 1024:  # Gmail admite 25 MB
            print(f"   ⚠ Adjuntos demasiado grandes; se omite {ruta.name}")
            continue
        sub = "pdf" if ruta.suffix == ".pdf" else "html"
        msg.add_attachment(datos, maintype="application" if sub == "pdf" else "text", subtype=sub, filename=ruta.name)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(usuario, clave)
        s.send_message(msg)
    print(f"   ✉ Mail enviado a {destino}")
    return True
