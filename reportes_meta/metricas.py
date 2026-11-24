"""Normaliza las respuestas de Meta y calcula los KPIs y las variaciones contra el período anterior."""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Cliente

# Prioridad de tipos de acción por objetivo (se toma el primero disponible para no contar doble).
ACCIONES = {
    "ventas": ["omni_purchase", "purchase", "offsite_conversion.fb_pixel_purchase",
               "onsite_web_purchase", "onsite_conversion.purchase"],
    "leads": ["lead", "onsite_conversion.lead_grouped", "offsite_conversion.fb_pixel_lead",
              "leadgen_grouped", "onsite_conversion.lead"],
    "mensajes": ["onsite_conversion.messaging_conversation_started_7d",
                 "onsite_conversion.total_messaging_connection"],
    "trafico": ["landing_page_view", "link_click"],
    "reconocimiento": [],
}
ZONA = ZoneInfo(os.environ.get("ZONA_HORARIA", "America/Argentina/Buenos_Aires"))

NOMBRE_RESULTADO = {"ventas": ("venta", "ventas"), "leads": ("contacto", "contactos"),
                    "mensajes": ("conversación", "conversaciones"),
                    "trafico": ("visita al sitio", "visitas al sitio"),
                    "reconocimiento": ("persona alcanzada", "personas alcanzadas")}


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _accion(lista, tipos) -> float:
    if not lista:
        return 0.0
    por_tipo = {a.get("action_type"): _f(a.get("value")) for a in lista}
    for t in tipos:
        if t in por_tipo:
            return por_tipo[t]
    return 0.0


def _div(a, b):
    return a / b if b else None


def var(actual, anterior):
    if actual is None or anterior in (None, 0):
        return None
    return (actual - anterior) / anterior


def fila_ads(raw: dict, objetivo: str) -> dict:
    """Convierte una fila de insights de Meta en un dict numérico con KPIs."""
    tipos = ACCIONES[objetivo]
    gasto = _f(raw.get("spend"))
    imp = _f(raw.get("impressions"))
    alcance = _f(raw.get("reach"))
    clics_link = _f(raw.get("inline_link_clicks"))
    clics = _f(raw.get("clicks"))
    if objetivo == "reconocimiento":
        resultados = alcance
    else:
        resultados = _accion(raw.get("actions"), tipos)
    valor = _accion(raw.get("action_values"), ACCIONES["ventas"]) if objetivo == "ventas" else 0.0
    carritos = _accion(raw.get("actions"), ["omni_add_to_cart", "add_to_cart",
                                             "offsite_conversion.fb_pixel_add_to_cart"])
    video_3s = _accion(raw.get("actions"), ["video_view"])
    thruplays = sum(_f(x.get("value")) for x in raw.get("video_thruplay_watched_actions") or [])
    return {
        "gasto": gasto, "impresiones": imp, "alcance": alcance,
        "frecuencia": _f(raw.get("frequency")) or _div(imp, alcance),
        "clics": clics, "clics_link": clics_link,
        "ctr": _div(clics_link, imp),                # CTR de enlace
        "cpc": _div(gasto, clics_link),              # costo por clic en el enlace
        "cpm": _div(gasto * 1000, imp),
        "resultados": resultados,
        "cpa": _div(gasto, resultados) if objetivo != "reconocimiento" else _div(gasto * 1000, alcance),
        "valor": valor, "roas": _div(valor, gasto) if valor else None,
        "tasa_conversion": _div(resultados, clics_link) if objetivo not in ("reconocimiento", "trafico") else None,
        "carritos": carritos,
        # Video: % que pasa los 3 s (gancho) y % de esos que llega a ThruPlay (retención)
        "video_3s": video_3s, "thruplays": thruplays,
        "hook_rate": _div(video_3s, imp) if video_3s else None,
        "hold_rate": _div(thruplays, video_3s) if video_3s and thruplays else None,
    }


# Monedas sin centavos en la API de Meta (los presupuestos vienen en la unidad mínima de la moneda)
SIN_CENTAVOS = {"CLP", "COP", "CRC", "HUF", "ISK", "IDR", "JPY", "KRW", "PYG", "TWD", "VND"}
ACTIVO = {"ACTIVE", "IN_PROCESS", "WITH_ISSUES", None}


def _presupuesto(obj: dict | None, moneda: str):
    """Devuelve (monto_diario, tipo) desde daily_budget / lifetime_budget."""
    if not obj:
        return None, None
    div = 1 if moneda in SIN_CENTAVOS else 100
    if obj.get("daily_budget"):
        return _f(obj["daily_budget"]) / div, "diario"
    if obj.get("lifetime_budget"):
        return _f(obj["lifetime_budget"]) / div, "total"
    return None, None


def _formato(creativo: dict | None, nombre: str) -> str:
    cr = creativo or {}
    t = (cr.get("object_type") or "").upper()
    if cr.get("video_id") or t == "VIDEO":
        return "video"
    if t in ("SHARE", "STATUS") and not cr.get("image_url") and not cr.get("thumbnail_url"):
        return "otro"
    n = nombre.lower()
    if "carrusel" in n or "carousel" in n:
        return "carrusel"
    if any(x in n for x in ("video", "reel", "ugc", "story")):
        return "video"
    return "imagen" if t in ("PHOTO", "SHARE", "") else t.lower()


def calcular_ads(cliente: Cliente, ads: dict) -> dict:
    obj = cliente.objetivo
    mon = cliente.moneda
    objetos = ads.get("objetos") or {"campanas": {}, "conjuntos": {}, "anuncios": {}}
    act = fila_ads(ads["actual"]["totales"], obj)
    prev = fila_ads(ads["anterior"]["totales"], obj)
    variaciones = {k: var(act[k], prev[k]) for k in act}

    def _con_prev(fila_act, fila_prev):
        claves = ("cpa", "ctr", "cpm", "frecuencia", "tasa_conversion", "gasto", "resultados", "hook_rate", "roas")
        return {f"var_{k}": var(fila_act[k], fila_prev[k]) if fila_prev else None for k in claves}

    # ---- Campañas
    prev_camp = {c.get("campaign_id"): fila_ads(c, obj) for c in ads["anterior"]["campanas"]}
    campanas = []
    for c in ads["actual"]["campanas"]:
        m = fila_ads(c, obj)
        cid = c.get("campaign_id")
        o = objetos["campanas"].get(cid, {})
        ppto, tipo_ppto = _presupuesto(o, mon)
        m.update(_con_prev(m, prev_camp.get(cid)))
        m.update({"id": cid, "nombre": c.get("campaign_name", "Sin nombre"), "objetivo_meta": c.get("objective"),
                  "participacion": _div(m["gasto"], act["gasto"]), "estado": o.get("effective_status"),
                  "presupuesto": ppto, "tipo_presupuesto": tipo_ppto, "cbo": ppto is not None})
        campanas.append(m)
    campanas.sort(key=lambda x: x["gasto"], reverse=True)
    camp_por_id = {c["id"]: c for c in campanas}

    # ---- Anuncios
    prev_ads = {a.get("ad_id"): fila_ads(a, obj) for a in ads["anterior"].get("anuncios", [])}
    anuncios = []
    for a in ads["actual"]["anuncios"]:
        m = fila_ads(a, obj)
        aid = a.get("ad_id")
        o = objetos["anuncios"].get(aid, {})
        cr = o.get("creative") or {}
        m.update(_con_prev(m, prev_ads.get(aid)))
        m.update({"id": aid, "nombre": a.get("ad_name", "Sin nombre"),
                  "conjunto": a.get("adset_name"), "conjunto_id": a.get("adset_id"),
                  "campana": a.get("campaign_name"), "campana_id": a.get("campaign_id"),
                  "miniatura": a.get("miniatura") or cr.get("thumbnail_url") or cr.get("image_url"),
                  "estado": o.get("effective_status"), "activo": o.get("effective_status") in ACTIVO,
                  "formato": a.get("formato") or _formato(cr, a.get("ad_name", "")),
                  "titulo": cr.get("title"), "texto": cr.get("body"), "cta": cr.get("call_to_action_type"),
                  "nuevo": aid not in prev_ads})
        anuncios.append(m)
    anuncios.sort(key=lambda x: x["gasto"], reverse=True)

    # ---- Conjuntos
    prev_cj = {c.get("adset_id"): fila_ads(c, obj) for c in ads["anterior"].get("conjuntos", [])}
    filas_cj = ads["actual"].get("conjuntos") or []
    if not filas_cj:  # compatibilidad: reconstruir desde anuncios
        agrup = defaultdict(list)
        for a in ads["actual"]["anuncios"]:
            agrup[(a.get("adset_id"), a.get("adset_name"), a.get("campaign_id"), a.get("campaign_name"))].append(a)
        filas_cj = [{"adset_id": k[0], "adset_name": k[1], "campaign_id": k[2], "campaign_name": k[3],
                     "spend": sum(_f(x.get("spend")) for x in v), "impressions": sum(_f(x.get("impressions")) for x in v),
                     "reach": sum(_f(x.get("reach")) for x in v), "inline_link_clicks": sum(_f(x.get("inline_link_clicks")) for x in v),
                     "actions": [{"action_type": t, "value": sum(_accion(x.get("actions"), [t]) for x in v)}
                                 for t in ACCIONES[obj][:1]]} for k, v in agrup.items()]
    conjuntos = []
    for c in filas_cj:
        m = fila_ads(c, obj)
        sid = c.get("adset_id")
        o = objetos["conjuntos"].get(sid, {})
        ppto, tipo_ppto = _presupuesto(o, mon)
        aprendizaje = (o.get("learning_stage_info") or {}).get("status")
        propios = [x for x in anuncios if x["conjunto_id"] == sid]
        m.update(_con_prev(m, prev_cj.get(sid)))
        m.update({"id": sid, "nombre": c.get("adset_name", "Sin nombre"), "campana": c.get("campaign_name"),
                  "campana_id": c.get("campaign_id"), "estado": o.get("effective_status"),
                  "activo": o.get("effective_status") in ACTIVO,
                  "presupuesto": ppto, "tipo_presupuesto": tipo_ppto, "aprendizaje": aprendizaje,
                  "optimizacion": o.get("optimization_goal"),
                  "anuncios_activos": sum(1 for x in propios if x["activo"] and x["gasto"] > 0),
                  "anuncios": len(propios)})
        if ppto is None and camp_por_id.get(m["campana_id"], {}).get("cbo"):
            m["presupuesto_en_campana"] = True
        conjuntos.append(m)
    conjuntos.sort(key=lambda x: x["gasto"], reverse=True)

    diario = []
    for d in ads["actual"].get("diario", []):
        m = fila_ads(d, obj)
        m["fecha"] = d.get("date_start")
        diario.append(m)

    return {"actual": act, "anterior": prev, "var": variaciones, "campanas": campanas,
            "anuncios": anuncios, "conjuntos": conjuntos, "diario": diario,
            "resultado_singular": NOMBRE_RESULTADO[obj][0], "resultado_plural": NOMBRE_RESULTADO[obj][1],
            "cuenta": ads.get("cuenta", {})}


def _tasa(inter, alcance):
    return _div(inter or 0, alcance) if alcance else None


def calcular_organico(red: str, datos: dict) -> dict:
    act, prev = datos["actual"], datos["anterior"]
    pubs = act.get("publicaciones", [])
    for po in pubs:
        po["tasa"] = _tasa(po.get("interacciones"), po.get("alcance")) if po.get("alcance") else None
        try:
            po["dt"] = datetime.fromisoformat(str(po["fecha"]).replace("+0000", "+00:00")).astimezone(ZONA)
        except (ValueError, KeyError):
            po["dt"] = None
    orden = sorted(pubs, key=lambda x: (x.get("interacciones") or 0), reverse=True)

    por_tipo = defaultdict(lambda: {"cantidad": 0, "interacciones": 0, "alcance": 0})
    for po in pubs:
        t = por_tipo[_tipo_legible(po.get("tipo"))]
        t["cantidad"] += 1
        t["interacciones"] += po.get("interacciones") or 0
        t["alcance"] += po.get("alcance") or 0
    for t in por_tipo.values():
        t["promedio_interacciones"] = t["interacciones"] / t["cantidad"]
        t["promedio_alcance"] = t["alcance"] / t["cantidad"] if t["alcance"] else None

    por_dia = defaultdict(lambda: [0, 0])
    por_hora = defaultdict(lambda: [0, 0])
    for po in pubs:
        if po["dt"]:
            local = po["dt"]
            por_dia[local.weekday()][0] += po.get("interacciones") or 0
            por_dia[local.weekday()][1] += 1
            por_hora[local.hour][0] += po.get("interacciones") or 0
            por_hora[local.hour][1] += 1

    claves = ["seguidores", "alcance", "vistas", "interacciones", "nuevos_seguidores",
              "cuentas_interactuaron", "visitas_perfil"]
    res = {k: act.get(k) for k in claves}
    res["engagement"] = _tasa(act.get("interacciones"), act.get("alcance"))
    prev_eng = _tasa(prev.get("interacciones"), prev.get("alcance"))
    res["var"] = {k: var(act.get(k), prev.get(k)) for k in claves}
    res["var"]["engagement"] = var(res["engagement"], prev_eng)
    res.update({
        "red": red, "nombre": act.get("nombre") or ("@" + act["usuario"] if act.get("usuario") else red),
        "cantidad_publicaciones": len(pubs), "top": orden[:3], "peores": orden[-2:] if len(orden) > 4 else [],
        "por_tipo": dict(por_tipo),
        "por_dia": {d: v[0] / v[1] for d, v in por_dia.items()},
        "por_hora": {h: v[0] / v[1] for h, v in por_hora.items()},
    })
    return res


def _tipo_legible(t) -> str:
    t = (t or "").upper()
    return {"REELS": "Reels", "VIDEO": "Videos", "CAROUSEL": "Carruseles", "CAROUSEL_ALBUM": "Carruseles",
            "FEED": "Fotos", "IMAGE": "Fotos", "ADDED_PHOTOS": "Fotos", "ADDED_VIDEO": "Videos",
            "SHARED_STORY": "Compartidos", "MOBILE_STATUS_UPDATE": "Textos", "STORY": "Historias"}.get(t, "Otros")


def calcular(cliente: Cliente, datos: dict) -> dict:
    return {
        "ads": calcular_ads(cliente, datos["ads"]) if datos.get("ads") and datos["ads"]["actual"]["totales"] else None,
        "facebook": calcular_organico("facebook", datos["facebook"]) if datos.get("facebook") else None,
        "instagram": calcular_organico("instagram", datos["instagram"]) if datos.get("instagram") else None,
        "avisos": datos.get("avisos", []),
    }
