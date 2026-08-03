# ScenePort

**Convierte escenas en espacios.**

ScenePort es un proyecto de código abierto que transforma fotos, vídeos y
señales de cámaras en vivo en entornos 3D explorables. El desarrollo comienza
con un prototipo de una sola imagen y avanza hacia la reconstrucción de vídeo
multivista y la captura espacial con una cámara en vivo.

> [!IMPORTANT]
> Una sola imagen no puede revelar la geometría de las zonas que no fueron
> capturadas. El primer hito genera una escena 3D con profundidad inferida, no
> una reconstrucción completa ni métricamente exacta.

## Idiomas

- [English](../../README.md)
- [한국어](README.ko.md)
- [日本語](README.ja.md)
- [简体中文](README.zh-CN.md)
- **Español**

La documentación en inglés es la fuente principal del proyecto.

## Visión

1. Crear una escena interactiva con profundidad a partir de una foto.
2. Usar fotogramas de vídeo para reconstruir geometría más completa y coherente.
3. Conectar una cámara para capturar y visualizar espacios casi en tiempo real.

## Primer MVP: de foto a 3D

- Aceptar una imagen JPG o PNG.
- Estimar un mapa de profundidad a partir de la imagen.
- Convertir el color y la profundidad estimada en geometría 3D con color.
- Mostrar el resultado en un visor interactivo con órbita, desplazamiento y zoom.
- Comunicar claramente las limitaciones de la reconstrucción.

La recuperación de superficies ocultas, la escala métrica, la geometría con
calidad de producción y el procesamiento en tiempo real quedan fuera del primer
hito.

## Estado del proyecto

ScenePort se encuentra en la etapa de **planificación y creación de prototipos**.
Las API, los formatos y los detalles de implementación pueden cambiar sin previo
aviso.

## Documentación

- [Resumen del producto](../product-brief.md)
- [Hoja de ruta](../roadmap.md)
- [Arquitectura](../architecture.md)
- [Internacionalización](../i18n.md)
- [Guía de contribución](../../CONTRIBUTING.md)

La documentación técnica detallada se mantiene actualmente en inglés.

## Licencia

ScenePort se distribuye bajo la [Licencia MIT](../../LICENSE).
