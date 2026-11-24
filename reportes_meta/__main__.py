"""Uso:
  python -m reportes_meta generar --periodo semanal [--demo] [--cliente SLUG] [--sin-mail] [--fecha AAAA-MM-DD]
  python -m reportes_meta nuevo-cliente            # formulario interactivo en la terminal
  python -m reportes_meta desde-issue cuerpo.md    # crea el cliente desde el formulario de GitHub
  python -m reportes_meta listar
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import traceback
from datetime import date
from pathlib import Path

from . import acciones as acciones_mod
from . import analisis as analisis_mod
from . import config, correo, ia, metricas, panel, periodos, render
from . import formato as fmt
from .config import Cliente, RAIZ

SALIDA = RAIZ / "salida"


def generar_cliente(c: Cliente, p: periodos.Periodo, demo: bool) -> dict:
    if demo:
        from . import demo as demo_mod
        datos = demo_mod.generar(c, p)
    else:
        from . import meta_api
        datos = meta_api.descargar(c, p)
    m = metricas.calcular(c, datos)
    plan = acciones_mod.generar(c, p, m["ads"])
    a = analisis_mod.analizar(c, p, m, plan)
    textos_ia = ia.redactar(c, p, m, a, plan)
    g = render.preparar_graficos(c, m)
    ctx = dict(cliente=c, periodo=p, m=m, analisis=a, plan=plan, ia=textos_ia, graficos=g)
    carpeta = SALIDA / p.clave
    pdf_cliente = render.a_pdf(render.html("cliente.html.j2", **ctx), carpeta / f"{c.slug}-cliente-{p.clave}.pdf")
    pdfs = [pdf_cliente]
    if os.environ.get("PDF_INTERNO") == "1":  # opcional: tu vista principal es el panel web
        pdfs.append(render.a_pdf(render.html("interno.html.j2", **ctx), carpeta / f"{c.slug}-INTERNO-{p.clave}.pdf"))
    return {**ctx, "pdfs": pdfs}


def cuerpo_mail(p, reportes, errores, url_panel) -> str:
    filas = ""
    colores = {"verde": "#0f7b3e", "amarillo": "#b54708", "rojo": "#b42318", "gris": "#6b7280"}
    for r in reportes:
        a, c = r["analisis"], r["cliente"]
        ads = r["m"]["ads"]
        prioridades = [f"{x.tipo}: {x.anuncio or x.conjunto or x.campana}" for x in r["plan"].acciones[:3]] or \
                      [h.titulo for h in a.hallazgos if h.nivel in ("critico", "alerta")][:3]
        filas += (f'<tr><td style="padding:8px;border-bottom:1px solid #eee"><b>{c.nombre}</b><br>'
                  f'<span style="color:{colores[a.estado]}">● {a.estado_texto}</span></td>'
                  f'<td style="padding:8px;border-bottom:1px solid #eee;text-align:right">'
                  f'{fmt.moneda(ads["actual"]["gasto"], c.moneda) if ads else "—"}<br>'
                  f'<small>CPA {fmt.moneda(ads["actual"]["cpa"], c.moneda) if ads else "—"}</small></td>'
                  f'<td style="padding:8px;border-bottom:1px solid #eee;font-size:13px">'
                  + "<br>".join(f"• {t}" for t in prioridades) + "</td></tr>")
    err = "".join(f"<li>{e}</li>" for e in errores)
    enlace = (f'<p><a href="{url_panel}" style="display:inline-block;background:#4f46e5;color:#fff;padding:10px 18px;'
              f'border-radius:8px;text-decoration:none;font-weight:600">Abrir el panel y el plan de acción →</a></p>'
              if url_panel else "")
    return f"""<div style="font-family:Segoe UI,Arial,sans-serif;max-width:720px">
<h2 style="margin:0 0 4px">{p.titulo}</h2><p style="color:#555">{len(reportes)} cliente(s) procesados.</p>{enlace}
<table style="border-collapse:collapse;width:100%"><tr style="text-align:left;color:#777;font-size:12px">
<th style="padding:8px">Cliente</th><th style="padding:8px;text-align:right">Inversión</th><th style="padding:8px">Prioridades</th></tr>{filas}</table>
{"<h3>Errores</h3><ul>" + err + "</ul>" if err else ""}
<p style="color:#777;font-size:12px">Adjuntos: el PDF de cada cliente, listo para reenviar.
El plan de acción completo está en el panel{"" if url_panel else " (va adjunto como archivo HTML: abrilo con el navegador)"}.</p></div>"""


def cmd_generar(args):
    hoy = date.fromisoformat(args.fecha) if args.fecha else None
    p = periodos.calcular(args.periodo, hoy)
    clientes = config.cargar_clientes(incluir_ejemplos=args.demo)
    if args.cliente:
        clientes = [c for c in clientes if c.slug == args.cliente]
    else:
        clientes = [c for c in clientes if args.periodo in c.frecuencias]
    if not clientes:
        print("No hay clientes para procesar. Agregá uno en clientes/ o con 'nuevo-cliente'.")
        return 1
    print(f"▶ {p.titulo} · {len(clientes)} cliente(s){' · MODO DEMO' if args.demo else ''}")
    reportes, errores = [], []
    for c in clientes:
        print(f" • {c.nombre}")
        try:
            r = generar_cliente(c, p, args.demo)
            reportes.append(r)
            print(f"   {r['analisis'].resumen_interno}")
        except Exception as e:  # noqa: BLE001 - un cliente con error no frena al resto
            traceback.print_exc()
            errores.append(f"{c.nombre}: {e}")
    if not reportes:
        print("Ningún reporte se pudo generar.")
        return 1
    panel_local = panel.publicar(p, reportes)
    print(f" ✔ Panel: {panel_local}")
    if not args.sin_mail:
        url = os.environ.get("PANEL_URL")
        url = f"{url.rstrip('/')}/{p.tipo}.html" if url else None
        adjuntos = [pdf for r in reportes for pdf in r["pdfs"]]
        if panel_local and not url:  # sin panel online, el panel va adjunto
            adjuntos.append(panel_local)
        prefijo = "[DEMO] " if args.demo else ""
        correo.enviar(f"{prefijo}Reportes Meta · {p.titulo}", cuerpo_mail(p, reportes, errores, url), adjuntos)
    print(f" ✔ Listo. Archivos en {SALIDA / p.clave}")
    return 0 if not errores else 2


# ---------------------------------------------------------------- alta de clientes
PREGUNTAS = [
    ("nombre", "Nombre del cliente / marca", True),
    ("rubro", "Rubro (ej: indumentaria, estética, inmobiliaria)", False),
    ("objetivo", f"Objetivo principal ({' / '.join(config.OBJETIVOS)})", True),
    ("moneda", "Moneda de la cuenta (ARS, USD, ...)", False),
    ("ad_account_id", "ID de la cuenta publicitaria (act_... o solo números; vacío si no hace Ads)", False),
    ("page_id", "ID de la página de Facebook (vacío si no aplica)", False),
    ("instagram_id", "ID de la cuenta de Instagram Business (vacío si no aplica)", False),
    ("presupuesto_mensual", "Presupuesto mensual de Ads", False),
    ("cpa_objetivo", "Costo máximo aceptable por resultado (CPA objetivo)", False),
    ("roas_objetivo", "ROAS objetivo (solo ventas, ej: 4)", False),
    ("ticket_promedio", "Ticket promedio de venta (solo ventas)", False),
    ("frecuencias", "Frecuencia de reportes (semanal, mensual o ambas)", False),
    ("color", "Color de marca en HEX (ej: #E11D48)", False),
    ("logo_url", "URL pública del logo (opcional)", False),
    ("notas", "Notas / contexto para el análisis (opcional)", False),
]


def cmd_nuevo_cliente(_args):
    print("Alta de cliente nuevo. Enter para dejar vacío.\n")
    d = {}
    for clave, texto, obligatoria in PREGUNTAS:
        while True:
            v = input(f"{texto}: ").strip()
            if v or not obligatoria:
                break
        if v:
            d[clave] = v
    c = Cliente.desde_dict(d)
    print(f"\n✔ Guardado en {config.guardar_cliente(c)}")
    return 0


ETIQUETAS_ISSUE = {
    "nombre del cliente": "nombre", "rubro": "rubro", "objetivo principal": "objetivo", "moneda": "moneda",
    "id de la cuenta publicitaria": "ad_account_id", "id de la página de facebook": "page_id",
    "id de instagram business": "instagram_id", "presupuesto mensual de ads": "presupuesto_mensual",
    "cpa objetivo": "cpa_objetivo", "roas objetivo": "roas_objetivo", "ticket promedio": "ticket_promedio",
    "frecuencia de reportes": "frecuencias", "color de marca": "color", "logo": "logo_url",
    "notas para el análisis": "notas",
}


def parsear_issue(cuerpo: str) -> dict:
    d = {}
    for bloque in re.split(r"^###\s+", cuerpo, flags=re.M)[1:]:
        titulo, _, valor = bloque.partition("\n")
        titulo = re.sub(r"\s*\(.*?\)\s*", " ", titulo).strip().lower()
        clave = next((v for k, v in ETIQUETAS_ISSUE.items() if titulo.startswith(k)), None)
        valor = valor.strip()
        if not clave or not valor or valor == "_No response_":
            continue
        if clave == "frecuencias":
            marcadas = re.findall(r"- \[[xX]\]\s*(\w+)", valor)
            valor = [m.lower() for m in marcadas] or None
        elif clave == "objetivo":
            valor = valor.split("—")[0].split("-")[0].strip()
        if valor:
            d[clave] = valor
    return d


def cmd_desde_issue(args):
    cuerpo = Path(args.archivo).read_text(encoding="utf-8")
    d = parsear_issue(cuerpo)
    if "nombre" not in d:
        print("ERROR: el formulario no tiene 'Nombre del cliente'.")
        return 1
    c = Cliente.desde_dict(d)
    ruta = config.guardar_cliente(c)
    print(c.slug)
    print(f"Guardado en {ruta}", file=sys.stderr)
    return 0


def cmd_listar(_args):
    for c in config.cargar_clientes(solo_activos=False):
        print(f"{'✔' if c.activo else '✖'} {c.slug:<24} {c.nombre:<28} {c.objetivo:<14} "
              f"ads={'sí' if c.tiene_ads else 'no'} fb={'sí' if c.page_id else 'no'} "
              f"ig={'sí' if c.instagram_id else 'no'} {','.join(c.frecuencias)}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="reportes_meta", description="Reportes automáticos de Meta")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generar")
    g.add_argument("--periodo", choices=["semanal", "mensual"], required=True)
    g.add_argument("--cliente")
    g.add_argument("--demo", action="store_true", help="usar datos de prueba (no necesita token)")
    g.add_argument("--sin-mail", action="store_true")
    g.add_argument("--fecha", help="simular que hoy es esta fecha (AAAA-MM-DD)")
    g.set_defaults(f=cmd_generar)
    sub.add_parser("nuevo-cliente").set_defaults(f=cmd_nuevo_cliente)
    di = sub.add_parser("desde-issue")
    di.add_argument("archivo")
    di.set_defaults(f=cmd_desde_issue)
    sub.add_parser("listar").set_defaults(f=cmd_listar)
    args = ap.parse_args(argv)
    return args.f(args)


if __name__ == "__main__":
    sys.exit(main())
