"""Plan de acción concreto para Meta Ads.

Para cada cambio recomendado indica:
  · DÓNDE  → campaña › conjunto › anuncio (y el creativo, con miniatura y formato)
  · QUÉ    → el cambio exacto (pausar, subir el presupuesto de $X a $Y, cambiar el gancho del video…)
  · CÓMO   → los pasos en el Administrador de anuncios
  · POR QUÉ → los números que lo justifican, comparados con el objetivo y con el resto de la cuenta
  · IMPACTO → qué se espera ganar o ahorrar
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from . import formato as fmt
from .config import Cliente
from .periodos import Periodo

# Referencias de la industria (ajustables)
HOOK_MIN = 0.25          # ≥25 % de las impresiones deberían pasar los 3 s del video
HOLD_MIN = 0.20          # ≥20 % de quienes pasan los 3 s deberían llegar a ThruPlay
CTR_MIN = 0.008          # CTR de enlace mínimo aceptable (0,8 %)
FREC_ANUNCIO_FATIGA = 4.0
SUBA_PRESUPUESTO = 0.20  # cambios ≤20 % no reinician la fase de aprendizaje
MIN_IMPRESIONES = 1500   # por debajo no hay datos suficientes para juzgar un creativo

PRIORIDAD_ORDEN = {"alta": 0, "media": 1, "baja": 2}
PALABRAS_RMK = ("remarketing", "retargeting", "rmk", "visitantes", "carrito", "compradores", "interacc")

IDEAS_GANCHO = [
    "Arrancar mostrando el resultado final o el producto en uso (no el logo).",
    "Una pregunta directa al dolor del cliente: «¿Cansada de…?».",
    "Texto grande en pantalla en el primer segundo con el beneficio o la oferta.",
    "Movimiento o un cambio de plano antes del segundo 1; una persona hablando a cámara (estilo UGC).",
]


@dataclass
class Accion:
    prioridad: str          # alta | media | baja
    tipo: str               # etiqueta corta del cambio
    nivel: str              # anuncio | conjunto | campaña
    campana: str
    que: str
    porque: list[str]
    como: list[str]
    conjunto: str | None = None
    anuncio: str | None = None
    miniatura: str | None = None
    formato: str | None = None
    impacto: str | None = None
    monto: float = 0.0      # dinero involucrado (para ordenar)
    campana_id: str | None = None
    conjunto_id: str | None = None
    categoria: str = "otro" # pausar | escalar | creativo | presupuesto | audiencia | estructura | landing

    @property
    def donde(self) -> str:
        partes = [f"Campaña «{self.campana}»"]
        if self.conjunto:
            partes.append(f"Conjunto «{self.conjunto}»")
        if self.anuncio:
            partes.append(f"Anuncio «{self.anuncio}»")
        return " › ".join(partes)


@dataclass
class Plan:
    acciones: list[Accion] = field(default_factory=list)
    referencias: dict = field(default_factory=dict)

    def agregar(self, a: Accion):
        self.acciones.append(a)

    @property
    def por_campana(self) -> dict:
        d = defaultdict(list)
        for a in self.acciones:
            d[a.campana].append(a)
        return dict(d)


def _ruta(campana, conjunto=None, pestana="Anuncios") -> str:
    r = f"Administrador de anuncios → Campañas → abrí «{campana}»"
    if conjunto:
        r += f" → conjunto «{conjunto}»"
    return r + f" → pestaña {pestana}."


def _es_rmk(nombre: str | None) -> bool:
    return any(p in (nombre or "").lower() for p in PALABRAS_RMK)


def generar(c: Cliente, p: Periodo, m: dict) -> Plan:
    plan = Plan()
    if not m:
        return plan
    obj = c.objetivo
    mon = c.moneda
    act = m["actual"]
    sing, plur = m["resultado_singular"], m["resultado_plural"]
    periodo_txt = "esta semana" if p.tipo == "semanal" else "este mes"
    por_periodo = "por semana" if p.tipo == "semanal" else "por mes"
    conv = obj not in ("reconocimiento",)
    ref = (c.cpa_objetivo or act["cpa"]) if conv else None
    ref_txt = (f"el objetivo de {fmt.moneda(c.cpa_objetivo, mon)}" if c.cpa_objetivo
               else f"el promedio de la cuenta ({fmt.moneda(act['cpa'], mon)})")
    ref_del = "d" + ref_txt[1:] if ref_txt.startswith("el ") else ref_txt  # "del objetivo…"

    def res(n) -> str:
        return f"{fmt.numero(n)} {sing if round(n) == 1 else plur}"
    ctr_cta = act["ctr"] or CTR_MIN
    tasa_cta = act["tasa_conversion"]
    frec_lim = 3.5 if p.tipo == "semanal" else 5.0
    limite_aprendizaje = 50 * p.dias / 7

    anuncios = [a for a in m["anuncios"] if a["gasto"] > 0]
    activos = [a for a in anuncios if a["activo"]]

    # Formato que mejor funciona en la cuenta (para recomendar creativos nuevos)
    por_formato = defaultdict(lambda: [0.0, 0.0])
    for a in anuncios:
        por_formato[a["formato"]][0] += a["gasto"]
        por_formato[a["formato"]][1] += a["resultados"]
    mejor_formato = None
    if conv:
        candidatos = {f: g / r for f, (g, r) in por_formato.items() if r >= 2}
        if candidatos:
            mejor_formato = min(candidatos, key=candidatos.get)
    plan.referencias = {"cpa_ref": ref, "ref_txt": ref_txt, "ctr_cuenta": act["ctr"], "mejor_formato": mejor_formato,
                        "hook_min": HOOK_MIN, "hold_min": HOLD_MIN}

    # Mejor anuncio de cada conjunto (para comparar)
    mejor_en_conjunto = {}
    for a in anuncios:
        if conv and a["resultados"] > 0:
            actual = mejor_en_conjunto.get(a["conjunto_id"])
            if not actual or a["cpa"] < actual["cpa"]:
                mejor_en_conjunto[a["conjunto_id"]] = a
    activos_por_conjunto = defaultdict(int)
    for a in activos:
        activos_por_conjunto[a["conjunto_id"]] += 1

    acciones_por_anuncio = defaultdict(int)

    def base_ad(a, **kw):
        return dict(nivel="anuncio", campana=a["campana"], conjunto=a["conjunto"], anuncio=a["nombre"],
                    miniatura=a["miniatura"], formato=a["formato"], campana_id=a["campana_id"],
                    conjunto_id=a["conjunto_id"], **kw)

    def diagnostico_creativo(a) -> tuple[str, str, list[str], list[str]] | None:
        """Devuelve (tipo, qué, por qué, cómo) según dónde se cae el embudo del anuncio."""
        if a["impresiones"] < MIN_IMPRESIONES:
            return None
        if a["formato"] == "video" and a["hook_rate"] is not None and a["hook_rate"] < HOOK_MIN:
            return ("Cambiar el gancho del video",
                    "Reemplazar los primeros 3 segundos del video (el resto puede quedar igual).",
                    [f"Solo el {fmt.porcentaje(a['hook_rate'], 0)} de las personas que lo vieron pasó los 3 primeros "
                     f"segundos (referencia: {fmt.porcentaje(HOOK_MIN, 0)} o más). La gente lo pasa de largo antes de "
                     f"entender la propuesta."],
                    [_ruta(a["campana"], a["conjunto"]),
                     f"Marcá «{a['nombre']}» → Duplicar → mismo conjunto.",
                     "En el duplicado, subí el video con un comienzo nuevo. Ideas: " + " / ".join(IDEAS_GANCHO[:3]),
                     "Dejá los dos activos 3-4 días y quedate con el que tenga más «Reproducciones de 3 segundos» "
                     "por impresión (agregá esa columna en Personalizar columnas → Video)."])
        if a["formato"] == "video" and a["hold_rate"] is not None and a["hold_rate"] < HOLD_MIN:
            return ("Acortar / dar ritmo al video",
                    "Editar el video para que sea más corto y dinámico, con el producto antes del segundo 5.",
                    [f"El gancho funciona ({fmt.porcentaje(a['hook_rate'], 0)} pasa los 3 s) pero solo "
                     f"{fmt.porcentaje(a['hold_rate'], 0)} sigue mirando hasta el final (referencia: "
                     f"{fmt.porcentaje(HOLD_MIN, 0)}). Se pierden antes de llegar a la oferta o al CTA."],
                    [_ruta(a["campana"], a["conjunto"]),
                     f"Duplicá «{a['nombre']}» en el mismo conjunto.",
                     "Subí una versión de 15-20 s: cortes cada 2-3 s, subtítulos, producto visible antes del segundo 5, "
                     "oferta y CTA dichos y escritos en los últimos 3 s.",
                     "Compará a los 3-4 días: ThruPlays por reproducción de 3 s y CPA."])
        if a["ctr"] is not None and a["ctr"] < max(CTR_MIN, ctr_cta * 0.7):
            texto_actual = f" Hoy el texto empieza: «{a['texto'][:80]}…»." if a.get("texto") else ""
            cta_sug = {"ventas": "Comprar", "leads": "Registrarte / Obtener oferta",
                       "mensajes": "Enviar mensaje", "trafico": "Más información"}.get(obj, "")
            pasos = [_ruta(a["campana"], a["conjunto"]),
                     f"Duplicá «{a['nombre']}» en el mismo conjunto y en el duplicado cambiá:",
                     "• Texto principal: primera línea con el beneficio concreto o la oferta (precio, % OFF, envío "
                     "gratis, cuotas) y una sola llamada a la acción." + texto_actual,
                     "• Visual: producto en uso o persona real; la oferta escrita sobre la imagen; en formato 4:5 o 9:16."]
            if a.get("cta") and cta_sug and a["cta"] in ("LEARN_MORE", "NO_BUTTON") and obj in ("ventas", "leads", "mensajes"):
                pasos.append(f"• Botón: hoy es «{a['cta']}»; cambialo a «{cta_sug}».")
            pasos.append("Dejá los dos 3-4 días y pausá el que tenga peor CTR y CPA.")
            return ("Cambiar texto / imagen",
                    "Probar una variación con otro mensaje y otro visual: el anuncio no genera interés para hacer clic.",
                    [f"CTR de enlace {fmt.porcentaje(a['ctr'], 2)} vs {fmt.porcentaje(ctr_cta, 2)} del promedio de la cuenta "
                     f"(mínimo sano: {fmt.porcentaje(CTR_MIN, 1)}). De cada 1.000 personas que lo ven, solo "
                     f"{fmt.numero(a['ctr'] * 1000, 0)} hacen clic."],
                    pasos)
        if (conv and tasa_cta and a["tasa_conversion"] is not None and a["clics_link"] >= 30
                and a["ctr"] and a["ctr"] >= ctr_cta * 0.9 and a["tasa_conversion"] < tasa_cta * 0.6):
            pasos = {
                "ventas": ["Abrí el link del anuncio desde el celular y verificá: que lleve al producto exacto del anuncio "
                           "(no a la home), que el precio y la promo coincidan, que cargue en menos de 3 s y que haya stock.",
                           "Si el anuncio muestra varios productos, mandá a una colección filtrada.",
                           "Revisá que el costo de envío no aparezca recién en el checkout."],
                "leads": ["Abrí el formulario como usuario: dejalo en 3-4 preguntas como máximo.",
                          "Agregá una pantalla de introducción que repita la oferta del anuncio.",
                          "Si va a una web, verificá que el formulario se vea sin scrollear en el celular."],
                "mensajes": ["Revisá el mensaje de bienvenida y las preguntas frecuentes de WhatsApp/Instagram.",
                             "Medí el tiempo de respuesta: más de 15 minutos hace perder la mayoría de las consultas.",
                             "Que el primer mensaje automático repita la oferta del anuncio."],
                "trafico": ["Verificá velocidad de carga y que la página corresponda al anuncio."],
            }[obj]
            return ("Revisar la página de destino",
                    "El anuncio atrae clics pero esas visitas no se convierten: ajustar lo que pasa después del clic.",
                    [f"CTR {fmt.porcentaje(a['ctr'], 2)} (bien, igual o mejor que la cuenta), pero solo "
                     f"{fmt.porcentaje(a['tasa_conversion'], 1)} de los clics termina en {sing} vs "
                     f"{fmt.porcentaje(tasa_cta, 1)} del promedio. El problema no es el creativo sino la promesa vs lo que encuentran."],
                    pasos)
        return None

    # ------------------------------------------------------------------ ANUNCIOS
    for a in activos:
        if not conv or not ref:
            continue
        mejor = mejor_en_conjunto.get(a["conjunto_id"])
        comparacion = (f" En el mismo conjunto, «{mejor['nombre']}» consigue {plur} a {fmt.moneda(mejor['cpa'], mon)}."
                       if mejor and mejor["id"] != a["id"] else "")
        malo_sin_resultados = a["gasto"] > 2 * ref and a["resultados"] == 0
        malo_caro = a["resultados"] > 0 and a["cpa"] > 2 * ref and a["gasto"] > 1.5 * ref
        if malo_sin_resultados or malo_caro:
            diag = diagnostico_creativo(a)
            porque = [f"Gastó {fmt.moneda(a['gasto'], mon)} {periodo_txt} y consiguió {res(a['resultados'])}"
                      + (f" (CPA {fmt.moneda(a['cpa'], mon)}, {fmt.numero(a['cpa'] / ref, 1)} veces {ref_txt})." if a["resultados"]
                         else f", cuando {ref_txt} indica que con ese gasto deberían haber salido ~{fmt.numero(a['gasto'] / ref)}.")
                      + comparacion]
            if diag:
                porque.append("Diagnóstico del creativo: " + diag[2][0])
            unico = activos_por_conjunto[a["conjunto_id"]] <= 1
            reinv = act["cpa"] or ref  # conservador: CPA promedio de la cuenta
            if unico:
                como = [_ruta(a["campana"], a["conjunto"]),
                        "Es el único anuncio activo del conjunto: primero subí 2-3 creativos nuevos ahí "
                        + (f"(el formato que mejor convierte en la cuenta es {mejor_formato}). " if mejor_formato else ". ")
                        + "Ver «Cambiar texto/imagen» o «Cambiar el gancho» más abajo para saber qué cambiar.",
                        f"Cuando los nuevos estén activos (pasada la revisión), desactivá «{a['nombre']}»."]
                tipo, que = "Reemplazar anuncio", "Subir 2-3 creativos nuevos al conjunto y después apagar este anuncio."
            else:
                como = [_ruta(a["campana"], a["conjunto"]), f"Desactivá el interruptor de «{a['nombre']}».",
                        "No cambies el presupuesto del conjunto ese mismo día: Meta redistribuye solo el gasto "
                        "hacia los anuncios que quedan activos."]
                tipo, que = "Pausar anuncio", "Apagar este anuncio."
            plan.agregar(Accion(prioridad="alta", tipo=tipo, que=que, porque=porque, como=como,
                                impacto=f"Libera ~{fmt.moneda(a['gasto'], mon)} {por_periodo}; reinvertidos al CPA promedio "
                                        f"de la cuenta ({fmt.moneda(reinv, mon)}) serían ≈{res(a['gasto'] / reinv)} más.",
                                monto=a["gasto"], categoria="pausar", **base_ad(a)))
            acciones_por_anuncio[a["id"]] += 1
            continue

        # Ganador → duplicar y crear variaciones
        if a["resultados"] >= (3 if p.tipo == "semanal" else 6) and a["cpa"] < 0.75 * ref:
            prospeccion = not _es_rmk(a["campana"])
            como = [_ruta(a["campana"], a["conjunto"]),
                    f"Marcá «{a['nombre']}» → Duplicar → en «Publicación» elegí «Usar publicación existente» "
                    "(conserva likes y comentarios, que bajan el costo).",
                    ("Ubicalo en un conjunto nuevo de prospección amplia (Público Advantage+) para probarlo con más gente."
                     if prospeccion else "Llevalo también a la campaña de prospección: si funciona en remarketing, "
                     "probalo con público frío."),
                    f"Creá 2 variaciones del mismo concepto en otros formatos (si es {a['formato']}, probá "
                    + ("carrusel e imagen 4:5" if a["formato"] == "video" else "un reel 9:16 de 15 s") + ")."]
            plan.agregar(Accion(prioridad="media", tipo="Duplicar ganador",
                                que="Darle más alcance y crear variaciones de este anuncio.",
                                porque=[f"CPA {fmt.moneda(a['cpa'], mon)}: un {fmt.porcentaje(1 - a['cpa'] / ref, 0)} más barato "
                                        f"que {ref_txt}, con {res(a['resultados'])}."
                                        + (f" CTR {fmt.porcentaje(a['ctr'], 2)}." if a["ctr"] else "")],
                                como=como, impacto="Es el concepto que hoy mejor funciona: replicarlo es la forma más "
                                                   "rápida de bajar el CPA general.",
                                monto=a["gasto"], categoria="escalar", **base_ad(a)))
            acciones_por_anuncio[a["id"]] += 1

        # Fatiga creativa
        if (a["frecuencia"] or 0) > FREC_ANUNCIO_FATIGA and a["gasto"] > act["gasto"] * 0.05 and (a["var_ctr"] or 0) < -0.1:
            plan.agregar(Accion(prioridad="media", tipo="Refrescar creativo (fatiga)",
                                que="Crear una versión nueva del mismo concepto antes de que el CPA se dispare.",
                                porque=[f"Frecuencia {fmt.numero(a['frecuencia'], 1)}: cada persona ya lo vio más de 4 veces, y el "
                                        f"CTR cayó {fmt.variacion(a['var_ctr'])} contra {p.etiqueta_anterior}"
                                        + (f" (y el CPA {fmt.variacion(a['var_cpa'])})." if a["var_cpa"] else ".")],
                                como=[_ruta(a["campana"], a["conjunto"]),
                                      f"Duplicá «{a['nombre']}» y cambiá el gancho/portada y la primera línea del texto "
                                      "(mismo mensaje, otra cara), o pasalo a otro formato (imagen → reel o carrusel).",
                                      "Cuando la versión nueva tenga ~1.000 impresiones con CTR igual o mejor, apagá la original."],
                                impacto="Evita que el costo por resultado siga subiendo por cansancio del público.",
                                monto=a["gasto"], categoria="creativo", **base_ad(a)))
            acciones_por_anuncio[a["id"]] += 1

        # Diagnóstico del creativo para anuncios caros o con poco interés
        if acciones_por_anuncio[a["id"]] == 0 and (a["cpa"] is None or a["cpa"] > 1.15 * ref or (a["ctr"] or 0) < CTR_MIN):
            diag = diagnostico_creativo(a)
            if diag and a["gasto"] > 0.5 * ref:
                tipo, que, porque, como = diag
                if a["cpa"]:
                    porque = porque + [f"Resultado: CPA {fmt.moneda(a['cpa'], mon)} vs {ref_txt}.{comparacion}"]
                plan.agregar(Accion(prioridad="media", tipo=tipo, que=que, porque=porque, como=como,
                                    impacto="Mejorar este paso del embudo baja el CPA del anuncio sin gastar más.",
                                    monto=a["gasto"], categoria="landing" if "destino" in tipo else "creativo",
                                    **base_ad(a)))

    # Reconocimiento: solo creativos (gancho / CTR)
    if not conv:
        for a in activos:
            diag = diagnostico_creativo(a)
            if diag and diag[0] != "Revisar la página de destino":
                tipo, que, porque, como = diag
                plan.agregar(Accion(prioridad="media", tipo=tipo, que=que, porque=porque, como=como,
                                    monto=a["gasto"], categoria="creativo", **base_ad(a)))

    # ------------------------------------------------------------------ CONJUNTOS
    campanas_escaladas = set()
    camp_por_id = {x["id"]: x for x in m["campanas"]}
    conjuntos_por_camp = defaultdict(list)
    for cj in m["conjuntos"]:
        if cj["activo"] and cj["gasto"] > 0:
            conjuntos_por_camp[cj["campana_id"]].append(cj)

    for cj in m["conjuntos"]:
        if not cj["activo"] or cj["gasto"] == 0:
            continue
        camp = camp_por_id.get(cj["campana_id"], {})
        en_campana = cj.get("presupuesto_en_campana")
        ppto = camp.get("presupuesto") if en_campana else cj["presupuesto"]
        tipo_ppto = camp.get("tipo_presupuesto") if en_campana else cj["tipo_presupuesto"]
        donde_ppto = (f"el presupuesto de la campaña «{cj['campana']}» (está en presupuesto de campaña / Advantage+)"
                      if en_campana else f"el presupuesto del conjunto «{cj['nombre']}»")
        base = dict(nivel="campaña" if en_campana else "conjunto", campana=cj["campana"],
                    conjunto=None if en_campana else cj["nombre"], campana_id=cj["campana_id"],
                    conjunto_id=None if en_campana else cj["id"])
        ids_cj = dict(campana_id=cj["campana_id"], conjunto_id=cj["id"])
        gasto_dia = cj["gasto"] / p.dias

        if conv and ref:
            # Subir presupuesto
            if (cj["resultados"] >= (5 if p.tipo == "semanal" else 15) and cj["cpa"] < 0.8 * ref
                    and (cj["frecuencia"] or 0) < frec_lim and not (en_campana and cj["campana_id"] in campanas_escaladas)):
                nuevo = (ppto or gasto_dia) * (1 + SUBA_PRESUPUESTO)
                extra = (nuevo - (ppto or gasto_dia)) * p.dias / (cj["cpa"] * 1.1)
                monto_txt = (f"de {fmt.moneda(ppto, mon)} a {fmt.moneda(nuevo, mon)} "
                             + ("diarios" if tipo_ppto == "diario" else "(presupuesto total)")) if ppto else \
                            f"un 20 % (hoy gasta ~{fmt.moneda(gasto_dia, mon)} por día → ~{fmt.moneda(nuevo, mon)})"
                aprendiendo = cj.get("aprendizaje") == "LEARNING"
                plan.agregar(Accion(
                    prioridad="alta", tipo="Subir presupuesto", categoria="presupuesto",
                    que=f"Subir {donde_ppto} {monto_txt}.",
                    porque=[f"CPA {fmt.moneda(cj['cpa'], mon)}, un {fmt.porcentaje(1 - cj['cpa'] / ref, 0)} por debajo de {ref_txt}, "
                            f"con {res(cj['resultados'])} y frecuencia {fmt.numero(cj['frecuencia'], 1)} "
                            "(todavía hay público por alcanzar)."]
                           + (["Está en fase de aprendizaje: esperá a que salga antes de tocarlo."] if aprendiendo else []),
                    como=[_ruta(cj["campana"], None if en_campana else cj["nombre"],
                                "Campañas" if en_campana else "Conjuntos de anuncios"),
                          f"Tocá «Editar» → Presupuesto → {monto_txt}.",
                          f"Repetí la suba de 15-20 % cada 3-4 días mientras el CPA siga por debajo de {fmt.moneda(ref, mon)}. "
                          "Subas mayores al 20 % reinician la fase de aprendizaje.",
                          "Si después de 3 días el CPA sube más de 20 %, volvé al presupuesto anterior."],
                    impacto=f"≈{res(extra)} más {por_periodo} si el CPA se mantiene (al escalar suele subir 5-15 %).",
                    monto=cj["gasto"], **base))
                if en_campana:
                    campanas_escaladas.add(cj["campana_id"])
                continue

            # Pausar conjunto
            if (cj["gasto"] > 3 * ref and cj["resultados"] == 0) or (cj["resultados"] and cj["cpa"] > 2.5 * ref and cj["gasto"] > 4 * ref):
                if len(conjuntos_por_camp[cj["campana_id"]]) > 1:
                    plan.agregar(Accion(
                        prioridad="alta", tipo="Pausar conjunto", categoria="pausar",
                        que="Apagar el conjunto completo: ningún anuncio logra resultados con este público.",
                        porque=[f"Gastó {fmt.moneda(cj['gasto'], mon)} con {res(cj['resultados'])}"
                                + (f" (CPA {fmt.moneda(cj['cpa'], mon)}, {fmt.numero(cj['cpa'] / ref, 1)}× {ref_txt})." if cj["resultados"] else ".")
                                + f" CPM {fmt.moneda(cj['cpm'], mon)} y CTR {fmt.porcentaje(cj['ctr'], 2)}."],
                        como=[_ruta(cj["campana"], pestana="Conjuntos de anuncios"),
                              f"Desactivá el interruptor de «{cj['nombre']}».",
                              "Si tenía presupuesto propio, sumá ese monto al conjunto con mejor CPA de la campaña "
                              "(en pasos de hasta 20 %)."],
                        impacto=f"Libera ~{fmt.moneda(cj['gasto'], mon)} {por_periodo}.",
                        monto=cj["gasto"], nivel="conjunto", campana=cj["campana"], conjunto=cj["nombre"], **ids_cj))
                    continue

            # Bajar presupuesto
            if cj["resultados"] and 1.3 * ref < cj["cpa"] <= 2.5 * ref and cj["gasto"] > 2 * ref and not en_campana:
                nuevo = (ppto or gasto_dia) * 0.75
                plan.agregar(Accion(
                    prioridad="media", tipo="Bajar presupuesto", categoria="presupuesto",
                    que=f"Bajar el presupuesto del conjunto un 25 %"
                        + (f" (de {fmt.moneda(ppto, mon)} a {fmt.moneda(nuevo, mon)})." if ppto else "."),
                    porque=[f"CPA {fmt.moneda(cj['cpa'], mon)}: {fmt.porcentaje(cj['cpa'] / ref - 1, 0)} por encima {ref_del}, "
                            f"con {fmt.moneda(cj['gasto'], mon)} invertidos."],
                    como=[_ruta(cj["campana"], pestana="Conjuntos de anuncios"),
                          f"Editá «{cj['nombre']}» → Presupuesto"
                          + (f" → {fmt.moneda(nuevo, mon)}." if ppto else " → bajalo 25 %."),
                          "Mientras tanto, aplicá los cambios de creativos sugeridos para sus anuncios."],
                    impacto=f"Ahorra ~{fmt.moneda(cj['gasto'] * 0.25, mon)} {por_periodo} mientras se corrige.",
                    monto=cj["gasto"], nivel="conjunto", campana=cj["campana"], conjunto=cj["nombre"], **ids_cj))

        # Ampliar audiencia (frecuencia alta)
        if (cj["frecuencia"] or 0) > frec_lim and ((cj["var_cpm"] or 0) > 0.1 or (cj["var_cpa"] or 0) > 0.1
                                                   or (ref and cj["cpa"] and cj["cpa"] > ref)):
            rmk = _es_rmk(cj["nombre"]) or _es_rmk(cj["campana"])
            como = ([_ruta(cj["campana"], pestana="Conjuntos de anuncios"),
                     f"Editá «{cj['nombre']}» → Público: ampliá la ventana de visitantes/interacciones de 30 a 60-90 días "
                     "y sumá las personas que interactuaron con Instagram y Facebook.",
                     "Si la frecuencia sigue por encima de 5, bajá el presupuesto del conjunto un 20-30 %: el público es chico."]
                    if rmk else
                    [_ruta(cj["campana"], pestana="Conjuntos de anuncios"),
                     f"Editá «{cj['nombre']}» → Público: activá «Público Advantage+» o ampliá el lookalike de 1 % a 3-5 %.",
                     "Sacá intereses que se superponen y abrí la edad todo lo que el producto permita.",
                     "Excluí a quienes ya compraron en los últimos 30-60 días."])
            plan.agregar(Accion(
                prioridad="media", tipo="Ampliar audiencia", categoria="audiencia",
                que="Ampliar el público: se está mostrando siempre a las mismas personas.",
                porque=[f"Frecuencia {fmt.numero(cj['frecuencia'], 1)} en el período (límite sano: {fmt.numero(frec_lim, 1)})"
                        + (f"; CPM {fmt.variacion(cj['var_cpm'])}" if cj["var_cpm"] else "")
                        + (f"; CPA {fmt.variacion(cj['var_cpa'])} vs {p.etiqueta_anterior}" if cj["var_cpa"] else "") + "."],
                como=como, impacto="Baja la frecuencia y el CPM, y frena la suba del CPA.",
                monto=cj["gasto"], nivel="conjunto", campana=cj["campana"], conjunto=cj["nombre"], **ids_cj))

        # Pocos creativos
        if cj["anuncios_activos"] < 3 and cj["gasto"] > act["gasto"] * 0.08:
            plan.agregar(Accion(
                prioridad="baja", tipo="Agregar creativos", categoria="creativo",
                que=f"Sumar {3 - cj['anuncios_activos'] + 1} creativos nuevos al conjunto.",
                porque=[f"Tiene solo {cj['anuncios_activos']} anuncio(s) activo(s). Meta necesita 3-5 opciones por conjunto "
                        "para encontrar la combinación más barata, y sin variedad la fatiga llega antes."],
                como=[_ruta(cj["campana"], cj["nombre"]),
                      "Creá anuncios nuevos con ángulos distintos: (1) beneficio principal, (2) testimonio/UGC, (3) oferta o urgencia."
                      + (f" El formato que mejor convierte en esta cuenta es {mejor_formato}." if mejor_formato else "")],
                impacto="Más opciones para que Meta optimice y menos fatiga creativa.",
                monto=cj["gasto"] * 0.1, nivel="conjunto", campana=cj["campana"], conjunto=cj["nombre"], **ids_cj))

        if cj.get("aprendizaje") == "FAIL":
            plan.agregar(Accion(
                prioridad="media", tipo="Salir de aprendizaje limitado", categoria="estructura",
                que="El conjunto quedó en «Aprendizaje limitado»: darle más volumen de conversiones.",
                porque=[f"Meta necesita ~50 {plur} por semana por conjunto para optimizar; este consiguió "
                        f"{fmt.numero(cj['resultados'])} en {p.dias} días."],
                como=[_ruta(cj["campana"], pestana="Conjuntos de anuncios"),
                      "Opciones (en orden): unificarlo con otro conjunto similar; ampliar el público; o, si nada de eso alcanza, "
                      "optimizar por un evento anterior del embudo (ej. agregar al carrito en vez de compra)."],
                impacto="Salir del aprendizaje limitado estabiliza la entrega y suele bajar el CPA.",
                monto=cj["gasto"], nivel="conjunto", campana=cj["campana"], conjunto=cj["nombre"], **ids_cj))

    # ------------------------------------------------------------------ CAMPAÑAS
    if conv and ref:
        con_datos = [x for x in m["campanas"] if x["resultados"] >= 2 and x["participacion"] and x["participacion"] > 0.1
                     and x.get("estado") in (None, "ACTIVE")]
        if len(con_datos) >= 2:
            mejor = min(con_datos, key=lambda x: x["cpa"])
            peor = max(con_datos, key=lambda x: x["cpa"])
            if peor["cpa"] > 1.4 * mejor["cpa"] and peor["cpa"] > ref:
                mover = (peor["presupuesto"] if peor.get("presupuesto") and peor.get("tipo_presupuesto") == "diario"
                         else peor["gasto"] / p.dias) * 0.2
                extra = mover * p.dias / mejor["cpa"] - mover * p.dias / peor["cpa"]
                pasos = ["Administrador de anuncios → pestaña Campañas.",
                         f"En «{peor['nombre']}» bajá el presupuesto diario en {fmt.moneda(mover, mon)}"
                         + (f" (de {fmt.moneda(peor['presupuesto'], mon)} a {fmt.moneda(peor['presupuesto'] - mover, mon)})."
                            if peor.get("presupuesto") else " (bajando los conjuntos con peor CPA)."),
                         f"En «{mejor['nombre']}» subilo en el mismo monto"
                         + (f" (de {fmt.moneda(mejor['presupuesto'], mon)} a {fmt.moneda(mejor['presupuesto'] + mover, mon)})."
                            if mejor.get("presupuesto") else " (en el conjunto con mejor CPA)."),
                         "Hacé los dos cambios el mismo día y no toques nada más por 3-4 días."]
                plan.agregar(Accion(
                    prioridad="alta", tipo="Mover presupuesto entre campañas", categoria="presupuesto",
                    nivel="campaña", campana=f"{peor['nombre']} → {mejor['nombre']}",
                    que=f"Pasar ~{fmt.moneda(mover, mon)} por día de «{peor['nombre']}» a «{mejor['nombre']}».",
                    porque=[f"«{mejor['nombre']}» consigue {plur} a {fmt.moneda(mejor['cpa'], mon)} y «{peor['nombre']}» a "
                            f"{fmt.moneda(peor['cpa'], mon)} ({fmt.numero(peor['cpa'] / mejor['cpa'], 1)} veces más caro). "
                            "Con la misma inversión total se consiguen más resultados."],
                    como=pasos,
                    impacto=f"≈{res(max(extra, 0))} más {por_periodo} con la misma inversión.",
                    campana_id=peor["id"], monto=mover * p.dias))

        for camp_id, cjs in conjuntos_por_camp.items():
            chicos = [x for x in cjs if x["resultados"] < limite_aprendizaje * 0.3]
            if len(cjs) >= 3 and len(chicos) >= 3:
                campana = camp_por_id.get(camp_id, {}).get("nombre", cjs[0]["campana"])
                base_cj = min((x for x in cjs if x["resultados"]), key=lambda x: x["cpa"], default=cjs[0])
                plan.agregar(Accion(
                    prioridad="baja", tipo="Unificar conjuntos", categoria="estructura", nivel="campaña", campana=campana,
                    que=f"Unificar los {len(cjs)} conjuntos en 1 o 2 para salir de la fase de aprendizaje.",
                    porque=[f"{len(chicos)} conjuntos tienen menos de {fmt.numero(limite_aprendizaje * 0.3)} {plur} en el período. "
                            "Con el presupuesto repartido, ninguno junta las ~50 conversiones semanales que Meta necesita."],
                    como=[_ruta(campana, pestana="Conjuntos de anuncios"),
                          f"Usá «{base_cj['nombre']}» como base (es el de mejor CPA).",
                          "Duplicá a ese conjunto los 3-5 mejores anuncios de los demás (Duplicar → conjunto existente).",
                          "Apagá los otros conjuntos y pasá su presupuesto al que queda, o activá el presupuesto de campaña Advantage+."],
                    impacto="Más conversiones por conjunto: el algoritmo optimiza mejor y el CPA suele bajar entre 10 y 25 %.",
                    campana_id=camp_id, monto=sum(x["gasto"] for x in cjs) * 0.2))

        # Campañas cuyo CPA subió fuerte: explicar la causa
        for x in m["campanas"]:
            if (x.get("var_cpa") or 0) > 0.25 and (x["participacion"] or 0) > 0.15 and x["resultados"]:
                causas, pasos = [], []
                if (x.get("var_cpm") or 0) > 0.15:
                    causas.append(f"CPM {fmt.variacion(x['var_cpm'])} (cuesta más mostrar los anuncios)")
                    pasos.append("CPM: revisá la frecuencia de los conjuntos y ampliá públicos; evitá conjuntos que compitan entre sí por la misma gente.")
                if (x.get("var_ctr") or 0) < -0.15:
                    causas.append(f"CTR {fmt.variacion(x['var_ctr'])} (los anuncios interesan menos)")
                    pasos.append("CTR: renová los creativos marcados con fatiga o con CTR bajo (ver acciones de anuncios).")
                if (x.get("var_tasa_conversion") or 0) < -0.15:
                    causas.append(f"tasa de conversión {fmt.variacion(x['var_tasa_conversion'])} (los clics convierten menos)")
                    pasos.append("Conversión: revisá la web o el checkout (cambios de precio, stock, envío, medios de pago, velocidad).")
                if not causas:
                    continue
                plan.agregar(Accion(
                    prioridad="media", tipo="Corregir suba de CPA", categoria="estructura", nivel="campaña",
                    campana=x["nombre"],
                    que="Atacar la causa de la suba del costo por resultado.",
                    porque=[f"El CPA pasó a {fmt.moneda(x['cpa'], mon)} ({fmt.variacion(x['var_cpa'])} vs {p.etiqueta_anterior}). "
                            "Causa: " + "; ".join(causas) + "."],
                    como=pasos, campana_id=x["id"], monto=x["gasto"],
                    impacto="Corregir la causa principal devuelve el CPA a su nivel anterior."))

    _depurar(plan, conjuntos_por_camp, camp_por_id, mon, por_periodo)
    plan.acciones.sort(key=lambda a: (PRIORIDAD_ORDEN[a.prioridad], -a.monto))
    return plan


def _depurar(plan: Plan, conjuntos_por_camp: dict, camp_por_id: dict, mon: str, por_periodo: str):
    """Evita recomendaciones contradictorias o repetidas."""
    acc = plan.acciones
    cj_pausados = {a.conjunto_id for a in acc if a.tipo == "Pausar conjunto"}

    # Si se pausarían todos los conjuntos activos de una campaña → pausar la campaña entera
    for camp_id, cjs in conjuntos_por_camp.items():
        if cjs and all(cj["id"] in cj_pausados for cj in cjs):
            camp = camp_por_id.get(camp_id, {})
            nombre = camp.get("nombre", cjs[0]["campana"])
            gasto = sum(cj["gasto"] for cj in cjs)
            motivos = [x.porque[0] for x in acc if x.tipo == "Pausar conjunto" and x.campana_id == camp_id]
            acc[:] = [x for x in acc if x.campana_id != camp_id]
            acc.append(Accion(
                prioridad="alta", tipo="Pausar campaña", categoria="pausar", nivel="campaña", campana=nombre,
                campana_id=camp_id,
                que="Apagar la campaña completa y pasar su presupuesto a la campaña con mejor costo por resultado.",
                porque=[f"Ninguno de sus {len(cjs)} conjuntos llega a un costo aceptable:"] + [f"• {m}" for m in motivos],
                como=["Administrador de anuncios → pestaña Campañas.", f"Desactivá el interruptor de «{nombre}».",
                      "Sumá su presupuesto diario a la campaña con mejor CPA en pasos de hasta 20 % cada 3-4 días.",
                      "Antes de relanzarla, cambiá la oferta, el público o los creativos: no la reactives igual."],
                impacto=f"Libera ~{fmt.moneda(gasto, mon)} {por_periodo}.", monto=gasto))
            cj_pausados -= {cj["id"] for cj in cjs}

    # Nada que hacer sobre anuncios o ajustes de un conjunto que se pausa
    acc[:] = [x for x in acc if not (x.conjunto_id in cj_pausados and x.tipo != "Pausar conjunto")]

    # No proponer unificar conjuntos en una campaña donde ya se pausan conjuntos
    camp_con_pausa = {x.campana_id for x in acc if x.tipo == "Pausar conjunto"}
    acc[:] = [x for x in acc if not (x.tipo == "Unificar conjuntos" and x.campana_id in camp_con_pausa)]

    # "Agregar creativos" sobra si ya se pide reemplazar un anuncio en ese conjunto
    con_reemplazo = {x.conjunto_id for x in acc if x.tipo == "Reemplazar anuncio"}
    acc[:] = [x for x in acc if not (x.tipo == "Agregar creativos" and x.conjunto_id in con_reemplazo)]

    # Máximo 3 "Duplicar ganador" (los de mayor inversión)
    ganadores = sorted((x for x in acc if x.tipo == "Duplicar ganador"), key=lambda x: -x.monto)
    for x in ganadores[3:]:
        acc.remove(x)
