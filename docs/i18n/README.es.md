# DepthScape

**Convierte una foto de paisaje en una escena 2.5D explorable.**

DepthScape es un proyecto de código abierto que transforma una foto de paisaje
en una escena por capas con profundidad. Estima la profundidad relativa, separa
la imagen en primer plano, plano medio y fondo, genera pequeñas zonas ocultas
por el primer plano y ofrece un efecto de paralaje limitado en el navegador.

> [!IMPORTANT]
> DepthScape no recupera el contenido real detrás de un objeto. Las zonas
> ocultas son generadas por IA a partir del contexto visible y deben señalarse
> como contenido generado. El resultado es una experiencia visual 2.5D, no una
> reconstrucción 3D completa ni métricamente exacta.

## Idiomas

- [English](../../README.md)
- [한국어](README.ko.md)
- [日本語](README.ja.md)
- [简体中文](README.zh-CN.md)
- **Español**

La documentación en inglés es la fuente principal del proyecto.

## Experiencia objetivo

```text
Foto de paisaje
→ mapa de profundidad relativa
→ capas de primer plano, plano medio y fondo
→ máscaras de oclusión y huecos
→ relleno de imagen y profundidad del fondo
→ escena 2.5D por capas
→ vista interactiva con paralaje limitado
```

El primer visor limitará el movimiento de la cámara a un intervalo pequeño y
documentado. Así se reduce el contenido generado y se atenúan los desgarros en
los bordes de profundidad.

## Modelos de referencia iniciales

- **Depth Anything V2 Small:** candidato para profundidad relativa
- **LaMa:** candidato para relleno de imagen RGB
- **Código de DepthScape:** capas, visibilidad, profundidad oculta y escena

Las versiones exactas, las licencias de los pesos, los requisitos de hardware y
las alternativas se fijarán después de un experimento reproducible. Solo se
considerará un pequeño modelo de corrección propio cuando exista una limitación
importante y medible en la referencia.

## Alcance

- Aceptar una foto de paisaje JPG o PNG local.
- Conservar la orientación y la relación de aspecto.
- Mostrar la profundidad relativa y las máscaras de capa.
- Generar solo el fondo necesario para el movimiento de cámara permitido.
- Distinguir los píxeles observados de los generados.
- Ofrecer paralaje limitado y accesible mediante teclado.
- Guardar metadatos de configuración compactos para reproducir el resultado.

La reconstrucción de vídeo, la cámara en vivo, el movimiento libre, la
profundidad métrica y la reconstrucción completa de superficies ocultas quedan
fuera del alcance.

## Estado del proyecto

DepthScape está en la etapa de **planificación y evaluación de referencias**.
Las API, los formatos, los modelos y los detalles de implementación pueden
cambiar durante los primeros experimentos.

## Documentación

- [Resumen del producto](../product-brief.md)
- [Hoja de ruta](../roadmap.md)
- [Arquitectura](../architecture.md)
- [Modelos de referencia](../model-baselines.md)
- [Decisión de alcance](../decisions/0001-focus-on-landscape-2-5d.md)
- [Internacionalización](../i18n.md)
- [Guía de contribución](../../CONTRIBUTING.md)

La documentación técnica detallada se mantiene actualmente en inglés.

## Licencia

DepthScape se distribuye bajo la [Licencia MIT](../../LICENSE).
