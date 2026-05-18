# AgroDataLab EnviroPro

**Analítica de datos y aplicación web para Horizonte Verde Digital.**

Proyecto intermodular que transforma datos reales de sensores agrícolas
**EnviroPro** en información útil para analizar el estado del suelo,
detectar riesgo relativo, generar alertas y visualizar resultados.

---
## DESPLIEGUE🐐
- https://agrodatalab.onrender.com
## Integrantes

- **Diegos** — análisis, modelo, aplicación Django, despliegue y documentación.

## Descripción del problema

El sistema EnviroPro recoge lecturas horarias de:

- 8 sensores de **humedad del suelo** (porcentaje).
- 8 sensores de **temperatura del suelo** (promedio / máximo / mínimo).
- **Batería** y **panel solar** del nodo (milivoltios).

Los datos llegan en bruto con peculiaridades reales: BOM UTF-8, coma
decimal, cabecera en dos filas, sensores ocasionalmente bloqueados y
huecos temporales. El producto debe **importar, limpiar, analizar,
generar alertas y mostrar resultados en una aplicación web Django**.

## Estructura del repositorio

```
proyecto/
├── README.md                  # este archivo
├── requirements.txt           # dependencias Python
├── .gitignore
├── analisis/
│   ├── analizador.py          # módulo reutilizable (importar, limpiar, alertas)
│   ├── main.py                # pipeline completo + gráficas + modelo
│   ├── notebook_analisis.ipynb
│   ├── datos/
│   │   └── enviropro_raw.csv  # dataset original
│   ├── graficas/              # 12 PNG con las visualizaciones obligatorias
│   └── salidas/
│       ├── enviropro_limpio.csv
│       ├── enviropro_diario.csv
│       ├── alertas.csv
│       ├── indicadores_resumen.json
│       ├── informe_limpieza.json
│       ├── modelo_metricas.json
│       └── modelo_sequedad.pkl
└── web/
    ├── manage.py
    ├── agrodatalab/           # configuración Django
    ├── enviropro/             # app: modelos, vistas, urls, comandos
    ├── templates/             # base.html, registration/, enviropro/
    └── static/css/estilos.css
```

## Dataset EnviroPro analizado

- **20.284 registros** desde **2024-01-01** hasta **2026-04-29**.
- Cadencia mediana: **1 hora**.
- 8 sensores de humedad media + 8 de temperatura (con max/min) + batería + panel solar.

## Variables analizadas

| Bloque        | Columnas finales normalizadas                              |
|---------------|-----------------------------------------------------------|
| Tiempo        | `fecha_hora`                                              |
| Humedad       | `humedad_s1_media` ... `humedad_s8_media`                  |
| Temperatura   | `temp_s1_media`, `temp_s1_max`, `temp_s1_min` ... `s8`     |
| Energía       | `bateria_mv`, `panel_solar_mv`, `bateria_v`, `panel_solar_v` |
| Indicadores   | `humedad_media_global`, `temp_media_global`, `humedad_rango`, `temp_rango` |

## Instrucciones — ejecutar el análisis

```bash
pip install -r requirements.txt
python analisis/main.py
```

Salidas generadas en `analisis/salidas/` y `analisis/graficas/`.

Para abrir el notebook narrativo:

```bash
jupyter notebook analisis/notebook_analisis.ipynb
```

## Instrucciones — ejecutar la aplicación Django

```bash
cd web/
python manage.py migrate
python manage.py poblar_bbdd --solo-resumen   # 1 lectura por día (~850)
python manage.py runserver
```

Abrir <http://127.0.0.1:8000/>. Para entrar en el panel `/admin/` y editar
recomendaciones desde la web hace falta un usuario con permisos:

```bash
python manage.py createsuperuser
```

Usuario de prueba precargado (si se importa la BD de la demo):

- **usuario:** `demo`
- **contraseña:** `DemoAgro2026`

## URL pública del proyecto

> **URL pública pendiente de despliegue.** El proyecto está preparado para
> Render, Railway o PythonAnywhere mediante variables de entorno
> (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`,
> opcionalmente `DATABASE_URL` para Postgres).

## Enlace al vídeo

> **Pendiente de grabación.** Ver `docs/guion_video.md` para el guion
> detallado (8 minutos).

## Principales conclusiones

1. La humedad media global presenta **estacionalidad** clara (caídas en verano,
   recuperación en invierno y primavera) y correlación negativa moderada con la
   temperatura media del suelo (`r ≈ -0.45`).
2. Los **sensores superficiales** muestran más volatilidad y outliers; los
   profundos están amortiguados por la inercia térmica del suelo.
3. El nodo presenta **caídas de batería** correlacionadas con periodos de
   baja producción solar; se generan 46 alertas críticas de batería baja.
4. El **modelo predictivo** de sequedad relativa logra **recall 1.0** con
   precisión baja (~11%): prioriza no perder eventos críticos a costa de falsos
   positivos. Es adecuado como alerta temprana, no como decisión definitiva.
5. El sistema produce **1.824 alertas** clasificadas en 9 tipos, todas con
   recomendaciones prudentes asociadas (no se emiten órdenes agronómicas).

## Limitaciones

- El dataset no incluye **tipo de cultivo, riego real, lluvia local ni
  profundidad exacta** de los sensores. Las recomendaciones se formulan
  siempre en términos de **riesgo relativo**.
- El modelo predictivo se basa solo en datos EnviroPro; incorporar
  IFAPA-RIA mejoraría la precisión.
- Cadencia horaria limita la detección de eventos sub-horarios.

## Mejoras futuras

- Integrar la API REST de IFAPA-RIA en producción.
- Probar modelos no lineales (Random Forest, Gradient Boosting).
- Notificaciones push (Telegram/email) para alertas críticas.
- Calibración de sensores con medidas agronómicas de referencia.

## Ampliación: comparación con IFAPA-RIA

La sección final del notebook (apartado 13) documenta cómo realizar la
ampliación opcional con la **Estación Meteorológica de Belmez** (Córdoba,
código 1):

- **Fuente:** API REST de la Red de Información Agroclimática de Andalucía.
- **Variables comparadas:** precipitación, ETo, radiación, temperatura media
  y humedad relativa frente a humedad/temperatura del suelo EnviroPro.
- **Periodo:** 2024-01-01 → 2026-04-29.
- **Limitaciones:** EnviroPro mide el suelo, IFAPA mide el aire; las
  variables son **complementarias, no equivalentes**. ETo se utiliza solo
  como variable de contexto, no para calcular riego.

La ampliación pertenece **únicamente** al módulo de análisis. No se
integra en la aplicación Django.
