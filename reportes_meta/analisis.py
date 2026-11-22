"""Motor de interpretación (reglas): resumen simple para el cliente y diagnóstico técnico
con recomendaciones accionables para la agencia. Es 100 % gratis y determinístico."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import formato as fmt
from .config import Cliente
from .periodos import Periodo

# Umbrales generales (ajustables)
CTR_BAJO = 0.008       # 0,8 % CTR de enlace
CTR_BUENO = 0.015
FREC_ALTA_SEMANAL = 3.0
FREC_ALTA_MENSUAL = 4.5
FREC_AD_FATIGA = 4.0
CAMBIO_FUERTE = 0.20


@dataclass
class Hallazgo:
    nivel: str  # critico | alerta | oportunidad | ok
    area: str   # Ads | Facebook | Instagram | Presupuesto
    titulo: str
    detalle: str
    accion: str = ""

    @property
    def orden(self) -> int:
        return {"critico": 0, "alerta": 1, "oportunidad": 2, "ok": 3}[self.nivel]


@dataclass
class Analisis:
    estado: str = "verde"  # verde | amarillo | rojo | gris
    estado_texto: str = ""
    resumen_cliente: list[str] = field(default_factory=list)
    destacados_cliente: list[str] = field(default_factory=list)
    proximos_pasos_cliente: list[str] = field(default_factory=list)
    hallazgos: list[Hallazgo] = field(default_factory=list)
    resumen_interno: str = ""

    def agregar(self, *a, **kw):
        self.hallazgos.append(Hallazgo(*a, **kw))


def _sube_baja(v, bueno_si_sube=True, umbral=0.03):
    if v is None or abs(v) < umbral:
        return "se mantuvo estable"
    palabra = "subió" if v > 0 else "bajó"
    return f"{palabra} {fmt.variacion(abs(v)).lstrip('+')}"


def _analizar_ads(c: Cliente, p: Periodo, m: dict, a: Analisis):
    act, var = m["actual"], m["var"]
    mon = c.moneda
    sing, plur = m["resultado_singular"], m["resultado_plural"]
    ant = p.etiqueta_anterior
    costo_label = "costo por mil personas alcanzadas" if c.objetivo == "reconocimiento" else f"costo por {sing}"

    # ---------------- Resumen para el cliente (lenguaje simple)
    a.resumen_cliente.append(
        f"Invertimos {fmt.moneda(act['gasto'], mon)} en publicidad y llegamos a "
        f"{fmt.compacto(act['alcance'])} personas, que vieron los anuncios {fmt.numero(act['frecuencia'], 1)} veces en promedio.")
    if c.objetivo == "reconocimiento":
        a.resumen_cliente.append(
            f"Cada mil personas alcanzadas costaron {fmt.moneda(act['cpa'], mon)} "
            f"({_sube_baja(var.get('cpa'))} respecto de {ant}).")
    else:
        if act["resultados"]:
            linea = (f"Conseguimos {fmt.numero(act['resultados'])} {plur if act['resultados'] != 1 else sing} "
                     f"a {fmt.moneda(act['cpa'], mon)} cada una")
            if var.get("resultados") is not None:
                linea += f". La cantidad {_sube_baja(var['resultados'])} y el costo {_sube_baja(var.get('cpa'))} frente a {ant}"
            a.resumen_cliente.append(linea + ".")
        else:
            a.resumen_cliente.append(f"En este período todavía no se registraron {plur} atribuidas a los anuncios.")
    if act.get("roas"):
        a.resumen_cliente.append(
            f"Las ventas atribuidas a los anuncios sumaron {fmt.moneda(act['valor'], mon)}: por cada $1 invertido "
            f"volvieron $ {fmt.numero(act['roas'], 2)} en ventas.")
    a.resumen_cliente.append(
        f"{fmt.numero(act['clics_link'])} personas hicieron clic para conocer más "
        f"({fmt.porcentaje(act['ctr'], 2)} de quienes vieron un anuncio).")

    buenos = [x for x in m["anuncios"] if x["resultados"] > 0 and x["cpa"]]
    if buenos:
        top = min(buenos, key=lambda x: x["cpa"]) if c.objetivo != "reconocimiento" else max(buenos, key=lambda x: x["alcance"])
        a.destacados_cliente.append(f"El anuncio que mejor funcionó fue «{top['nombre']}» ({fmt.numero(top['resultados'])} {plur}).")

    # ---------------- Diagnóstico interno
    cpa, cpa_obj = act["cpa"], c.cpa_objetivo
    if c.objetivo != "reconocimiento":
        if cpa_obj and cpa:
            desvio = cpa / cpa_obj - 1
            if desvio > 0.3:
                a.agregar("critico", "Ads", f"CPA {fmt.variacion(desvio)} sobre el objetivo",
                          f"CPA {fmt.moneda(cpa, mon)} vs objetivo {fmt.moneda(cpa_obj, mon)}.",
                          "Pausar los anuncios con CPA > 2× objetivo, concentrar presupuesto en los 2-3 mejores "
                          "y revisar landing/oferta si la tasa de conversión cayó.")
            elif desvio > 0.05:
                a.agregar("alerta", "Ads", f"CPA {fmt.variacion(desvio)} sobre el objetivo",
                          f"CPA {fmt.moneda(cpa, mon)} vs objetivo {fmt.moneda(cpa_obj, mon)}.",
                          "Recortar 20-30 % el presupuesto de los conjuntos más caros y testear 2 creatividades nuevas.")
            elif desvio < -0.2 and act["resultados"] >= 5:
                a.agregar("oportunidad", "Ads", "CPA muy por debajo del objetivo: hay margen para escalar",
                          f"CPA {fmt.moneda(cpa, mon)} ({fmt.variacion(desvio)} vs objetivo).",
                          "Subir presupuesto 15-20 % cada 3-4 días en las campañas ganadoras (sin superar 20 % por "
                          "cambio para no reiniciar el aprendizaje).")
            else:
                a.agregar("ok", "Ads", "CPA dentro del objetivo",
                          f"CPA {fmt.moneda(cpa, mon)} vs objetivo {fmt.moneda(cpa_obj, mon)}.")
        elif act["resultados"] == 0 and act["gasto"] > 0:
            a.agregar("critico", "Ads", f"Sin {plur} registradas",
                      f"Se invirtieron {fmt.moneda(act['gasto'], mon)} sin {plur} atribuidas.",
                      "Verificar píxel/API de conversiones y el evento optimizado en Administrador de eventos; "
                      "si el tracking está bien, revisar oferta y segmentación.")
        if not cpa_obj:
            a.agregar("alerta", "Ads", "El cliente no tiene CPA objetivo cargado",
                      "Sin objetivo no se puede evaluar si el costo es bueno o malo.",
                      f"Cargar 'cpa_objetivo' en clientes/{c.slug}.yaml.")

        v = var.get("cpa")
        if v is not None and v > CAMBIO_FUERTE:
            causas = []
            if (var.get("cpm") or 0) > 0.15:
                causas.append(f"el CPM subió {fmt.variacion(var['cpm'])} (más competencia o audiencia más chica)")
            if (var.get("ctr") or 0) < -0.15:
                causas.append(f"el CTR cayó {fmt.variacion(var['ctr'])} (posible fatiga creativa)")
            if (var.get("tasa_conversion") or 0) < -0.15:
                causas.append(f"la tasa de conversión cayó {fmt.variacion(var['tasa_conversion'])} (revisar landing, stock, precio o checkout)")
            a.agregar("alerta", "Ads", f"El CPA empeoró {fmt.variacion(v)} vs {ant}",
                      ("Causa probable: " + "; ".join(causas) + ".") if causas else "Sin una causa única evidente en CPM/CTR/conversión.",
                      "Atacar primero la causa principal indicada.")
        elif v is not None and v < -CAMBIO_FUERTE:
            a.agregar("ok", "Ads", f"El CPA mejoró {fmt.variacion(v)} vs {ant}", "Mantener la estructura actual.")

    roas, roas_obj = act.get("roas"), c.roas_objetivo
    if roas_obj and c.objetivo == "ventas":
        if roas is None or roas < roas_obj * 0.8:
            a.agregar("critico" if (roas or 0) < roas_obj * 0.6 else "alerta", "Ads",
                      "ROAS por debajo del objetivo",
                      f"ROAS {fmt.numero(roas or 0, 2)} vs objetivo {fmt.numero(roas_obj, 2)}.",
                      "Priorizar remarketing y catálogo; revisar ticket promedio (packs, envío gratis desde X monto).")
        elif roas > roas_obj * 1.25:
            a.agregar("oportunidad", "Ads", "ROAS por encima del objetivo",
                      f"ROAS {fmt.numero(roas, 2)} vs objetivo {fmt.numero(roas_obj, 2)}.",
                      "Escalar presupuesto gradualmente o abrir nuevas audiencias de prospección.")

    frec_lim = FREC_ALTA_MENSUAL if p.tipo == "mensual" else FREC_ALTA_SEMANAL
    if act["frecuencia"] and act["frecuencia"] > frec_lim:
        a.agregar("alerta", "Ads", f"Frecuencia alta ({fmt.numero(act['frecuencia'], 1)})",
                  "La misma gente está viendo los anuncios demasiadas veces: riesgo de saturación y CPA en aumento.",
                  "Ampliar audiencias (Advantage+ / lookalikes más amplios) y rotar creatividades.")

    if act["ctr"] is not None:
        if act["ctr"] < CTR_BAJO:
            a.agregar("alerta", "Ads", f"CTR de enlace bajo ({fmt.porcentaje(act['ctr'], 2)})",
                      "Los anuncios no generan suficiente interés para hacer clic.",
                      "Probar ganchos más fuertes en los primeros 3 segundos, UGC/testimonios y un CTA más claro.")
        elif act["ctr"] > CTR_BUENO:
            a.agregar("ok", "Ads", f"CTR de enlace sólido ({fmt.porcentaje(act['ctr'], 2)})", "Las creatividades captan atención.")

    if (var.get("cpm") or 0) > 0.25:
        a.agregar("alerta", "Ads", f"CPM subió {fmt.variacion(var['cpm'])}",
                  "Pagar más por cada mil impresiones encarece todo el embudo.",
                  "Revisar si la audiencia se achicó, probar ubicaciones Advantage+ y evitar superposición de conjuntos.")

    if c.objetivo == "ventas" and act["carritos"] and act["resultados"]:
        tasa_cierre = act["resultados"] / act["carritos"]
        if tasa_cierre < 0.2:
            a.agregar("alerta", "Ads", f"Solo {fmt.porcentaje(tasa_cierre, 0)} de los carritos terminan en compra",
                      f"{fmt.numero(act['carritos'])} agregados al carrito → {fmt.numero(act['resultados'])} compras.",
                      "Revisar costos de envío, medios de pago y checkout; activar remarketing de carrito abandonado.")

    # Anuncios para pausar / escalar
    if c.objetivo != "reconocimiento":
        ref = cpa_obj or cpa
        if ref:
            pausar = [x for x in m["anuncios"] if x["gasto"] > 2 * ref and (x["resultados"] == 0 or (x["cpa"] or 0) > 2 * ref)]
            escalar = [x for x in m["anuncios"] if x["resultados"] >= 3 and x["cpa"] and x["cpa"] < 0.75 * ref]
            if pausar:
                a.agregar("critico" if len(pausar) > 2 else "alerta", "Ads", f"{len(pausar)} anuncio(s) para pausar",
                          "; ".join(f"«{x['nombre']}» ({x['campana']}): gastó {fmt.moneda(x['gasto'], mon)}, "
                                    f"{fmt.numero(x['resultados'])} {plur}" for x in pausar[:5]),
                          "Pausarlos y redistribuir ese presupuesto hacia los ganadores.")
            if escalar:
                a.agregar("oportunidad", "Ads", f"{len(escalar)} anuncio(s) ganadores",
                          "; ".join(f"«{x['nombre']}»: CPA {fmt.moneda(x['cpa'], mon)}" for x in escalar[:5]),
                          "Duplicarlos en un conjunto nuevo o darles más presupuesto; crear variaciones del mismo concepto.")

    fatigados = [x for x in m["anuncios"] if (x["frecuencia"] or 0) > FREC_AD_FATIGA and x["gasto"] > act["gasto"] * 0.05]
    if fatigados:
        a.agregar("alerta", "Ads", "Creatividades con fatiga",
                  ", ".join(f"«{x['nombre']}» (frec. {fmt.numero(x['frecuencia'], 1)})" for x in fatigados[:5]),
                  "Reemplazar o refrescar (nuevo gancho, nuevo formato) en los próximos días.")

    if m["campanas"] and m["campanas"][0]["participacion"] and m["campanas"][0]["participacion"] > 0.75 and len(m["campanas"]) > 1:
        a.agregar("oportunidad", "Ads", "Presupuesto muy concentrado en una campaña",
                  f"«{m['campanas'][0]['nombre']}» se lleva {fmt.porcentaje(m['campanas'][0]['participacion'], 0)} de la inversión.",
                  "Está bien si es la ganadora, pero conviene reservar 10-20 % para testeo.")

    if c.objetivo in ("ventas", "leads", "mensajes"):
        limite_aprendizaje = 50 * p.dias / 7
        en_aprendizaje = [n for n, cj in m["conjuntos"].items() if cj["resultados"] < limite_aprendizaje * 0.3 and cj["gasto"] > 0]
        if len(en_aprendizaje) >= 3:
            a.agregar("oportunidad", "Ads", f"{len(en_aprendizaje)} conjuntos con pocas conversiones",
                      "Con menos de ~50 conversiones por semana por conjunto, Meta no sale de la fase de aprendizaje.",
                      "Consolidar conjuntos (menos conjuntos con más presupuesto cada uno) o usar Advantage+.")

    activos = [x for x in m["anuncios"] if x["gasto"] > 0]
    if len(activos) < 3:
        a.agregar("oportunidad", "Ads", "Pocas creatividades activas",
                  f"Solo {len(activos)} anuncio(s) con inversión.",
                  "Tener al menos 3-5 creatividades por conjunto para que el algoritmo optimice.")

    # Presupuesto
    if c.presupuesto_mensual:
        if p.tipo == "mensual":
            uso = act["gasto"] / c.presupuesto_mensual
            if uso < 0.85 or uso > 1.1:
                a.agregar("alerta", "Presupuesto", f"Se usó {fmt.porcentaje(uso, 0)} del presupuesto mensual",
                          f"Invertido {fmt.moneda(act['gasto'], mon)} de {fmt.moneda(c.presupuesto_mensual, mon)}.",
                          "Ajustar presupuestos diarios para el mes próximo.")
        else:
            proyeccion = act["gasto"] / p.dias * 30
            uso = proyeccion / c.presupuesto_mensual
            if uso < 0.85 or uso > 1.1:
                a.agregar("alerta", "Presupuesto", f"Ritmo de gasto: {fmt.porcentaje(uso, 0)} del presupuesto",
                          f"Al ritmo de esta semana se invertirían {fmt.moneda(proyeccion, mon)} en el mes "
                          f"(presupuesto {fmt.moneda(c.presupuesto_mensual, mon)}).",
                          f"Llevar el gasto diario a ~{fmt.moneda(c.presupuesto_mensual / 30, mon)}.")


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _analizar_organico(o: dict, p: Periodo, a: Analisis):
    red = "Instagram" if o["red"] == "instagram" else "Facebook"
    ant = p.etiqueta_anterior
    v = o["var"]
    partes = []
    if o.get("alcance") is not None:
        partes.append(f"llegamos a {fmt.compacto(o['alcance'])} cuentas ({_sube_baja(v.get('alcance'))} vs {ant})")
    if o.get("interacciones") is not None:
        partes.append(f"recibimos {fmt.compacto(o['interacciones'])} interacciones")
    if o.get("nuevos_seguidores") is not None:
        partes.append(f"sumamos {fmt.numero(o['nuevos_seguidores'])} seguidores nuevos")
    if partes:
        a.resumen_cliente.append(f"En {red} " + ", ".join(partes) + ".")
    if o["top"]:
        t = o["top"][0]
        a.destacados_cliente.append(
            f"La publicación de {red} con más interacciones fue «{(t['texto'] or 'sin texto')[:60]}» "
            f"({fmt.numero(t.get('interacciones'))} interacciones).")

    # Interno
    semanas = max(p.dias / 7, 1)
    por_semana = o["cantidad_publicaciones"] / semanas
    if por_semana < 3:
        a.agregar("alerta", red, f"Baja frecuencia de publicación ({fmt.numero(por_semana, 1)} por semana)",
                  f"{o['cantidad_publicaciones']} publicaciones en el período.",
                  "Apuntar a 3-5 publicaciones semanales para sostener el alcance orgánico.")
    if v.get("alcance") is not None and v["alcance"] < -0.25:
        a.agregar("alerta", red, f"Alcance orgánico cayó {fmt.variacion(v['alcance'])}",
                  "Menos distribución que el período anterior.",
                  "Aumentar reels/videos cortos, usar tendencias y colaboraciones, y publicar en los horarios con mejor respuesta.")
    if o.get("engagement") is not None:
        if o["engagement"] < 0.01:
            a.agregar("alerta", red, f"Engagement bajo ({fmt.porcentaje(o['engagement'], 2)})",
                      "Interacciones / alcance por debajo de 1 %.",
                      "Sumar preguntas, encuestas y CTA a comentar/guardar; contenido más útil o polémico.")
    tipos = o["por_tipo"]
    if len(tipos) >= 2:
        mejor = max(tipos.items(), key=lambda kv: kv[1]["promedio_interacciones"])
        peor = min(tipos.items(), key=lambda kv: kv[1]["promedio_interacciones"])
        if peor[1]["promedio_interacciones"] and mejor[1]["promedio_interacciones"] / peor[1]["promedio_interacciones"] > 1.5:
            a.agregar("oportunidad", red, f"Los {mejor[0].lower()} rinden más",
                      f"{mejor[0]}: {fmt.numero(mejor[1]['promedio_interacciones'])} interacciones promedio vs "
                      f"{peor[0].lower()}: {fmt.numero(peor[1]['promedio_interacciones'])}.",
                      f"Aumentar la proporción de {mejor[0].lower()} en el calendario. Los mejores pueden usarse como anuncios.")
    if o["por_dia"] and o["cantidad_publicaciones"] >= 5:
        dia = max(o["por_dia"], key=o["por_dia"].get)
        hora = max(o["por_hora"], key=o["por_hora"].get) if o["por_hora"] else None
        a.agregar("oportunidad", red, "Mejor momento para publicar",
                  f"Mejor respuesta los {DIAS[dia]}" + (f", alrededor de las {hora}:00 h." if hora is not None else "."),
                  "Programar las piezas más importantes en ese horario.")
    if o["top"] and o["top"][0].get("interacciones"):
        a.agregar("oportunidad", red, "Contenido candidato a anuncio",
                  f"«{(o['top'][0]['texto'] or '')[:60]}» fue la mejor publicación orgánica.",
                  "Probarla como anuncio (publicación existente) para aprovechar la prueba social.")


def analizar(c: Cliente, p: Periodo, m: dict) -> Analisis:
    a = Analisis()
    if m["ads"]:
        _analizar_ads(c, p, m["ads"], a)
    for red in ("instagram", "facebook"):
        if m[red]:
            _analizar_organico(m[red], p, a)
    a.hallazgos.sort(key=lambda h: (h.orden, h.area))

    criticos = sum(h.nivel == "critico" for h in a.hallazgos)
    alertas = sum(h.nivel == "alerta" for h in a.hallazgos)
    if not (m["ads"] or m["facebook"] or m["instagram"]):
        a.estado, a.estado_texto = "gris", "Sin datos"
    elif criticos:
        a.estado, a.estado_texto = "rojo", f"{criticos} punto(s) crítico(s)"
    elif alertas >= 3:
        a.estado, a.estado_texto = "amarillo", f"{alertas} alertas"
    else:
        a.estado, a.estado_texto = "verde", "En línea con los objetivos"

    # Próximos pasos para el cliente (traducción amable de las acciones)
    pasos = []
    areas = {h.titulo for h in a.hallazgos if h.nivel in ("critico", "alerta", "oportunidad")}
    texto = " ".join(areas).lower()
    if "pausar" in texto or "cpa" in texto:
        pasos.append("Vamos a concentrar la inversión en los anuncios que mejores resultados están dando.")
    if "ganadores" in texto or "escalar" in texto or "roas por encima" in texto:
        pasos.append("Hay anuncios funcionando muy bien: vamos a darles más alcance de forma gradual.")
    if "fatiga" in texto or "frecuencia alta" in texto or "ctr" in texto:
        pasos.append("Vamos a renovar las piezas creativas para mantener el interés del público.")
    if "rinden más" in texto or "frecuencia de publicación" in texto:
        pasos.append("Vamos a ajustar el calendario de contenido priorizando los formatos que más funcionan.")
    if "carritos" in texto:
        pasos.append("Te vamos a compartir sugerencias para que más personas terminen su compra en la web.")
    if not pasos:
        pasos.append("Seguimos con la estrategia actual y testeando nuevas ideas para seguir mejorando.")
    a.proximos_pasos_cliente = pasos[:4]

    a.resumen_interno = (f"{c.nombre}: {a.estado_texto}. "
                         f"{criticos} crítico(s), {alertas} alerta(s), "
                         f"{sum(h.nivel == 'oportunidad' for h in a.hallazgos)} oportunidad(es).")
    return a
