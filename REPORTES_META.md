# Sistema de reportes de Meta (Ads + orgánico)

Genera automáticamente, para cada cliente:

| Qué | Para quién | Contenido |
|---|---|---|
| **PDF del cliente** | Para reenviar al cliente | Resumen en lenguaje simple, KPIs con explicación, gráficos, mejores anuncios y publicaciones, próximos pasos y glosario. Con el color y el logo del cliente. |
| **PDF INTERNO** | Para vos | **Plan de acción**: qué cambiar en cada campaña, conjunto y anuncio, cómo y por qué. Además, el diagnóstico general, las métricas completas con variaciones, las tablas de campañas, conjuntos y anuncios, y el detalle del orgánico. |
| **Panel web** | Para vos | Todas las cuentas en una sola pantalla, protegido con contraseña, con historial. |

- **Cuándo:** el semanal sale todos los lunes (semana anterior, de lunes a domingo) y el mensual el día 1 (mes anterior). En los dos casos se compara contra el período anterior.
- **Cómo llega:** te llega un mail con todos los PDF adjuntos y un resumen de prioridades por cliente.
- **Costo:** $0. Corre gratis en GitHub Actions.

---

## Puesta en marcha (una sola vez)

### 1. Token de Meta (lo más importante)

1. Entrá a [developers.facebook.com](https://developers.facebook.com) → **Mis apps** → **Crear app** → tipo **Empresa / Business**, y vinculala a tu Business Manager.
2. En la app, agregá los productos **Marketing API** e **Instagram Graph API**.
3. En **Business Manager → Configuración del negocio → Usuarios → Usuarios del sistema**, creá un usuario del sistema con rol **Administrador**.
4. **Asignale los activos** de cada cliente: cuentas publicitarias, páginas e Instagram, con permiso de ver rendimiento o administrar.
5. Tocá **Generar nuevo token**, elegí tu app, poné caducidad **Nunca** y marcá estos permisos:
   `ads_read`, `read_insights`, `pages_show_list`, `pages_read_engagement`, `instagram_basic`, `instagram_manage_insights`, `business_management`.
6. Copiá el token. **No lo pegues en ningún chat ni archivo:** va directo a GitHub (paso 4).

> Cuando sumás un cliente nuevo, acordate de asignar sus activos al usuario del sistema (paso 4). Si no lo hacés, el reporte va a mostrar un aviso de permisos.

### 2. Contraseña de aplicación de Gmail (para el envío por mail)

1. Activá la verificación en 2 pasos en tu cuenta de Google.
2. Entrá a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), creá una contraseña llamada "Reportes" y copiá los 16 caracteres.

### 3. (Opcional) IA gratis para redactar los textos

Sin este paso igual tenés interpretaciones y recomendaciones, porque las genera el motor de reglas. Si querés que además una IA redacte un párrafo más natural:

1. Entrá a [aistudio.google.com/apikey](https://aistudio.google.com/apikey) y creá una API key gratis de Gemini.
2. ⚠️ En el plan gratuito, Google puede usar lo que se envía para mejorar sus modelos. Solo se mandan métricas agregadas (ningún dato personal), pero tenelo en cuenta.

### 4. Cargar los secretos en GitHub

En el repositorio: **Settings → Secrets and variables → Actions → New repository secret**:

| Nombre | Valor |
|---|---|
| `META_ACCESS_TOKEN` | El token del paso 1 |
| `PANEL_PASSWORD` | La contraseña que vas a usar para abrir el panel. **Mínimo 12 caracteres**, una frase larga es ideal. |
| `GMAIL_USER` | Tu Gmail |
| `GMAIL_APP_PASSWORD` | La contraseña de aplicación del paso 2 |
| `REPORT_TO` | Mail donde querés recibir los reportes (si no lo cargás, llegan a `GMAIL_USER`) |
| `GEMINI_API_KEY` | *(opcional)* La key del paso 3 |

En la pestaña **Variables**, también podés cargar:

| Nombre | Valor |
|---|---|
| `PANEL_URL` | La dirección del panel (paso 5), para que el mail incluya el link |
| `META_API_VERSION` | *(opcional)* Versión de la API, por ejemplo `v23.0` |

### 5. Activar el panel web

En **Settings → Pages → Build and deployment**, elegí *Deploy from a branch*, la rama principal y la carpeta **`/docs`**. Guardá.
El panel queda en `https://<tu-usuario>.github.io/<repo>/`. Cargá esa dirección en la variable `PANEL_URL`.

> El panel se publica **cifrado** (AES-256). Aunque el repo sea público, sin la contraseña nadie puede ver los números.

### 6. Probar

**Actions → Reportes Meta → Run workflow**. Tildá *Usar datos de prueba* para probar sin token: genera los reportes con los dos clientes de ejemplo y te los manda por mail.

---

## Agregar un cliente

**Opción A, con el formulario (recomendada):** **Issues → New issue → ➕ Nuevo cliente**. Completás el formulario y, en menos de un minuto, el sistema crea `clientes/<cliente>.yaml`, te avisa con un comentario y cierra el issue.
Solo funciona si el issue lo abrís vos, la dueña del repo. Si lo abre otra persona, se ignora.

**Opción B, desde la terminal:** `python -m reportes_meta nuevo-cliente`, que hace las mismas preguntas una por una.

**Para editar o pausar un cliente:** abrí `clientes/<cliente>.yaml` en GitHub, tocá el lápiz, cambiá lo que necesites (por ejemplo `activo: false`) y guardá.

### Qué pide el formulario y para qué sirve

| Campo | Para qué se usa |
|---|---|
| Objetivo (ventas / leads / mensajes / tráfico / reconocimiento) | Define qué cuenta como "resultado" (compra, lead, conversación…) y qué reglas de análisis se aplican. |
| CPA objetivo | Clave para el diagnóstico: decide qué anuncios pausar (CPA > 2× objetivo) y cuáles escalar (< 0,75×). |
| ROAS objetivo / ticket promedio | Solo para ventas: alerta si el retorno cae y sugiere acciones sobre el ticket. |
| Presupuesto mensual | Controla el ritmo de gasto (si va por arriba o por debajo de lo pactado). |
| Frecuencia | Semanal, mensual o ambas, según el cliente. |
| Color y logo | Personalizan el PDF del cliente. |
| Notas | Contexto que se suma al análisis (y a la IA, si la activaste). |

---

## Plan de acción para Meta Ads (en el PDF interno y en el panel)

Cada cambio recomendado viene en una ficha con:

| | |
|---|---|
| **Dónde** | Campaña › Conjunto › Anuncio, con la miniatura y el formato del creativo (video, imagen o carrusel) |
| **Qué hacer** | El cambio exacto: "Apagar este anuncio", "Subir el presupuesto del conjunto de $ 9.500 a $ 11.400 diarios", "Reemplazar los primeros 3 segundos del video"… |
| **Por qué** | Los números que lo justifican, comparados con tu CPA objetivo, con el promedio de la cuenta y con el mejor anuncio del mismo conjunto |
| **Cómo hacerlo** | Los pasos dentro del Administrador de anuncios |
| **Impacto esperado** | Cuánta plata libera o cuántos resultados más se esperan |

Arriba de todo hay una tabla resumen ordenada por prioridad (alta, media, baja).

### Qué cambios detecta

| Nivel | Cambio | Cuándo lo sugiere |
|---|---|---|
| Anuncio | **Pausar anuncio** / **Reemplazar anuncio** | Gastó más de 2 veces el CPA objetivo sin resultados, o su CPA es más de 2 veces el objetivo. Si es el único anuncio del conjunto, primero pide subir el reemplazo. |
| Anuncio | **Cambiar el gancho del video** | Menos del 25 % de las impresiones pasa los 3 primeros segundos. |
| Anuncio | **Acortar / dar ritmo al video** | El gancho funciona, pero menos del 20 % sigue mirando hasta el final (ThruPlay). |
| Anuncio | **Cambiar texto / imagen** | CTR bajo: menos de 0,8 % o 30 % por debajo de la cuenta. Muestra el texto actual y sugiere un CTA mejor. |
| Anuncio | **Revisar la página de destino** | El CTR es bueno pero los clics no convierten. Los pasos se adaptan a ventas, leads o mensajes. |
| Anuncio | **Refrescar creativo (fatiga)** | Frecuencia mayor a 4 y CTR en caída contra el período anterior. |
| Anuncio | **Duplicar ganador** | CPA 25 % por debajo del objetivo con volumen. Sugiere usar la publicación existente y crear variaciones en otros formatos. |
| Conjunto o campaña | **Subir presupuesto (de $X a $Y)** | CPA 20 % por debajo del objetivo, con volumen y frecuencia sana. Siempre sube +20 % para no reiniciar el aprendizaje. Si la campaña tiene presupuesto de campaña (Advantage+), lo indica ahí. |
| Conjunto | **Bajar presupuesto** / **Pausar conjunto** | CPA entre 1,3 y 2,5 veces el objetivo, o sin resultados. |
| Conjunto | **Ampliar audiencia** | Frecuencia alta junto con suba del CPM o del CPA. Las instrucciones cambian según sea prospección o remarketing. |
| Conjunto | **Agregar creativos** | Menos de 3 anuncios activos. |
| Conjunto | **Salir de aprendizaje limitado** | Meta lo marca como "Aprendizaje limitado". |
| Campaña | **Mover presupuesto entre campañas** | Una campaña consigue resultados 40 % más baratos que otra. Indica cuánto mover por día. |
| Campaña | **Pausar campaña** | Ninguno de sus conjuntos llega a un costo aceptable. |
| Campaña | **Unificar conjuntos** | Hay 3 o más conjuntos con pocas conversiones. |
| Campaña | **Corregir suba de CPA** | Explica la causa: CPM, CTR o conversión de la web. |

El sistema también evita contradicciones: si un conjunto se va a pausar, no sugiere cambios en sus anuncios, y si se pausarían todos los conjuntos de una campaña, recomienda pausar la campaña entera.
Las referencias (25 % de gancho, 0,8 % de CTR, etc.) se ajustan al principio de `reportes_meta/acciones.py`.

### Diagnóstico general de la cuenta

Además del plan, el reporte interno resume la salud general de la cuenta:
- CPA y ROAS contra el objetivo.
- Frecuencia, CTR y CPM.
- Carritos que no terminan en compra.
- Ritmo de gasto contra el presupuesto mensual.
- En el orgánico: frecuencia de publicación, alcance, engagement, mejor formato, mejor horario y qué publicación conviene pasar a anuncio.

## Uso local (opcional)

```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m reportes_meta generar --periodo semanal --demo --sin-mail   # prueba con datos ficticios
python -m reportes_meta listar
```

Los archivos quedan en `salida/`, que **nunca** se sube al repo.

## Privacidad

- Los PDF **no** se guardan en GitHub: solo te llegan por mail.
- El panel se publica cifrado.
- ⚠️ Mientras el repositorio sea **público**, los archivos de `clientes/*.yaml` y los issues de alta (IDs de cuentas, presupuestos, objetivos) se pueden ver. Si eso te preocupa, pasá el repositorio a **privado**: Actions sigue siendo gratis (2.000 minutos por mes, y cada reporte usa unos 3 a 5), pero GitHub Pages en un repo privado requiere un plan pago. En ese caso, el panel te sigue llegando como archivo HTML adjunto en el mail.

## Estructura

```
clientes/               ← un .yaml por cliente (ejemplos/ solo se usa en modo demo)
reportes_meta/
  meta_api.py           ← descarga de Meta (Ads, Facebook, Instagram)
  metricas.py           ← cálculo de KPIs y variaciones
  acciones.py           ← plan de acción por campaña / conjunto / anuncio
  analisis.py           ← diagnóstico general y resumen para el cliente
  ia.py                 ← redacción opcional con Gemini (gratis)
  plantillas/           ← diseño de los PDF y del panel
  panel.py              ← panel cifrado para GitHub Pages
  correo.py             ← envío por Gmail
.github/workflows/      ← automatización (reportes + alta de clientes)
.github/ISSUE_TEMPLATE/ ← formulario "Nuevo cliente"
```
