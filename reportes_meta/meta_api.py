"""Descarga de datos desde la Graph API / Marketing API de Meta.

Requiere la variable de entorno META_ACCESS_TOKEN (token de System User del Business Manager)
con permisos: ads_read, read_insights, pages_read_engagement, pages_show_list,
instagram_basic, instagram_manage_insights.

Meta cambia y retira métricas con frecuencia, así que cada métrica orgánica se pide de forma
tolerante: si una falla, se registra un aviso y el reporte sigue con las demás.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timedelta, timezone

import requests

from .config import Cliente
from .periodos import Periodo

VERSION = os.environ.get("META_API_VERSION", "v23.0")
BASE = f"https://graph.facebook.com/{VERSION}"

CAMPOS_INSIGHTS = [
    "spend", "impressions", "reach", "frequency", "clicks", "inline_link_clicks",
    "ctr", "inline_link_click_ctr", "cpc", "cpm", "actions", "action_values",
]
# ThruPlays (video visto completo o 15 s). Las reproducciones de 3 s vienen en actions (video_view).
CAMPOS_VIDEO = ["video_thruplay_watched_actions"]


class ErrorMeta(RuntimeError):
    pass


class MetaAPI:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("META_ACCESS_TOKEN")
        if not self.token:
            raise ErrorMeta("Falta META_ACCESS_TOKEN. Configuralo como secreto en GitHub "
                            "(Settings → Secrets and variables → Actions).")
        self.avisos: list[str] = []
        self._tokens_pagina: dict[str, str] = {}

    # ------------------------------------------------------------------ HTTP
    def get(self, ruta: str, params: dict | None = None, token: str | None = None) -> dict:
        params = dict(params or {})
        params["access_token"] = token or self.token
        url = ruta if ruta.startswith("http") else f"{BASE}/{ruta.lstrip('/')}"
        for intento in range(4):
            r = requests.get(url, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            try:
                err = r.json().get("error", {})
            except ValueError:
                err = {"message": r.text[:200]}
            # 4, 17, 32, 613 = límites de uso; reintentar con espera
            if err.get("code") in (4, 17, 32, 613) or r.status_code >= 500:
                time.sleep(15 * (intento + 1))
                continue
            raise ErrorMeta(f"{err.get('message', 'Error desconocido')} (código {err.get('code')})")
        raise ErrorMeta("Meta no respondió después de varios intentos (límite de uso).")

    def paginar(self, ruta: str, params: dict | None = None, token: str | None = None,
                maximo: int = 2000) -> list[dict]:
        datos = self.get(ruta, params, token)
        filas = list(datos.get("data", []))
        while datos.get("paging", {}).get("next") and len(filas) < maximo:
            datos = self.get(datos["paging"]["next"], {}, token)
            filas.extend(datos.get("data", []))
        return filas

    # ------------------------------------------------------------------- ADS
    def insights(self, cuenta: str, desde: date, hasta: date, nivel: str = "account",
                 extra: list[str] | None = None, diario: bool = False) -> list[dict]:
        params = {
            "fields": ",".join(CAMPOS_INSIGHTS + (extra or [])),
            "level": nivel,
            "time_range": json.dumps({"since": desde.isoformat(), "until": hasta.isoformat()}),
            "limit": 500,
        }
        if diario:
            params["time_increment"] = 1
        return self.paginar(f"{cuenta}/insights", params)

    def datos_ads(self, cliente: Cliente, p: Periodo) -> dict:
        c = cliente.ad_account_id
        cols_ad = ["ad_id", "ad_name", "adset_id", "adset_name", "campaign_id", "campaign_name"] + CAMPOS_VIDEO
        cols_cj = ["adset_id", "adset_name", "campaign_id", "campaign_name"]
        tot = self.insights(c, p.desde, p.hasta, extra=CAMPOS_VIDEO)
        tot_prev = self.insights(c, p.prev_desde, p.prev_hasta, extra=CAMPOS_VIDEO)
        campanas = self.insights(c, p.desde, p.hasta, "campaign", ["campaign_id", "campaign_name", "objective"])
        campanas_prev = self.insights(c, p.prev_desde, p.prev_hasta, "campaign", ["campaign_id", "campaign_name"])
        conjuntos = self.insights(c, p.desde, p.hasta, "adset", cols_cj)
        conjuntos_prev = self.insights(c, p.prev_desde, p.prev_hasta, "adset", cols_cj)
        anuncios = self.insights(c, p.desde, p.hasta, "ad", cols_ad)
        anuncios_prev = self.insights(c, p.prev_desde, p.prev_hasta, "ad", cols_ad)
        diario = self.insights(c, p.desde, p.hasta, diario=True)
        try:
            cuenta = self.get(c, {"fields": "name,currency,account_status"})
        except ErrorMeta as e:
            self.avisos.append(f"No se pudo leer la cuenta publicitaria: {e}")
            cuenta = {}
        return {
            "cuenta": cuenta,
            "objetos": self._objetos(c),
            "actual": {"totales": tot[0] if tot else {}, "campanas": campanas, "conjuntos": conjuntos,
                       "anuncios": anuncios, "diario": diario},
            "anterior": {"totales": tot_prev[0] if tot_prev else {}, "campanas": campanas_prev,
                         "conjuntos": conjuntos_prev, "anuncios": anuncios_prev},
        }

    def _objetos(self, cuenta: str) -> dict:
        """Configuración actual de campañas, conjuntos y anuncios (presupuestos, estado, creativo)."""
        pedidos = {
            "campanas": ("campaigns", "id,name,effective_status,objective,daily_budget,lifetime_budget,bid_strategy"),
            "conjuntos": ("adsets", "id,name,campaign_id,effective_status,daily_budget,lifetime_budget,"
                                    "optimization_goal,learning_stage_info"),
            "anuncios": ("ads", "id,name,adset_id,campaign_id,effective_status,created_time,"
                                "creative{object_type,thumbnail_url,image_url,video_id,title,body,call_to_action_type}"),
        }
        res = {}
        for clave, (edge, campos) in pedidos.items():
            try:
                filas = self.paginar(f"{cuenta}/{edge}", {"fields": campos, "limit": 200}, maximo=1000)
            except ErrorMeta as e:
                self.avisos.append(f"No se pudo leer la configuración de {clave}: {e}")
                filas = []
            res[clave] = {f["id"]: f for f in filas}
        return res

    # ------------------------------------------------------------- FACEBOOK
    def _token_pagina(self, page_id: str) -> str:
        if page_id not in self._tokens_pagina:
            d = self.get(page_id, {"fields": "access_token"})
            self._tokens_pagina[page_id] = d.get("access_token", self.token)
        return self._tokens_pagina[page_id]

    def _metrica_pagina(self, page_id, token, metrica, desde, hasta) -> float | None:
        try:
            filas = self.get(f"{page_id}/insights", {
                "metric": metrica, "period": "day",
                "since": desde.isoformat(), "until": (hasta + timedelta(days=1)).isoformat(),
            }, token).get("data", [])
        except ErrorMeta as e:
            self.avisos.append(f"Facebook · métrica '{metrica}' no disponible: {e}")
            return None
        if not filas:
            return None
        return float(sum((v.get("value") or 0) for v in filas[0].get("values", [])
                         if isinstance(v.get("value"), (int, float))))

    def facebook(self, page_id: str, desde: date, hasta: date, con_posts: bool = True) -> dict:
        token = self._token_pagina(page_id)
        info = self.get(page_id, {"fields": "name,followers_count,fan_count,link"}, token)
        m = lambda *nombres: next((v for n in nombres
                                   if (v := self._metrica_pagina(page_id, token, n, desde, hasta)) is not None), None)
        res = {
            "nombre": info.get("name"),
            "seguidores": info.get("followers_count") or info.get("fan_count"),
            "alcance": m("page_impressions_unique"),
            "vistas": m("page_media_view", "page_impressions"),
            "interacciones": m("page_post_engagements"),
            "nuevos_seguidores": m("page_daily_follows_unique", "page_fan_adds_unique"),
            "publicaciones": [],
        }
        if con_posts:
            try:
                posts = self.paginar(f"{page_id}/posts", {
                    "fields": "id,message,created_time,permalink_url,full_picture,status_type,"
                              "shares,reactions.summary(true).limit(0),comments.summary(true).limit(0)",
                    "since": int(datetime.combine(desde, datetime.min.time(), timezone.utc).timestamp()),
                    "until": int(datetime.combine(hasta + timedelta(days=1), datetime.min.time(), timezone.utc).timestamp()),
                    "limit": 100,
                }, token, maximo=300)
            except ErrorMeta as e:
                self.avisos.append(f"Facebook · no se pudieron leer las publicaciones: {e}")
                posts = []
            for po in posts:
                reac = po.get("reactions", {}).get("summary", {}).get("total_count", 0)
                com = po.get("comments", {}).get("summary", {}).get("total_count", 0)
                comp = po.get("shares", {}).get("count", 0)
                res["publicaciones"].append({
                    "id": po["id"], "texto": (po.get("message") or "")[:200],
                    "fecha": po.get("created_time"), "tipo": po.get("status_type", "post"),
                    "link": po.get("permalink_url"), "imagen": po.get("full_picture"),
                    "reacciones": reac, "comentarios": com, "compartidos": comp,
                    "interacciones": reac + com + comp,
                })
        return res

    # ------------------------------------------------------------ INSTAGRAM
    def _ig_total(self, ig_id, metrica, desde, hasta) -> float | None:
        """Suma total_value en tramos de hasta 30 días (límite de la API)."""
        total, inicio, ok = 0.0, desde, False
        while inicio <= hasta:
            fin = min(inicio + timedelta(days=29), hasta)
            try:
                d = self.get(f"{ig_id}/insights", {
                    "metric": metrica, "period": "day", "metric_type": "total_value",
                    "since": inicio.isoformat(), "until": (fin + timedelta(days=1)).isoformat(),
                }).get("data", [])
                if d:
                    total += float(d[0].get("total_value", {}).get("value") or 0)
                    ok = True
            except ErrorMeta as e:
                self.avisos.append(f"Instagram · métrica '{metrica}' no disponible: {e}")
                return None
            inicio = fin + timedelta(days=1)
        return total if ok else None

    def _ig_seguidores_nuevos(self, ig_id, desde, hasta) -> float | None:
        try:
            d = self.get(f"{ig_id}/insights", {
                "metric": "follower_count", "period": "day",
                "since": desde.isoformat(), "until": (hasta + timedelta(days=1)).isoformat(),
            }).get("data", [])
        except ErrorMeta as e:
            self.avisos.append(f"Instagram · seguidores nuevos no disponibles (solo últimos 30 días): {e}")
            return None
        return float(sum(v.get("value", 0) for v in d[0].get("values", []))) if d else None

    def instagram(self, ig_id: str, desde: date, hasta: date, con_posts: bool = True) -> dict:
        info = self.get(ig_id, {"fields": "username,followers_count,media_count"})
        res = {
            "usuario": info.get("username"),
            "seguidores": info.get("followers_count"),
            "alcance": self._ig_total(ig_id, "reach", desde, hasta),
            "vistas": self._ig_total(ig_id, "views", desde, hasta),
            "interacciones": self._ig_total(ig_id, "total_interactions", desde, hasta),
            "cuentas_interactuaron": self._ig_total(ig_id, "accounts_engaged", desde, hasta),
            "visitas_perfil": self._ig_total(ig_id, "profile_views", desde, hasta),
            "nuevos_seguidores": self._ig_seguidores_nuevos(ig_id, desde, hasta),
            "publicaciones": [],
        }
        if not con_posts:
            return res
        try:
            media = self.paginar(f"{ig_id}/media", {
                "fields": "id,caption,media_type,media_product_type,timestamp,permalink,"
                          "like_count,comments_count,thumbnail_url,media_url",
                "since": int(datetime.combine(desde, datetime.min.time(), timezone.utc).timestamp()),
                "limit": 50,
            }, maximo=150)
        except ErrorMeta as e:
            self.avisos.append(f"Instagram · no se pudieron leer las publicaciones: {e}")
            media = []
        for mm in media:
            ts = datetime.fromisoformat(mm["timestamp"].replace("+0000", "+00:00"))
            if not (desde <= ts.date() <= hasta):
                continue
            ins = {}
            metricas = ["reach", "views", "saved", "shares", "total_interactions"]
            try:
                for fila in self.get(f"{mm['id']}/insights", {"metric": ",".join(metricas)}).get("data", []):
                    ins[fila["name"]] = (fila.get("values") or [{}])[0].get("value", 0)
            except ErrorMeta:
                pass
            tipo = mm.get("media_product_type") or mm.get("media_type")
            if tipo == "FEED" and mm.get("media_type") == "CAROUSEL_ALBUM":
                tipo = "CAROUSEL"
            res["publicaciones"].append({
                "id": mm["id"], "texto": (mm.get("caption") or "")[:200], "fecha": mm["timestamp"],
                "tipo": tipo, "link": mm.get("permalink"),
                "imagen": mm.get("thumbnail_url") or mm.get("media_url"),
                "me_gusta": mm.get("like_count", 0), "comentarios": mm.get("comments_count", 0),
                "guardados": ins.get("saved", 0), "compartidos": ins.get("shares", 0),
                "alcance": ins.get("reach"), "vistas": ins.get("views"),
                "interacciones": ins.get("total_interactions")
                or (mm.get("like_count", 0) + mm.get("comments_count", 0)),
            })
        return res


def descargar(cliente: Cliente, p: Periodo) -> dict:
    api = MetaAPI()
    datos: dict = {"ads": None, "facebook": None, "instagram": None, "avisos": api.avisos}
    if cliente.tiene_ads:
        try:
            datos["ads"] = api.datos_ads(cliente, p)
        except ErrorMeta as e:
            api.avisos.append(f"Meta Ads: {e}")
    if cliente.page_id:
        try:
            datos["facebook"] = {"actual": api.facebook(cliente.page_id, p.desde, p.hasta),
                                 "anterior": api.facebook(cliente.page_id, p.prev_desde, p.prev_hasta, False)}
        except ErrorMeta as e:
            api.avisos.append(f"Facebook: {e}")
    if cliente.instagram_id:
        try:
            datos["instagram"] = {"actual": api.instagram(cliente.instagram_id, p.desde, p.hasta),
                                  "anterior": api.instagram(cliente.instagram_id, p.prev_desde, p.prev_hasta, False)}
        except ErrorMeta as e:
            api.avisos.append(f"Instagram: {e}")
    return datos
