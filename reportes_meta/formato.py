"""Formato de números, monedas, porcentajes y fechas en español (es-AR)."""
from __future__ import annotations

from datetime import date

SIMBOLOS = {"ARS": "$", "USD": "US$", "EUR": "€", "CLP": "$", "MXN": "$", "UYU": "$U",
            "COP": "$", "PEN": "S/", "BRL": "R$", "PYG": "₲"}

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def numero(valor, decimales: int = 0) -> str:
    if valor is None:
        return "—"
    s = f"{valor:,.{decimales}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def compacto(valor) -> str:
    if valor is None:
        return "—"
    v = abs(valor)
    if v >= 1_000_000:
        return numero(valor / 1_000_000, 1) + " M"
    if v >= 10_000:
        return numero(valor / 1_000, 1) + " mil"
    return numero(valor)


def moneda(valor, codigo: str = "ARS", decimales: int | None = None) -> str:
    if valor is None:
        return "—"
    if decimales is None:
        decimales = 0 if abs(valor) >= 100 else 2
    return f"{SIMBOLOS.get(codigo, codigo + ' ')} {numero(valor, decimales)}"


def porcentaje(valor, decimales: int = 1) -> str:
    """valor en proporción (0.0123 -> '1,2 %')."""
    if valor is None:
        return "—"
    return f"{numero(valor * 100, decimales)} %"


def variacion(valor) -> str:
    """valor en proporción con signo (0.15 -> '+15 %')."""
    if valor is None:
        return "—"
    signo = "+" if valor > 0 else ("−" if valor < 0 else "")
    return f"{signo}{numero(abs(valor) * 100, 0)} %"


def fecha(d: date, con_anio: bool = False) -> str:
    s = f"{d.day} de {MESES[d.month - 1]}"
    return s + f" de {d.year}" if con_anio else s


def rango(desde: date, hasta: date) -> str:
    if desde.month == hasta.month and desde.year == hasta.year:
        return f"{desde.day} al {hasta.day} de {MESES[hasta.month - 1]} de {hasta.year}"
    return f"{fecha(desde, desde.year != hasta.year)} al {fecha(hasta, True)}"


def mes(d: date) -> str:
    return f"{MESES[d.month - 1].capitalize()} {d.year}"
