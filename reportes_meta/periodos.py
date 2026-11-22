"""Cálculo de períodos: semana anterior completa (lunes a domingo) o mes anterior completo."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from . import formato


@dataclass(frozen=True)
class Periodo:
    tipo: str  # "semanal" | "mensual"
    desde: date
    hasta: date
    prev_desde: date
    prev_hasta: date

    @property
    def dias(self) -> int:
        return (self.hasta - self.desde).days + 1

    @property
    def titulo(self) -> str:
        if self.tipo == "mensual":
            return f"Reporte mensual · {formato.mes(self.desde)}"
        return f"Reporte semanal · {formato.rango(self.desde, self.hasta)}"

    @property
    def etiqueta_anterior(self) -> str:
        return "el mes anterior" if self.tipo == "mensual" else "la semana anterior"

    @property
    def clave(self) -> str:
        if self.tipo == "mensual":
            return self.desde.strftime("%Y-%m")
        return f"{self.desde:%Y}-S{self.desde.isocalendar()[1]:02d}"


def calcular(tipo: str, hoy: date | None = None) -> Periodo:
    hoy = hoy or date.today()
    if tipo == "semanal":
        hasta = hoy - timedelta(days=hoy.weekday() + 1)  # domingo pasado
        desde = hasta - timedelta(days=6)
        return Periodo(tipo, desde, hasta, desde - timedelta(days=7), hasta - timedelta(days=7))
    if tipo == "mensual":
        hasta = hoy.replace(day=1) - timedelta(days=1)
        desde = hasta.replace(day=1)
        prev_hasta = desde - timedelta(days=1)
        return Periodo(tipo, desde, hasta, prev_hasta.replace(day=1), prev_hasta)
    raise ValueError("El período debe ser 'semanal' o 'mensual'")
