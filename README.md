# 🔥 Generador de Mapas de Calor de Mirada

Este proyecto permite generar un **video con visualización dinámica de mapas de calor** a partir de datos de seguimiento ocular (eye tracking) sincronizados con un video. Es ideal para estudios de usabilidad, análisis de atención y comportamiento visual.

Estos datos se obtienen gracias al juego **Piratas a la Vista**, que se puede encontrar en:  
👉 [https://github.com/AlejandroCB-23/AppVR.git](https://github.com/AlejandroCB-23/AppVR.git)

## 🧠 ¿Qué hace esta app?

- Procesa datos de mirada (`.jsonl`) junto con un video fuente.
- Genera un video que muestra:
  - ✅ Mapa de calor dinámico sobre el video.
  - ✅ Puntos de fijación recientes.
  - ✅ Rastro de la mirada.
  - ✅ Estadísticas en pantalla.
  - ✅ Escala de intensidad del mapa.
  - ✅ Timestamps sincronizados.
- Exporta también un **reporte de resumen** con estadísticas clave del análisis.