"""Capa OPCIONAL de redacción con IA gratuita (Google Gemini, plan gratuito).

Solo se activa si existe la variable GEMINI_API_KEY. Si no está, o si falla, el sistema usa
únicamente el motor de reglas (analisis.py), así que el reporte nunca se rompe.

Ojo: en el plan gratuito, Google puede usar los datos enviados para mejorar sus productos.
Solo se envían métricas agregadas y los hallazgos (sin datos personales de nadie).
"""
from __future__ import annotations

import json
import os

import requests

MODELO = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def _llamar(prompt: str) -> str | None:
    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent"
    try:
        r = requests.post(url, params={"key": clave}, timeout=90, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 900},
        })
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:  # noqa: BLE001 - la IA es opcional; nunca debe romper el reporte
        print(f"   (IA no disponible: {e})")
        return None


def redactar(cliente, periodo, metricas: dict, analisis) -> dict:
    """Devuelve {'cliente': texto, 'interno': texto} o {} si la IA no está configurada."""
    if not os.environ.get("GEMINI_API_KEY"):
        return {}
    ads = metricas.get("ads") or {}
    contexto = {
        "cliente": cliente.nombre, "rubro": cliente.rubro, "objetivo": cliente.objetivo_legible,
        "periodo": periodo.titulo, "moneda": cliente.moneda,
        "cpa_objetivo": cliente.cpa_objetivo, "roas_objetivo": cliente.roas_objetivo,
        "ads_actual": ads.get("actual"), "ads_variacion": ads.get("var"),
        "instagram": {k: v for k, v in (metricas.get("instagram") or {}).items() if k in
                      ("alcance", "interacciones", "nuevos_seguidores", "engagement", "var")},
        "facebook": {k: v for k, v in (metricas.get("facebook") or {}).items() if k in
                     ("alcance", "interacciones", "nuevos_seguidores", "engagement", "var")},
        "hallazgos": [h.__dict__ for h in analisis.hallazgos],
        "notas_agencia": cliente.notas,
    }
    datos = json.dumps(contexto, ensure_ascii=False, default=str)
    texto_cliente = _llamar(
        "Sos una community manager y media buyer argentina. Con estos datos de Meta, escribí un párrafo "
        "de 4 a 6 oraciones para el CLIENTE (dueño de un negocio, no sabe de marketing), en español "
        "rioplatense, cálido y claro, sin tecnicismos (si usás uno, explicalo). Contá qué pasó, qué salió "
        "bien y qué vamos a hacer. No inventes números: usá solo los del JSON. Sin títulos ni viñetas.\n\n" + datos)
    texto_interno = _llamar(
        "Sos un media buyer senior de Meta Ads. Con estos datos y hallazgos, escribí para la AGENCIA un "
        "diagnóstico breve (máx. 120 palabras) en español rioplatense: la causa raíz más probable del "
        "rendimiento y las 3 acciones prioritarias en orden, concretas (qué tocar, cuánto). No inventes "
        "números.\n\n" + datos)
    return {k: v for k, v in (("cliente", texto_cliente), ("interno", texto_interno)) if v}
