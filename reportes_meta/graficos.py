"""Gráficos en SVG (matplotlib) para incrustar en los PDF y en el panel.
Un gráfico = una medida = un eje (nunca doble eje). Marcas finas, grilla suave."""
from __future__ import annotations

import io
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from . import formato as fmt  # noqa: E402

SERIE = "#2a78d6"
SERIE_SUAVE = "#9ec5f4"
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
GRILLA = "#e6e5e0"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRILLA,
    "axes.labelcolor": TEXTO_2, "xtick.color": TEXTO_2, "ytick.color": TEXTO_2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "svg.fonttype": "none",
})


def _svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", transparent=True)
    plt.close(fig)
    s = buf.getvalue()
    return s[s.find("<svg"):]


def _ejes(fig_w=7.2, fig_h=2.0):
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.grid(axis="y", color=GRILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    return fig, ax


def barras_diarias(diario: list[dict], clave: str, moneda: str | None = None, titulo_y: str = "") -> str | None:
    filas = [d for d in diario if d.get("fecha")]
    if len(filas) < 2:
        return None
    fechas = [date.fromisoformat(d["fecha"]) for d in filas]
    valores = [d.get(clave) or 0 for d in filas]
    fig, ax = _ejes()
    ax.bar(range(len(valores)), valores, color=SERIE, width=0.62)
    paso = 1 if len(fechas) <= 10 else max(1, len(fechas) // 8)
    ax.set_xticks(range(0, len(fechas), paso))
    ax.set_xticklabels([f"{f.day}/{f.month}" for f in fechas][::paso])
    ax.yaxis.set_major_formatter(FuncFormatter(
        lambda v, _: fmt.moneda(v, moneda, 0) if moneda else fmt.compacto(v)))
    if titulo_y:
        ax.set_ylabel(titulo_y)
    return _svg(fig)


def linea_diaria(diario: list[dict], clave: str, moneda: str | None = None, objetivo: float | None = None) -> str | None:
    filas = [d for d in diario if d.get("fecha") and d.get(clave)]
    if len(filas) < 2:
        return None
    fechas = [date.fromisoformat(d["fecha"]) for d in filas]
    valores = [d[clave] for d in filas]
    fig, ax = _ejes()
    ax.plot(range(len(valores)), valores, color=SERIE, linewidth=2, marker="o", markersize=4,
            markeredgecolor="white", markeredgewidth=1.5)
    if objetivo:
        ax.axhline(objetivo, color=TEXTO_2, linewidth=1, linestyle=(0, (4, 3)))
        ax.text(len(valores) - 1, objetivo, "  objetivo", va="bottom", ha="right", color=TEXTO_2, fontsize=8)
    paso = 1 if len(fechas) <= 10 else max(1, len(fechas) // 8)
    ax.set_xticks(range(0, len(fechas), paso))
    ax.set_xticklabels([f"{f.day}/{f.month}" for f in fechas][::paso])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt.moneda(v, moneda, 0) if moneda else fmt.compacto(v)))
    ax.set_ylim(bottom=0)
    return _svg(fig)


def barras_horizontales(etiquetas: list[str], valores: list[float], moneda: str | None = None,
                        porcentaje: bool = False) -> str | None:
    if not valores:
        return None
    etiquetas = [e if len(e) <= 34 else e[:32] + "…" for e in etiquetas][::-1]
    valores = valores[::-1]
    fig, ax = plt.subplots(figsize=(6.4, 0.42 * len(valores) + 0.4))
    ax.barh(etiquetas, valores, color=SERIE, height=0.55)
    ax.grid(False)
    ax.spines["bottom"].set_visible(False)
    ax.set_xticks([])
    ax.tick_params(length=0)
    tope = max(valores) or 1
    for i, v in enumerate(valores):
        txt = fmt.porcentaje(v, 0) if porcentaje else (fmt.moneda(v, moneda) if moneda else fmt.compacto(v))
        ax.text(v + tope * 0.015, i, txt, va="center", color=TEXTO, fontsize=8.5)
    ax.set_xlim(0, tope * 1.22)
    return _svg(fig)
