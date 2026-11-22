"""Carga y validación de la configuración de clientes (carpeta clientes/*.yaml)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_CLIENTES = RAIZ / "clientes"

OBJETIVOS = {
    "ventas": "Ventas",
    "leads": "Generación de clientes potenciales",
    "mensajes": "Mensajes (WhatsApp / Messenger / Instagram Direct)",
    "trafico": "Tráfico al sitio web",
    "reconocimiento": "Reconocimiento de marca / alcance",
}


def slugify(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()
    return texto or "cliente"


def _num(valor):
    """Convierte '1.500', '1500,5', '$ 2000' o 2000 en float. Vacío -> None."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip().replace("$", "").replace(" ", "")
    if not s or s.lower() in {"_no response_", "none", "-", "no"}:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1 or re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


@dataclass
class Cliente:
    slug: str
    nombre: str
    objetivo: str = "ventas"
    moneda: str = "ARS"
    ad_account_id: str | None = None
    page_id: str | None = None
    instagram_id: str | None = None
    presupuesto_mensual: float | None = None
    cpa_objetivo: float | None = None
    roas_objetivo: float | None = None
    ticket_promedio: float | None = None
    frecuencias: list[str] = field(default_factory=lambda: ["semanal", "mensual"])
    color: str = "#4F46E5"
    logo_url: str | None = None
    rubro: str | None = None
    notas: str | None = None
    activo: bool = True

    @property
    def tiene_ads(self) -> bool:
        return bool(self.ad_account_id)

    @property
    def tiene_organico(self) -> bool:
        return bool(self.page_id or self.instagram_id)

    @property
    def objetivo_legible(self) -> str:
        return OBJETIVOS.get(self.objetivo, self.objetivo)

    @classmethod
    def desde_dict(cls, d: dict, slug: str | None = None) -> "Cliente":
        objetivo = str(d.get("objetivo", "ventas")).strip().lower()
        objetivo = slugify(objetivo).replace("-", "")
        alias = {"venta": "ventas", "lead": "leads", "clientespotenciales": "leads",
                 "mensaje": "mensajes", "whatsapp": "mensajes", "trafico": "trafico",
                 "alcance": "reconocimiento", "marca": "reconocimiento"}
        objetivo = alias.get(objetivo, objetivo)
        if objetivo not in OBJETIVOS:
            raise ValueError(f"Objetivo desconocido: {d.get('objetivo')!r}. Opciones: {', '.join(OBJETIVOS)}")

        act = d.get("ad_account_id")
        if act:
            act = str(act).strip()
            if not act.startswith("act_"):
                act = "act_" + re.sub(r"\D", "", act)

        frecuencias = d.get("frecuencias") or ["semanal", "mensual"]
        if isinstance(frecuencias, str):
            frecuencias = [f.strip().lower() for f in re.split(r"[,\s/]+", frecuencias) if f.strip()]

        nombre = str(d["nombre"]).strip()
        return cls(
            slug=slug or d.get("slug") or slugify(nombre),
            nombre=nombre,
            objetivo=objetivo,
            moneda=str(d.get("moneda") or "ARS").upper().strip(),
            ad_account_id=act or None,
            page_id=(str(d["page_id"]).strip() if d.get("page_id") else None),
            instagram_id=(str(d["instagram_id"]).strip() if d.get("instagram_id") else None),
            presupuesto_mensual=_num(d.get("presupuesto_mensual")),
            cpa_objetivo=_num(d.get("cpa_objetivo")),
            roas_objetivo=_num(d.get("roas_objetivo")),
            ticket_promedio=_num(d.get("ticket_promedio")),
            frecuencias=frecuencias,
            color=str(d.get("color") or "#4F46E5"),
            logo_url=d.get("logo_url") or None,
            rubro=d.get("rubro") or None,
            notas=d.get("notas") or None,
            activo=bool(d.get("activo", True)),
        )

    def a_dict(self) -> dict:
        d = {
            "nombre": self.nombre,
            "activo": self.activo,
            "rubro": self.rubro,
            "objetivo": self.objetivo,
            "moneda": self.moneda,
            "ad_account_id": self.ad_account_id,
            "page_id": self.page_id,
            "instagram_id": self.instagram_id,
            "presupuesto_mensual": self.presupuesto_mensual,
            "cpa_objetivo": self.cpa_objetivo,
            "roas_objetivo": self.roas_objetivo,
            "ticket_promedio": self.ticket_promedio,
            "frecuencias": self.frecuencias,
            "color": self.color,
            "logo_url": self.logo_url,
            "notas": self.notas,
        }
        return {k: v for k, v in d.items() if v is not None}


def cargar_clientes(solo_activos: bool = True, incluir_ejemplos: bool = False) -> list[Cliente]:
    clientes = []
    rutas = sorted(CARPETA_CLIENTES.glob("*.yaml"))
    if incluir_ejemplos:
        rutas += sorted((CARPETA_CLIENTES / "ejemplos").glob("*.yaml"))
    for ruta in rutas:
        if ruta.name.startswith("_"):
            continue
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        cliente = Cliente.desde_dict(datos, slug=ruta.stem)
        if cliente.activo or not solo_activos:
            clientes.append(cliente)
    return clientes


def guardar_cliente(cliente: Cliente) -> Path:
    CARPETA_CLIENTES.mkdir(exist_ok=True)
    ruta = CARPETA_CLIENTES / f"{cliente.slug}.yaml"
    encabezado = f"# Cliente: {cliente.nombre}\n# Editá este archivo para cambiar objetivos, KPIs o cuentas.\n"
    ruta.write_text(encabezado + yaml.safe_dump(cliente.a_dict(), allow_unicode=True, sort_keys=False),
                    encoding="utf-8")
    return ruta
