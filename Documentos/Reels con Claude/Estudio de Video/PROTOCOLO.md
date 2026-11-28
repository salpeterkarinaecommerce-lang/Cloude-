# Estudio de Video · protocolo

Link: https://claude.ai/artifact/3bg9pLGcFwVh692N3RUaYv

```
ESTUDIO DE VIDEO · protocolo para subir videos (Artifact + ArtifactData)

1. Abrí el artifact: Artifact action "read" con su url
   (o action "list" y buscá el título "Estudio de Video").
2. Subí el MP4: Artifact action "publish" con url, file_path y asset: true.
   Guardá el "id" del resultado (assetId). Límite 15 MB: si pesa más,
   recomprimí con ffmpeg -c:v libx264 -crf 26 -c:a aac -movflags +faststart.
3. Elegí el proyecto: ArtifactData action "list", collection "proyectos".
   - Versión nueva de un video que ya está: usá ese mismo id de proyecto.
   - Video nuevo: id = slug corto y estable, p. ej. "ubicacion-arcoiris-juncal".
4. Escribí la versión (n = ultimaVersion + 1, o 1 si es nuevo):
   ArtifactData "set" en proyectos/<id>/versiones/v<n>
   {
     "n": <n>, "creada": "<ISO>", "nota": "qué cambió",
     "origen": "chat donde se hizo",
     "video": {"assetId": "<id>", "ancho": 1080, "alto": 1920, "duracion": 12.4},
     "subtitulos": [{"texto": "Hola", "inicio": 0.0, "fin": 1.8,
                     "x": 0.5, "y": 0.74, "estilo": {"color": "#FFFFFF"}}],
     "textos": [{"texto": "Título", "inicio": 0, "fin": 3, "x": 0.5, "y": 0.3}]
   }
   OBLIGATORIO: subí el MP4 SIN subtítulos quemados (renderizá una versión
   limpia) y mandá TODOS los subtítulos en "subtitulos", con sus tiempos.
   Así aparecen en la línea de tiempo y se pueden editar y mover.
   x/y van de 0 a 1 (centro del texto). "estilo" acepta: fuente, peso,
   tam (px sobre 1080 de ancho), color, mayus, contorno, grosor, sombra,
   fondo ("ninguno"|"caja"), colorFondo, opFondo, anim ("pop"|"fundido"|
   "subir"|"escribir"|"karaoke"), resaltado, efecto ("neon-dorado"|
   "neon-rosa"|"neon-celeste"|"neon-verde"|"fuego"|"oro"|"plata"|
   "arcoiris"|"personal"), colorEfecto (hex, con "personal"), tornasol
   (0-100, reflejo tornasolado con "personal"), brillo (0-100), cursiva,
   subrayado, ancho, alin.
   Los textos fijos (títulos, etiquetas) van en "textos" con el mismo formato.
5. Actualizá el proyecto: ArtifactData "set" (nuevo) o "update" (existente)
   en proyectos/<id>
   {"titulo": "...", "ultimaVersion": <n>, "ultimoVideo": "<assetId>",
    "actualizado": "<ISO>", "creado": "<ISO, solo si es nuevo>"}
   Escribí primero la versión y después el proyecto. La página se actualiza sola.
6. Ediciones del usuario: proyectos/<id>/ediciones/v<n> (solo lectura para Claude).
```

`estudio.html` es el código fuente de la página. Para cambiarla, editá este archivo y publicalo con Artifact pasando la url de arriba.
