"""Renderiza HTML (Jinja2) y lo convierte a PDF con Chromium (Playwright)."""
from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import formato as fmt
from . import graficos
from .metricas import _tipo_legible

PLANTILLAS = Path(__file__).parent / "plantillas"

env = Environment(loader=FileSystemLoader(PLANTILLAS), autoescape=select_autoescape(["html", "j2"]))
env.filters.update({
    "num": fmt.numero, "compacto": fmt.compacto, "moneda": fmt.moneda, "pct": fmt.porcentaje,
    "var": fmt.variacion, "tipo": _tipo_legible,
})


def _clase_var(v, bueno_si_sube=True):
    if v is None or abs(v) < 0.03:
        return "neutro"
    return "bueno" if (v > 0) == bueno_si_sube else "malo"


env.globals["clase_var"] = _clase_var


def preparar_graficos(cliente, metricas) -> dict:
    g = {}
    ads = metricas.get("ads")
    if ads:
        g["gasto_diario"] = graficos.barras_diarias(ads["diario"], "gasto", cliente.moneda)
        if cliente.objetivo != "reconocimiento":
            g["resultados_diarios"] = graficos.barras_diarias(ads["diario"], "resultados")
            g["cpa_diario"] = graficos.linea_diaria(ads["diario"], "cpa", cliente.moneda, cliente.cpa_objetivo)
        camp = ads["campanas"][:8]
        g["campanas_gasto"] = graficos.barras_horizontales([c["nombre"] for c in camp],
                                                           [c["gasto"] for c in camp], cliente.moneda)
    for red in ("instagram", "facebook"):
        o = metricas.get(red)
        if o and o["por_tipo"]:
            tipos = sorted(o["por_tipo"].items(), key=lambda kv: kv[1]["promedio_interacciones"], reverse=True)
            g[f"{red}_formatos"] = graficos.barras_horizontales(
                [t for t, _ in tipos], [v["promedio_interacciones"] for _, v in tipos])
    return g


def html(plantilla: str, **contexto) -> str:
    return env.get_template(plantilla).render(fmt=fmt, **contexto)


def a_pdf(html_str: str, salida: Path) -> Path:
    from playwright.sync_api import sync_playwright

    salida.parent.mkdir(parents=True, exist_ok=True)
    opciones = {"args": ["--no-sandbox"]}
    if os.environ.get("CHROMIUM_PATH"):
        opciones["executable_path"] = os.environ["CHROMIUM_PATH"]
    with sync_playwright() as pw:
        nav = pw.chromium.launch(**opciones)
        pagina = nav.new_page()
        pagina.set_content(html_str, wait_until="networkidle", timeout=60_000)
        pagina.emulate_media(media="print")
        pagina.pdf(path=str(salida), format="A4", print_background=True,
                   margin={"top": "14mm", "bottom": "16mm", "left": "12mm", "right": "12mm"},
                   display_header_footer=True, header_template="<span></span>",
                   footer_template='<div style="font-size:8px;color:#888;width:100%;text-align:center;">'
                                   'Página <span class="pageNumber"></span> de <span class="totalPages"></span></div>')
        nav.close()
    return salida
