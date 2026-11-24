"""Panel web protegido con contraseña.

El HTML del panel se cifra con AES-256-GCM (clave derivada de PANEL_PASSWORD con PBKDF2-SHA256,
600.000 iteraciones). Lo que se publica en GitHub Pages es solo una pantalla de contraseña + datos
cifrados: sin la contraseña nadie puede leer los números de tus clientes, aunque el repo sea público.
"""
from __future__ import annotations

import base64
import html as html_mod
import json
import os
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from . import render
from .config import RAIZ

CARPETA_PANEL = RAIZ / "docs"
ITERACIONES = 600_000

CASCARA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>__TITULO__</title>
<style>
  body { margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
         font-family: "Segoe UI", Arial, sans-serif; background: #111827; color: #f9fafb; padding: 16px; box-sizing: border-box; }
  form { background: #1f2937; padding: 28px; border-radius: 14px; width: 100%; max-width: 340px; }
  h1 { font-size: 18px; margin: 0 0 4px; } p { color: #9ca3af; font-size: 13px; margin: 0 0 16px; }
  input, button { width: 100%; box-sizing: border-box; padding: 11px 12px; border-radius: 8px; font-size: 15px; }
  input { border: 1px solid #374151; background: #111827; color: #fff; margin-bottom: 10px; }
  button { border: 0; background: #4f46e5; color: #fff; font-weight: 600; cursor: pointer; }
  label { font-size: 12px; color: #9ca3af; display: flex; gap: 6px; align-items: center; margin-bottom: 12px; }
  label input { width: auto; margin: 0; }
  .err { color: #fca5a5; font-size: 13px; min-height: 18px; margin-top: 8px; }
</style></head><body>
<form id="f"><h1>Panel de reportes</h1><p>__TITULO__</p>
<input id="c" type="password" placeholder="Contraseña" autocomplete="current-password" autofocus>
<label><input id="r" type="checkbox"> Recordar en este dispositivo</label>
<button>Entrar</button><div class="err" id="e"></div></form>
<script>
const D = __DATOS__;
const b = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
async function abrir(clave) {
  const k0 = await crypto.subtle.importKey("raw", new TextEncoder().encode(clave), "PBKDF2", false, ["deriveKey"]);
  const k = await crypto.subtle.deriveKey({name: "PBKDF2", salt: b(D.s), iterations: D.i, hash: "SHA-256"},
                                          k0, {name: "AES-GCM", length: 256}, false, ["decrypt"]);
  const txt = new TextDecoder().decode(await crypto.subtle.decrypt({name: "AES-GCM", iv: b(D.n)}, k, b(D.c)));
  document.open(); document.write(txt); document.close();
}
function guardada() { try { return localStorage.getItem("panel_clave"); } catch (e) { return null; } }
const g = guardada(); if (g) abrir(g).catch(() => { try { localStorage.removeItem("panel_clave"); } catch (e) {} });
document.getElementById("f").addEventListener("submit", async ev => {
  ev.preventDefault();
  const clave = document.getElementById("c").value;
  document.getElementById("e").textContent = "Abriendo…";
  try {
    if (document.getElementById("r").checked) { try { localStorage.setItem("panel_clave", clave); } catch (e) {} }
    await abrir(clave);
  } catch (e) { document.getElementById("e").textContent = "Contraseña incorrecta."; }
});
</script></body></html>"""


def cifrar(contenido: str, clave: str, titulo: str) -> str:
    sal, nonce = os.urandom(16), os.urandom(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sal, iterations=ITERACIONES)
    cifrado = AESGCM(kdf.derive(clave.encode())).encrypt(nonce, contenido.encode(), None)
    datos = {"s": base64.b64encode(sal).decode(), "n": base64.b64encode(nonce).decode(),
             "c": base64.b64encode(cifrado).decode(), "i": ITERACIONES}
    return (CASCARA.replace("__TITULO__", html_mod.escape(titulo))
            .replace("__DATOS__", json.dumps(datos)))


def _actualizar_historial(clave: str):
    carpeta = CARPETA_PANEL / "historial"
    archivos = sorted((p.stem for p in carpeta.glob("*.html")), reverse=True)
    filas = "".join(f'<li><a href="historial/{a}.html">{a.replace("-S", " · semana ")}</a></li>' for a in archivos)
    contenido = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Historial</title><style>body{{font-family:Segoe UI,Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px 16px;background:#f3f4f6;color:#111827}}
a{{color:#4f46e5}} li{{margin:6px 0}}</style></head><body><h1>Historial de paneles</h1>
<p><a href="semanal.html">Último semanal</a> · <a href="mensual.html">Último mensual</a></p><ul>{filas}</ul></body></html>"""
    (CARPETA_PANEL / "historial.html").write_text(cifrar(contenido, clave, "Historial"), encoding="utf-8")


def publicar(periodo, reportes: list[dict]) -> Path | None:
    """Genera docs/<tipo>.html y docs/historial/<clave>.html cifrados. Devuelve la ruta o None."""
    clave = os.environ.get("PANEL_PASSWORD")
    contenido = render.html("panel.html.j2", periodo=periodo, reportes=reportes,
                            generado=datetime.now().strftime("%d/%m/%Y %H:%M"))
    if not clave:
        print("   ⚠ PANEL_PASSWORD no está configurada: el panel se guarda SIN cifrar solo en salida/ (no se publica).")
        ruta = RAIZ / "salida" / f"panel-{periodo.clave}.html"
        ruta.parent.mkdir(exist_ok=True)
        ruta.write_text(contenido, encoding="utf-8")
        return ruta
    if len(clave) < 12:
        print("   ⚠ PANEL_PASSWORD es corta: usá al menos 12 caracteres.")
    (CARPETA_PANEL / "historial").mkdir(parents=True, exist_ok=True)
    cifrado = cifrar(contenido, clave, periodo.titulo)
    (CARPETA_PANEL / f"{periodo.tipo}.html").write_text(cifrado, encoding="utf-8")
    (CARPETA_PANEL / "historial" / f"{periodo.clave}.html").write_text(cifrado, encoding="utf-8")
    (CARPETA_PANEL / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=semanal.html">'
        '<a href="semanal.html">Ir al panel</a>', encoding="utf-8")
    (CARPETA_PANEL / ".nojekyll").write_text("", encoding="utf-8")
    _actualizar_historial(clave)
    # Copia local sin cifrar para adjuntar al mail
    local = RAIZ / "salida" / f"panel-{periodo.clave}.html"
    local.parent.mkdir(exist_ok=True)
    local.write_text(contenido, encoding="utf-8")
    return local

