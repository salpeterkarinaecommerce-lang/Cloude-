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

    def generar_periodo(factor):
        campanas, anuncios = [], []
        n = r.randint(3, 4)
        pesos = [r.uniform(0.5, 3) for _ in range(n)]
        for i in range(n):
            g = gasto_periodo * factor * pesos[i] / sum(pesos)
            nombre = NOMBRES_CAMP[i]
            calidad = r.uniform(0.45, 1.6) * (1.4 if "Remarketing" in nombre else 1)
            ads_camp = []
            n_ads = r.randint(2, 4)
            pesos_ad = [r.uniform(0.3, 3) for _ in range(n_ads)]
            for j in range(n_ads):
                ga = g * pesos_ad[j] / sum(pesos_ad)
                q = calidad * r.uniform(0.2, 1.7)
                ad_name = NOMBRES_AD[(i * 3 + j) % len(NOMBRES_AD)]
                ads_camp.append(_fila(r, ga, cpm_base * r.uniform(0.8, 1.4), 0.011 * q ** 0.5,
                                      conv_base * q, accion, ticket, {
                                          "ad_id": f"{i}{j}", "ad_name": ad_name,
                                          "adset_id": f"{i}", "adset_name": f"{nombre} · Conjunto A",
                                          "campaign_name": nombre, "miniatura": None}))
                if r.random() < 0.15:  # anuncio con frecuencia alta
                    ads_camp[-1]["frequency"] = f"{r.uniform(4, 6):.4f}"
            anuncios.extend(ads_camp)
            fila = _sumar(ads_camp)
            fila.update({"campaign_id": str(i), "campaign_name": nombre,
                         "objective": "OUTCOME_SALES" if cliente.objetivo == "ventas" else "OUTCOME_LEADS"})
            campanas.append(fila)
        return campanas, anuncios

    camp, ads = generar_periodo(1.0)
    camp_prev, _ = generar_periodo(r.uniform(0.8, 1.15))
    tot = _sumar(camp)
    diario = []
    for d in range(p.dias):
        dia = p.desde + timedelta(days=d)
        f = _fila(r, float(tot["spend"]) / p.dias * r.uniform(0.7, 1.3),
                  cpm_base * r.uniform(0.85, 1.2), 0.011 * r.uniform(0.8, 1.2),
                  conv_base * r.uniform(0.6, 1.4), accion, ticket)
        f["date_start"] = f["date_stop"] = dia.isoformat()
        diario.append(f)
    return {"cuenta": {"name": f"{cliente.nombre} · Cuenta publicitaria", "currency": cliente.moneda},
            "actual": {"totales": tot, "campanas": camp, "anuncios": ads, "diario": diario},
            "anterior": {"totales": _sumar(camp_prev), "campanas": camp_prev}}


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
