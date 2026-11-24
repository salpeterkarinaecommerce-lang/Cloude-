"""Datos de prueba con el mismo formato que devuelve Meta, para probar sin token."""
from __future__ import annotations

import random
from datetime import datetime, time, timedelta

from .config import Cliente
from .periodos import Periodo

ACCION = {"ventas": "omni_purchase", "leads": "lead",
          "mensajes": "onsite_conversion.messaging_conversation_started_7d",
          "trafico": "landing_page_view", "reconocimiento": None}

NOMBRES_CAMP = ["Prospección · Intereses", "Remarketing · Visitantes 30d", "Advantage+ · Catálogo",
                "Lookalike 1% · Compradores", "Video · Reconocimiento"]
NOMBRES_AD = ["Video testimonio", "Carrusel productos", "Imagen promo 20% OFF", "Reel UGC",
              "Imagen beneficio envío gratis", "Video unboxing", "Estático precio", "Story oferta"]


def _fila(r: random.Random, gasto, cpm, ctr, conv_rate, accion, ticket, extra=None):
    imp = max(1, int(gasto / cpm * 1000))
    frec = r.uniform(1.3, 3.8)
    reach = int(imp / frec)
    link = int(imp * ctr)
    clicks = int(link * r.uniform(1.4, 2.0))
    conv = int(link * conv_rate) if accion else 0
    fila = {
        "spend": f"{gasto:.2f}", "impressions": str(imp), "reach": str(reach),
        "frequency": f"{imp / max(reach, 1):.4f}", "clicks": str(clicks),
        "inline_link_clicks": str(link), "ctr": f"{clicks / imp * 100:.4f}",
        "inline_link_click_ctr": f"{link / imp * 100:.4f}",
        "cpc": f"{gasto / max(clicks, 1):.4f}", "cpm": f"{gasto / imp * 1000:.4f}",
        "actions": [{"action_type": "link_click", "value": str(link)},
                    {"action_type": "landing_page_view", "value": str(int(link * 0.75))}],
        "action_values": [],
    }
    if accion and accion != "landing_page_view":
        fila["actions"].append({"action_type": accion, "value": str(conv)})
        if accion == "omni_purchase":
            fila["actions"].append({"action_type": "add_to_cart", "value": str(conv * 4)})
            fila["action_values"].append({"action_type": accion,
                                          "value": f"{conv * ticket * r.uniform(0.85, 1.15):.2f}"})
    fila.update(extra or {})
    return fila


def _sumar(filas):
    num = ["spend", "impressions", "reach", "clicks", "inline_link_clicks"]
    t = {k: sum(float(f[k]) for f in filas) for k in num}
    acc, val = {}, {}
    for f in filas:
        for a in f["actions"]:
            acc[a["action_type"]] = acc.get(a["action_type"], 0) + float(a["value"])
        for a in f["action_values"]:
            val[a["action_type"]] = val.get(a["action_type"], 0) + float(a["value"])
    reach = t["reach"] * 0.8  # alcance no es aditivo
    return {
        "spend": f"{t['spend']:.2f}", "impressions": str(int(t["impressions"])), "reach": str(int(reach)),
        "frequency": f"{t['impressions'] / reach:.4f}", "clicks": str(int(t["clicks"])),
        "inline_link_clicks": str(int(t["inline_link_clicks"])),
        "ctr": f"{t['clicks'] / t['impressions'] * 100:.4f}",
        "inline_link_click_ctr": f"{t['inline_link_clicks'] / t['impressions'] * 100:.4f}",
        "cpc": f"{t['spend'] / max(t['clicks'], 1):.4f}", "cpm": f"{t['spend'] / t['impressions'] * 1000:.4f}",
        "actions": [{"action_type": k, "value": str(int(v))} for k, v in acc.items()],
        "action_values": [{"action_type": k, "value": f"{v:.2f}"} for k, v in val.items()],
    }


def _ads(cliente: Cliente, p: Periodo, r: random.Random) -> dict:
    accion = ACCION[cliente.objetivo]
    ticket = cliente.ticket_promedio or 25000
    presupuesto = cliente.presupuesto_mensual or 1_500_000
    gasto_periodo = presupuesto / 30 * p.dias * r.uniform(0.85, 1.1)
    conv_base = {"ventas": 0.022, "leads": 0.09, "mensajes": 0.16, "trafico": 0, "reconocimiento": 0}[cliente.objetivo]
    cpm_base = r.uniform(2500, 5500) if cliente.moneda == "ARS" else r.uniform(4, 12)
    div = 100  # presupuestos en centavos, como los devuelve Meta
    textos = ["Nueva colección disponible. Conocé todos los modelos en nuestra web.",
              "🔥 20% OFF solo por esta semana + envío gratis desde $60.000",
              "Lo que dicen nuestras clientas ⭐⭐⭐⭐⭐", "Hasta 6 cuotas sin interés. Comprá online."]
    n_camp = r.randint(3, 4)
    estructura = []  # (camp_idx, nombre, [(cj_idx, nombre_cj, [ad_idx...])])
    k = 0
    for i in range(n_camp):
        cjs = []
        for j in range(r.choice([1, 1, 2, 3])):
            ads_cj = list(range(k, k + r.randint(1, 4)))
            k += len(ads_cj)
            cjs.append((j, ["Conjunto A", "Conjunto B · Intereses", "Conjunto C · Lookalike"][j], ads_cj))
        estructura.append((i, NOMBRES_CAMP[i], cjs))
    calidad_ad = {a: r.uniform(0.2, 1.8) for a in range(k)}
    calidad_camp = {i: r.uniform(0.5, 1.5) * (1.4 if "Remarketing" in NOMBRES_CAMP[i] else 1) for i in range(n_camp)}
    pesos_camp = {i: r.uniform(0.5, 3) for i in range(n_camp)}
    hook = {a: r.uniform(0.12, 0.42) for a in range(k)}

    def generar_periodo(factor, fatiga=0.0):
        campanas, conjuntos, anuncios = [], [], []
        for i, nombre, cjs in estructura:
            g_camp = gasto_periodo * factor * pesos_camp[i] / sum(pesos_camp.values())
            filas_camp = []
            pesos_cj = [0.5 + (hash((i, j)) % 100) / 60 for j, _, _ in cjs]
            for j, nombre_cj, ids in cjs:
                g_cj = g_camp * pesos_cj[j] / sum(pesos_cj)
                pesos_ad = {a: r.uniform(0.3, 3) for a in ids}
                filas_cj = []
                for a in ids:
                    ga = g_cj * pesos_ad[a] / sum(pesos_ad.values())
                    q = calidad_camp[i] * calidad_ad[a] * (1 - fatiga * r.random())
                    ad_name = NOMBRES_AD[a % len(NOMBRES_AD)]
                    formato = ("video" if any(x in ad_name.lower() for x in ("video", "reel", "story"))
                               else "carrusel" if "carrusel" in ad_name.lower() else "imagen")
                    fila = _fila(r, ga, cpm_base * r.uniform(0.8, 1.4), 0.011 * q ** 0.5, conv_base * q, accion, ticket, {
                        "ad_id": str(a), "ad_name": ad_name, "adset_id": f"{i}-{j}",
                        "adset_name": f"{nombre} · {nombre_cj}", "campaign_id": str(i), "campaign_name": nombre,
                        "miniatura": None, "formato": formato})
                    if formato == "video":
                        v3 = int(float(fila["impressions"]) * hook[a])
                        fila["actions"].append({"action_type": "video_view", "value": str(v3)})
                        fila["video_thruplay_watched_actions"] = [{"action_type": "video_view",
                                                                   "value": str(int(v3 * r.uniform(0.08, 0.35)))}]
                    if r.random() < 0.18:
                        fila["frequency"] = f"{r.uniform(4.2, 6):.4f}"
                    filas_cj.append(fila)
                anuncios.extend(filas_cj)
                fcj = _sumar(filas_cj)
                fcj.update({"adset_id": f"{i}-{j}", "adset_name": f"{nombre} · {nombre_cj}",
                            "campaign_id": str(i), "campaign_name": nombre})
                if any(float(x["frequency"]) > 4 for x in filas_cj):
                    fcj["frequency"] = f"{r.uniform(3.6, 5):.4f}"
                conjuntos.append(fcj)
                filas_camp.extend(filas_cj)
            fila = _sumar(filas_camp)
            fila.update({"campaign_id": str(i), "campaign_name": nombre,
                         "objective": "OUTCOME_SALES" if cliente.objetivo == "ventas" else "OUTCOME_LEADS"})
            campanas.append(fila)
        return campanas, conjuntos, anuncios

    camp_prev, cj_prev, ads_prev = generar_periodo(r.uniform(0.8, 1.15))
    camp, cjs, ads = generar_periodo(1.0, fatiga=0.35)
    tot = _sumar(camp)
    diario = []
    for d in range(p.dias):
        dia = p.desde + timedelta(days=d)
        f = _fila(r, float(tot["spend"]) / p.dias * r.uniform(0.7, 1.3),
                  cpm_base * r.uniform(0.85, 1.2), 0.011 * r.uniform(0.8, 1.2),
                  conv_base * r.uniform(0.6, 1.4), accion, ticket)
        f["date_start"] = f["date_stop"] = dia.isoformat()
        diario.append(f)

    objetos = {"campanas": {}, "conjuntos": {}, "anuncios": {}}
    for i, nombre, estructura_cj in estructura:
        cbo = i == 2  # una campaña con presupuesto de campaña (Advantage+)
        gasto_dia = sum(float(c["spend"]) for c in camp if c["campaign_id"] == str(i)) / p.dias
        objetos["campanas"][str(i)] = {"id": str(i), "name": nombre, "effective_status": "ACTIVE",
                                      **({"daily_budget": str(int(gasto_dia * 1.05 * div))} if cbo else {})}
        for j, nombre_cj, ids in estructura_cj:
            g = sum(float(c["spend"]) for c in cjs if c["adset_id"] == f"{i}-{j}") / p.dias
            objetos["conjuntos"][f"{i}-{j}"] = {
                "id": f"{i}-{j}", "name": nombre_cj, "effective_status": "ACTIVE",
                **({} if cbo else {"daily_budget": str(int(round(g * 1.05 / 500) * 500 * div))}),
                "learning_stage_info": {"status": r.choice(["SUCCESS", "SUCCESS", "LEARNING", "FAIL"])}}
            for a in ids:
                objetos["anuncios"][str(a)] = {"id": str(a), "effective_status": "ACTIVE", "creative": {
                    "body": r.choice(textos), "call_to_action_type": r.choice(["SHOP_NOW", "LEARN_MORE"])}}
    return {"cuenta": {"name": f"{cliente.nombre} · Cuenta publicitaria", "currency": cliente.moneda},
            "objetos": objetos,
            "actual": {"totales": tot, "campanas": camp, "conjuntos": cjs, "anuncios": ads, "diario": diario},
            "anterior": {"totales": _sumar(camp_prev), "campanas": camp_prev, "conjuntos": cj_prev, "anuncios": ads_prev}}


def _posts(p: Periodo, r: random.Random, red: str, seguidores: int) -> list[dict]:
    n = r.randint(2, 5) * max(1, p.dias // 7)
    tipos = ["REELS", "CAROUSEL", "FEED"] if red == "ig" else ["video", "added_photos", "shared_story"]
    textos = ["Nuevo ingreso de temporada ✨", "¿Cuál es tu favorito? Contanos 👇", "Detrás de escena del equipo",
              "3 tips para elegir el ideal", "Promo de fin de semana 🔥", "Lo que dicen nuestros clientes",
              "Así lo usamos nosotros", "Sorteo: participá y ganá"]
    posts = []
    for i in range(n):
        tipo = r.choice(tipos)
        boost = 2.4 if tipo in ("REELS", "video") else (1.4 if tipo == "CAROUSEL" else 1)
        alcance = int(seguidores * r.uniform(0.08, 0.35) * boost)
        fecha = datetime.combine(p.desde + timedelta(days=r.randrange(p.dias)), time(r.choice([9, 12, 13, 18, 19, 20, 21])))
        mg, com = int(alcance * r.uniform(0.02, 0.07)), int(alcance * r.uniform(0.001, 0.008))
        gu, comp = int(alcance * r.uniform(0.002, 0.015)), int(alcance * r.uniform(0.001, 0.01))
        base = {"id": f"{red}{i}", "texto": r.choice(textos), "fecha": fecha.isoformat() + "+0000",
                "tipo": tipo, "link": "https://www.instagram.com/" if red == "ig" else "https://www.facebook.com/",
                "imagen": None, "comentarios": com, "compartidos": comp}
        if red == "ig":
            base.update({"me_gusta": mg, "guardados": gu, "alcance": alcance,
                         "vistas": int(alcance * r.uniform(1.2, 2.5)), "interacciones": mg + com + gu + comp})
        else:
            base.update({"reacciones": mg, "interacciones": mg + com + comp})
        posts.append(base)
    return posts


def _organico(p: Periodo, r: random.Random, red: str, nombre: str, factor=1.0, posts=True) -> dict:
    seg = r.randint(4000, 25000) if red == "ig" else r.randint(2000, 15000)
    pubs = _posts(p, r, red, seg) if posts else []
    alcance = int(seg * r.uniform(0.6, 1.8) * p.dias / 7 * factor)
    inter = sum(x["interacciones"] for x in pubs) or int(alcance * 0.04)
    d = {"seguidores": seg, "alcance": alcance, "vistas": int(alcance * r.uniform(1.8, 3)),
         "interacciones": inter, "nuevos_seguidores": int(seg * r.uniform(0.002, 0.02) * p.dias / 7 * factor),
         "publicaciones": pubs}
    if red == "ig":
        d.update({"usuario": nombre.lower().replace(" ", ""), "cuentas_interactuaron": int(inter * 0.6),
                  "visitas_perfil": int(alcance * r.uniform(0.02, 0.06))})
    else:
        d["nombre"] = nombre
    return d


def generar(cliente: Cliente, p: Periodo) -> dict:
    r = random.Random(f"{cliente.slug}-{p.clave}")
    datos = {"ads": None, "facebook": None, "instagram": None,
             "avisos": ["Reporte generado con DATOS DE PRUEBA (modo demo)."]}
    if cliente.tiene_ads:
        datos["ads"] = _ads(cliente, p, r)
    for red, clave, activo in (("fb", "facebook", cliente.page_id), ("ig", "instagram", cliente.instagram_id)):
        if activo:
            act = _organico(p, r, red, cliente.nombre)
            prev = _organico(p, r, red, cliente.nombre, r.uniform(0.75, 1.2), posts=False)
            prev["seguidores"] = act["seguidores"] - act["nuevos_seguidores"]
            datos[clave] = {"actual": act, "anterior": prev}
    return datos
