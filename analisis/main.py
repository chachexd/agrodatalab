"""
main.py
=======

Script principal del módulo de análisis de **AgroDataLab EnviroPro**.

Ejecuta el pipeline completo, genera todas las gráficas obligatorias del
enunciado (apartado A9, al menos 10 visualizaciones), entrena un modelo
predictivo sencillo (apartado B3), evalúa el modelo con separación
cronológica (apartado B4) y exporta todos los artefactos necesarios
para que la aplicación Django pueda consumirlos.

Salidas (en ``analisis/salidas/`` y ``analisis/graficas/``):

* ``enviropro_limpio.csv`` — dataset normalizado y limpio.
* ``enviropro_diario.csv`` — resumen diario.
* ``alertas.csv`` — alertas generadas con recomendaciones asociadas.
* ``indicadores_resumen.json`` — KPIs globales para el dashboard.
* ``informe_limpieza.json`` — métricas del proceso de limpieza.
* ``modelo_sequedad.pkl`` — modelo predictivo entrenado.
* ``modelo_metricas.json`` — métricas de evaluación del modelo.
* ``graficas/*.png`` — 12 visualizaciones interpretadas.

Uso::

    python analisis/main.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.preprocessing import StandardScaler

# Permitir ejecutar el script tanto como módulo (-m) como directamente.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analizador import (  # noqa: E402
    columnas_humedad,
    columnas_temp,
    ejecutar_pipeline,
)


RUTA_CSV = ROOT / "datos" / "enviropro_raw.csv"
DIR_SALIDA = ROOT / "salidas"
DIR_GRAFICAS = ROOT / "graficas"


def _guardar_grafica(fig: plt.Figure, nombre: str) -> Path:
    """Guarda una figura en ``analisis/graficas/`` y la cierra."""
    DIR_GRAFICAS.mkdir(parents=True, exist_ok=True)
    ruta = DIR_GRAFICAS / nombre
    fig.tight_layout()
    fig.savefig(ruta, dpi=110)
    plt.close(fig)
    return ruta


def generar_graficas(df: pd.DataFrame, alertas: pd.DataFrame, diario: pd.DataFrame) -> list[Path]:
    """Produce las 12 visualizaciones del apartado A9 del enunciado.

    Cada gráfica se acompaña de una interpretación escrita en el
    notebook y en el README final.
    """
    rutas: list[Path] = []
    plt.rcParams.update({"figure.figsize": (10, 4.5), "axes.grid": True})

    # 1. Línea temporal de humedad media global.
    fig, ax = plt.subplots()
    ax.plot(df["fecha_hora"], df["humedad_media_global"], color="#2b7a78", lw=0.8)
    ax.set_title("1. Evolución temporal de la humedad media del suelo")
    ax.set_xlabel("Fecha"); ax.set_ylabel("Humedad media (%)")
    rutas.append(_guardar_grafica(fig, "01_humedad_temporal.png"))

    # 2. Línea temporal de temperatura media global.
    fig, ax = plt.subplots()
    ax.plot(df["fecha_hora"], df["temp_media_global"], color="#d95d39", lw=0.8)
    ax.set_title("2. Evolución temporal de la temperatura media del suelo")
    ax.set_xlabel("Fecha"); ax.set_ylabel("Temperatura media (°C)")
    rutas.append(_guardar_grafica(fig, "02_temperatura_temporal.png"))

    # 3. Línea temporal de batería (V).
    fig, ax = plt.subplots()
    ax.plot(df["fecha_hora"], df["bateria_v"], color="#3a506b", lw=0.8)
    ax.set_title("3. Evolución temporal de la batería del nodo (V)")
    ax.set_xlabel("Fecha"); ax.set_ylabel("Batería (V)")
    rutas.append(_guardar_grafica(fig, "03_bateria_temporal.png"))

    # 4. Línea temporal del panel solar (V).
    fig, ax = plt.subplots()
    ax.plot(df["fecha_hora"], df["panel_solar_v"], color="#f4a261", lw=0.7)
    ax.set_title("4. Evolución temporal del panel solar (V)")
    ax.set_xlabel("Fecha"); ax.set_ylabel("Panel solar (V)")
    rutas.append(_guardar_grafica(fig, "04_panel_solar_temporal.png"))

    # 5. Comparación de humedad media por sensor (boxplot).
    hum_cols = columnas_humedad(df)
    fig, ax = plt.subplots()
    df[hum_cols].plot.box(ax=ax)
    ax.set_title("5. Distribución de humedad por sensor")
    ax.set_ylabel("Humedad (%)")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    rutas.append(_guardar_grafica(fig, "05_humedad_por_sensor_box.png"))

    # 6. Comparación de temperatura media por sensor (boxplot).
    t_cols = columnas_temp(df, "media")
    fig, ax = plt.subplots()
    df[t_cols].plot.box(ax=ax)
    ax.set_title("6. Distribución de temperatura media por sensor")
    ax.set_ylabel("Temperatura (°C)")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    rutas.append(_guardar_grafica(fig, "06_temp_por_sensor_box.png"))

    # 7. Evolución diaria de humedad (media, min y max diarios).
    fig, ax = plt.subplots()
    ax.plot(diario["fecha"], diario["humedad_media_dia"], label="Media", lw=1.1)
    ax.fill_between(diario["fecha"], diario["humedad_min_dia"], diario["humedad_max_dia"],
                     alpha=0.2, label="Rango (min-max)")
    ax.set_title("7. Evolución diaria de la humedad (banda min-max)")
    ax.set_xlabel("Fecha"); ax.set_ylabel("Humedad (%)"); ax.legend()
    rutas.append(_guardar_grafica(fig, "07_humedad_diaria.png"))

    # 8. Evolución diaria de la temperatura del suelo.
    fig, ax = plt.subplots()
    ax.plot(diario["fecha"], diario["temp_suelo_media_dia"], color="#bc4749", label="Media")
    if "temp_suelo_min_dia" in diario and "temp_suelo_max_dia" in diario:
        ax.fill_between(diario["fecha"], diario["temp_suelo_min_dia"],
                         diario["temp_suelo_max_dia"], alpha=0.2, color="#bc4749",
                         label="Rango (min-max)")
    ax.set_title("8. Evolución diaria de la temperatura del suelo")
    ax.set_xlabel("Fecha"); ax.set_ylabel("Temperatura (°C)"); ax.legend()
    rutas.append(_guardar_grafica(fig, "08_temperatura_diaria.png"))

    # 9. Correlación entre humedad media y temperatura media (heatmap simple).
    cols_corr = ["humedad_media_global", "temp_media_global", "bateria_v", "panel_solar_v"]
    corr = df[cols_corr].corr()
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols_corr))); ax.set_yticks(range(len(cols_corr)))
    ax.set_xticklabels(cols_corr, rotation=30, ha="right"); ax.set_yticklabels(cols_corr)
    for (i, j), val in np.ndenumerate(corr.values):
        ax.text(j, i, f"{val:.2f}", ha="center", va="center", color="black", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title("9. Correlaciones entre variables")
    rutas.append(_guardar_grafica(fig, "09_correlaciones.png"))

    # 10. Dispersión humedad media vs temperatura media (color por hora).
    fig, ax = plt.subplots()
    horas = df["fecha_hora"].dt.hour
    sc = ax.scatter(df["humedad_media_global"], df["temp_media_global"],
                    c=horas, cmap="twilight", s=4, alpha=0.5)
    ax.set_xlabel("Humedad media (%)"); ax.set_ylabel("Temperatura media (°C)")
    ax.set_title("10. Dispersión humedad vs temperatura (color = hora del día)")
    fig.colorbar(sc, ax=ax, label="Hora del día")
    rutas.append(_guardar_grafica(fig, "10_dispersion_humedad_temp.png"))

    # 11. Alertas por día.
    if not alertas.empty:
        alertas_dia = (
            alertas.assign(fecha=pd.to_datetime(alertas["fecha_hora"]).dt.date)
            .groupby("fecha").size()
        )
        fig, ax = plt.subplots()
        ax.bar(alertas_dia.index, alertas_dia.values, color="#a4243b")
        ax.set_title("11. Alertas generadas por día")
        ax.set_xlabel("Fecha"); ax.set_ylabel("Nº de alertas")
        rutas.append(_guardar_grafica(fig, "11_alertas_por_dia.png"))
    else:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "Sin alertas", ha="center", va="center", fontsize=16)
        ax.set_axis_off()
        rutas.append(_guardar_grafica(fig, "11_alertas_por_dia.png"))

    # 12. Valores nulos por columna.
    nulos = df.isna().sum().sort_values(ascending=False).head(20)
    fig, ax = plt.subplots(figsize=(9, 5))
    nulos.plot.barh(ax=ax, color="#6a8d92")
    ax.invert_yaxis()
    ax.set_title("12. Top columnas con más valores nulos")
    ax.set_xlabel("Nº de NaN")
    rutas.append(_guardar_grafica(fig, "12_nulos_por_columna.png"))

    return rutas


# ---------------------------------------------------------------------------
# Modelo predictivo (apartado B3, opción A: clasificación)
# ---------------------------------------------------------------------------

def entrenar_modelo(df: pd.DataFrame, alertas: pd.DataFrame) -> dict:
    """Entrena un clasificador que predice una alerta de sequedad próxima.

    Variable objetivo
    -----------------
    ``y = 1`` si en las próximas 6 horas (6 lecturas) el sistema generaría
    una alerta de ``sequedad_relativa``; ``y = 0`` en caso contrario.

    Features
    --------
    Humedad media global, temperatura media global, batería en mV,
    panel solar en mV, rango de humedad y rango térmico actual,
    media móvil de humedad en las últimas 6 lecturas, y diferencia
    de humedad respecto a la lectura anterior.

    Evaluación
    ----------
    Se utiliza separación cronológica 80% / 20% (sin shuffle) para
    respetar el carácter de serie temporal, tal como pide el enunciado.
    Se reportan accuracy, precision, recall, F1 y matriz de confusión.

    Returns
    -------
    dict
        Diccionario con métricas serializables a JSON.
    """
    df = df.sort_values("fecha_hora").reset_index(drop=True).copy()

    # Construcción del target a partir de los DÍAS marcados con alerta de
    # sequedad relativa. Una fila se considera "previa a alerta" si en los
    # próximos 3 días (~72 lecturas con cadencia horaria) hay alerta.
    dias_alerta = set(
        pd.to_datetime(alertas.loc[alertas["tipo"] == "sequedad_relativa",
                                    "fecha_hora"]).dt.date
    ) if not alertas.empty else set()

    df["fecha"] = df["fecha_hora"].dt.date
    df["dia_es_alerta"] = df["fecha"].isin(dias_alerta).astype(int)
    # Marcar como objetivo positivo aquellas filas que están en los días
    # previos a un día con alerta (ventana de 3 días).
    fechas_unicas = sorted(df["fecha"].unique())
    dias_objetivo = set()
    for i, d in enumerate(fechas_unicas):
        ventana = fechas_unicas[i + 1 : i + 4]  # próximos 3 días
        if any(v in dias_alerta for v in ventana):
            dias_objetivo.add(d)
    df["target"] = df["fecha"].isin(dias_objetivo).astype(int)

    # Features
    df["humedad_media_6h"] = df["humedad_media_global"].rolling(6).mean()
    df["humedad_delta"] = df["humedad_media_global"].diff()
    feats = [
        "humedad_media_global", "temp_media_global",
        "bateria_mv", "panel_solar_mv",
        "humedad_rango", "temp_rango",
        "humedad_media_6h", "humedad_delta",
    ]
    feats = [c for c in feats if c in df.columns]
    df_modelo = df[feats + ["target"]].dropna().copy()

    if df_modelo["target"].nunique() < 2 or len(df_modelo) < 100:
        return {
            "estado": "no_entrenado",
            "motivo": (
                "No hay alertas suficientes para entrenar (target con una sola clase) "
                "o pocos datos."
            ),
            "n_muestras": int(len(df_modelo)),
        }

    # Separación cronológica 80/20.
    corte = int(len(df_modelo) * 0.8)
    X_train, X_test = df_modelo.iloc[:corte][feats], df_modelo.iloc[corte:][feats]
    y_train, y_test = df_modelo.iloc[:corte]["target"], df_modelo.iloc[corte:]["target"]

    escalador = StandardScaler()
    X_train_e = escalador.fit_transform(X_train)
    X_test_e = escalador.transform(X_test)

    modelo = LogisticRegression(max_iter=500, class_weight="balanced")
    modelo.fit(X_train_e, y_train)
    y_pred = modelo.predict(X_test_e)

    # Persistir modelo + escalador como un único pipeline pickle.
    DIR_SALIDA.mkdir(parents=True, exist_ok=True)
    joblib.dump({"modelo": modelo, "escalador": escalador, "features": feats},
                DIR_SALIDA / "modelo_sequedad.pkl")

    metricas = {
        "estado": "entrenado",
        "tipo": "clasificacion_logistic_regression",
        "features": feats,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "matriz_confusion": confusion_matrix(y_test, y_pred).tolist(),
        "reporte_texto": classification_report(y_test, y_pred, zero_division=0),
    }
    return metricas


# ---------------------------------------------------------------------------
# Indicadores resumen para el dashboard Django
# ---------------------------------------------------------------------------

def construir_resumen(df: pd.DataFrame, alertas: pd.DataFrame) -> dict:
    """Crea el JSON de KPIs que consume el dashboard de la web."""
    def _safe(valor):
        if pd.isna(valor):
            return None
        return float(valor) if isinstance(valor, (int, float, np.floating)) else valor

    resumen = {
        "total_registros": int(len(df)),
        "fecha_primera_lectura": df["fecha_hora"].min().isoformat() if len(df) else None,
        "fecha_ultima_lectura": df["fecha_hora"].max().isoformat() if len(df) else None,
        "humedad_media_global": _safe(df["humedad_media_global"].mean()),
        "humedad_min_global": _safe(df["humedad_min_global"].min()),
        "humedad_max_global": _safe(df["humedad_max_global"].max()),
        "temp_media_global": _safe(df["temp_media_global"].mean()),
        "temp_max_global": _safe(df["temp_max_global"].max()),
        "temp_min_global": _safe(df["temp_min_global"].min()),
        "bateria_media_v": _safe(df["bateria_v"].mean()),
        "panel_solar_media_v": _safe(df["panel_solar_v"].mean()),
        "n_alertas_total": int(len(alertas)),
        "n_alertas_sequedad": int((alertas["tipo"] == "sequedad_relativa").sum()) if len(alertas) else 0,
        "n_alertas_energeticas": int(
            alertas["tipo"].isin(["bateria_baja", "panel_solar_diurno_bajo"]).sum()
        ) if len(alertas) else 0,
        "n_alertas_temp_incoherente": int((alertas["tipo"] == "temp_incoherente").sum()) if len(alertas) else 0,
        "ultima_recomendacion": alertas.iloc[-1]["recomendacion"] if len(alertas) else None,
    }
    return resumen


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def main() -> None:
    """Ejecuta el pipeline completo y guarda todos los artefactos."""
    DIR_SALIDA.mkdir(parents=True, exist_ok=True)
    DIR_GRAFICAS.mkdir(parents=True, exist_ok=True)

    print(f">> Leyendo {RUTA_CSV}")
    resultado = ejecutar_pipeline(RUTA_CSV)
    print(f"   Registros iniciales : {resultado.informe.registros_iniciales}")
    print(f"   Registros finales   : {resultado.informe.registros_finales}")
    print(f"   Duplicados elim.    : {resultado.informe.duplicados_eliminados}")
    print(f"   Valores anulados    : {resultado.informe.valores_fuera_de_rango_anulados}")
    print(f"   Incoherencias temp. : {resultado.informe.incoherencias_temperatura}")
    print(f"   Huecos temporales   : {resultado.informe.huecos_temporales}")

    # Exportar CSVs limpios.
    resultado.df_indicadores.to_csv(DIR_SALIDA / "enviropro_limpio.csv", index=False)
    resultado.df_diario.to_csv(DIR_SALIDA / "enviropro_diario.csv", index=False)
    resultado.df_alertas.to_csv(DIR_SALIDA / "alertas.csv", index=False)
    print(f"   {len(resultado.df_alertas)} alertas guardadas en alertas.csv")

    # Resumen.
    resumen = construir_resumen(resultado.df_indicadores, resultado.df_alertas)
    (DIR_SALIDA / "indicadores_resumen.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    # Informe de limpieza.
    (DIR_SALIDA / "informe_limpieza.json").write_text(
        json.dumps(resultado.informe.como_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Gráficas obligatorias.
    rutas = generar_graficas(resultado.df_indicadores, resultado.df_alertas, resultado.df_diario)
    print(f"   {len(rutas)} gráficas generadas en {DIR_GRAFICAS}")

    # Modelo predictivo.
    metricas = entrenar_modelo(resultado.df_indicadores, resultado.df_alertas)
    (DIR_SALIDA / "modelo_metricas.json").write_text(
        json.dumps(metricas, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    if metricas.get("estado") == "entrenado":
        print(f"   Modelo entrenado. F1={metricas['f1']:.3f}, Acc={metricas['accuracy']:.3f}")
    else:        print(f"   Modelo no entrenado: {metricas.get('motivo')}")

    print(">> Pipeline completado correctamente.")


if __name__ == "__main__":
    main()
