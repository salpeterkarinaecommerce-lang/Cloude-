# Instrucciones para Claude

## Estudio de Video (obligatorio para cada video que hagas)

La usuaria edita todos sus videos en el **Estudio de Video**:
https://claude.ai/artifact/3bg9pLGcFwVh692N3RUaYv

Cada vez que termines un video (MP4), subilo ahí. Si es otra versión de un video
que ya existe, agregalo como **versión nueva del mismo proyecto**, no como proyecto nuevo.
El protocolo completo está en `Documentos/Reels con Claude/Estudio de Video/PROTOCOLO.md`.

Resumen:
1. `Artifact` action `read` con la url del Estudio.
2. Subí el MP4 con `Artifact` publish `{url, file_path, asset: true}` y guardá el `id`
   (máx. 15 MB; si pesa más, recomprimí con ffmpeg `-crf 26`).
3. `ArtifactData` `list` de `proyectos` para ver si el video ya existe.
4. `set` en `proyectos/<id>/versiones/v<n>` y después `set`/`update` en `proyectos/<id>`
   (`ultimaVersion`, `ultimoVideo`, `actualizado`). La página se actualiza sola.
5. Mandá los subtítulos como datos (`subtitulos: [{texto, inicio, fin}]`) para que se puedan editar.
