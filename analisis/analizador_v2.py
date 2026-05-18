"""
analizador.py
=============

Módulo principal de análisis del proyecto **AgroDataLab EnviroPro**.

Contiene funciones reutilizables para:

* Importar el CSV original de EnviroPro (resistente a comas decimales,
  cabeceras dobles, BOM y encoding).
* Normalizar los nombres de columnas a un esquema corto y claro.
* Limpiar los datos (nulos, duplicados, valores imposibles, coherencia
  entre temperaturas mínima, promedio y máxima).
* Calcular indicadores agregados (humedad media, rango térmico, batería
  en voltios, niveles relativos, etc.).
* Generar el sistema de alertas mínimo descrito en el enunciado
  (sequedad relativa, humedad baja por sensor, subidas y caídas bruscas,
  temperatura alta, temperatura incoherente, batería baja, panel solar
  bajo en horario diurno, sensor bloqueado y huecos temporales).
* Resumir el dataset en formato diario para futuras comparaciones con
  IFAPA-RIA o para alimentar los modelos predictivos.

El módulo está pensado para usarse tanto desde el **notebook de análisis**
como desde la **aplicación Django**: la lógica de cálculo vive aquí y se
consume desde fuera, evitando duplicidades.

Las funciones no asumen un número fijo de registros: todo es relativo al
DataFrame que se proporciona, por lo que el pipeline funciona con nuevas
descargas del sensor.

Autor: Diego (proyecto intermodular Horizonte Verde Digital).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constantes de configuración
# ---------------------------------------------------------------------------

#: Número de sensores de humedad esperados en el dataset EnviroPro.
N_SENSORES_HUMEDAD = 8

#: Número de sensores de temperatura esperados.
N_SENSORES_TEMP = 8

#: Rango razonable de humedad relativa del suelo (porcentaje).
RANGO_HUMEDAD = (0.0, 100.0)

#: Rango razonable de temperatura del suelo en grados centígrados.
RANGO_TEMP = (-10.0, 60.0)

#: Rango razonable de batería en milivoltios.
RANGO_BATERIA_MV = (0.0, 15000.0)

#: Rango razonable de panel solar en milivoltios.
RANGO_PANEL_MV = (0.0, 25000.0)

#: Umbral por defecto para considerar batería baja (cuantil bajo del histórico).
UMBRAL_BATERIA_CUANTIL = 0.05

#: Cuantil que define humedad "baja" relativa (sequedad).
UMBRAL_HUMEDAD_BAJA_CUANTIL = 0.10

#: Cuantil que define temperatura "alta" relativa.
UMBRAL_TEMP_ALTA_CUANTIL = 0.90

#: Diferencia porcentual considerada subida o caída brusca entre lecturas
#: consecutivas (en puntos de humedad).
UMBRAL_VARIACION_HUMEDAD = 8.0

#: Si un sensor repite el mismo valor durante más de N lecturas consecutivas,
#: se considera "posiblemente bloqueado".
LECTURAS_BLOQUEO = 12  # ~12 horas con cadencia horaria

#: Horario diurno en el que se espera producción del panel solar.
HORA_DIURNA_INICIO = 9
HORA_DIURNA_FIN = 17

#: Valor mínimo esperado de panel solar en horario diurno (mV).
UMBRAL_PANEL_DIURNO_BAJO = 500.0


# ---------------------------------------------------------------------------
# 1. Importación
# ---------------------------------------------------------------------------

def importar_csv(ruta: str | Path) -> pd.DataFrame:
    """Importa el CSV original de EnviroPro tolerando varias rarezas reales.

    El dataset original puede llegar con:

    * BOM UTF-8 al inicio del archivo.
    * Coma decimal en lugar de punto.
    * Cabecera en una sola fila (versión consolidada) o en dos filas
      (versión original: la primera con el nombre y la segunda con el
      tipo de medida).

    La función detecta automáticamente cuál es el caso y devuelve un
    DataFrame con los nombres **originales** (sin normalizar). La
    normalización se aplica en :func:`normalizar_columnas`.

    Parameters
    ----------
    ruta : str | Path
        Ruta al CSV de entrada.

    Returns
    -------
    pandas.DataFrame
        DataFrame con los datos brutos, con la columna de fecha
        renombrada a ``fecha_hora`` y los valores numéricos parseados
        como float.
    """
    ruta = Path(ruta)
    # 1. Inspeccionar el separador decimal leyendo unas líneas.
    with open(ruta, "r", encoding="utf-8-sig", errors="replace") as f:
        muestra = "".join([next(f, "") for _ in range(5)])

    # Si en la muestra encontramos números con coma decimal entre comillas
    # tipo "12,34" usamos decimal=","; si vemos "12.34" usamos decimal=".".
    coma_decimal = bool(re.search(r"\d+,\d+", muestra))
    decimal = "," if coma_decimal else "."

    # 2. Detectar cabecera doble: si las dos primeras filas tras la
    # cabecera son texto en lugar de números, asumimos cabecera en
    # dos filas (la 2ª fila describe "promedio/máx/mín/última").
    df_test = pd.read_csv(ruta, encoding="utf-8-sig", nrows=2, sep=",")
    cabecera_doble = df_test.iloc[0].astype(str).str.match(
        r"^(promedio|m[aá]ximo|m[ií]nimo|[uú]ltima)", case=False
    ).any()

    if cabecera_doble:
        df = pd.read_csv(
            ruta,
            encoding="utf-8-sig",
            sep=",",
            header=[0, 1],
            decimal=decimal,
        )
        # Aplanar el MultiIndex uniendo nombre y tipo con " - ".
        df.columns = [
            f"{a.strip()} - {b.strip()}" if "Unnamed" not in str(b) else a.strip()
            for a, b in df.columns
        ]
    else:
        df = pd.read_csv(
            ruta,
            encoding="utf-8-sig",
            sep=",",
            decimal=decimal,
        )

    # 3. Renombrar la primera columna de fecha si llega con cualquier variante.
    primera = df.columns[0]
    df = df.rename(columns={primera: "fecha_hora"})

    # 4. Si los números siguen como cadena (por ejemplo, comas no detectadas),
    # forzar conversión a float reemplazando comas.
    for col in df.columns:
        if col == "fecha_hora":
            continue
        if df[col].dtype == object:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", ".", regex=False)
                .replace({"nan": np.nan, "": np.nan})
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 5. Parsear fechas.
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# 2. Normalización de columnas
# ---------------------------------------------------------------------------

# Diccionario para detectar el tipo de medida a partir del sufijo del nombre.
_MAPEO_MEDIDA = {
    "promedio": "media",
    "media": "media",
    "máx": "max",
    "max": "max",
    "máximo": "max",
    "maximo": "max",
    "mín": "min",
    "min": "min",
    "mínimo": "min",
    "minimo": "min",
    "última": "ultima",
    "ultima": "ultima",
}


def _detectar_medida(sufijo: str) -> str:
    sufijo = sufijo.lower().strip()
    for clave, valor in _MAPEO_MEDIDA.items():
        if clave in sufijo:
            return valor
    return sufijo.replace(" ", "_")


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas de EnviroPro a un esquema corto y claro.

    Esquema de salida (ejemplos):

    * ``fecha_hora`` — marca temporal.
    * ``humedad_s1_media`` ... ``humedad_s8_media``.
    * ``temp_s1_media``, ``temp_s1_max``, ``temp_s1_min``.
    * ``bateria_mv``, ``panel_solar_mv``.

    Los nombres se ajustan a las recomendaciones del enunciado del
    proyecto (apartado A2). No se eliminan columnas: si el dataset
    contiene una variante desconocida se conserva su nombre original
    saneado.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame tal como lo devuelve :func:`importar_csv`.

    Returns
    -------
    pandas.DataFrame
        Nuevo DataFrame con las columnas renombradas.
    """
    nuevos = {}
    for col in df.columns:
        if col == "fecha_hora":
            nuevos[col] = "fecha_hora"
            continue

        original = col

        # Humedad: "EnviroPro, sensor de humedad del suelo  N [%] - sufijo".
        m_hum = re.search(r"humedad.*?(\d+).*?-\s*(.+)$", original, re.IGNORECASE)
        if m_hum:
            idx = int(m_hum.group(1))
            medida = _detectar_medida(m_hum.group(2))
            nuevos[col] = f"humedad_s{idx}_{medida}"
            continue

        # Temperatura: "EnviroPro, sensor de temperatura del suelo  N [°C] - sufijo".
        m_tmp = re.search(r"temperatura.*?(\d+).*?-\s*(.+)$", original, re.IGNORECASE)
        if m_tmp:
            idx = int(m_tmp.group(1))
            medida = _detectar_medida(m_tmp.group(2))
            nuevos[col] = f"temp_s{idx}_{medida}"
            continue

        # Batería y panel solar: "Batería [mV] - última", "Panel solar [mV] - última".
        if re.search(r"bater[ií]a", original, re.IGNORECASE):
            nuevos[col] = "bateria_mv"
            continue
        if re.search(r"panel\s*solar", original, re.IGNORECASE):
            nuevos[col] = "panel_solar_mv"
            continue

        # Fallback: minúsculas, sin acentos básicos, espacios a guión bajo.
        slug = (
            original.lower()
            .replace("á", "a").replace("é", "e").replace("í", "i")
            .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
        )
        slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
        nuevos[col] = slug

    return df.rename(columns=nuevos).copy()


# ---------------------------------------------------------------------------
# 3. Listas dinámicas de columnas
# ---------------------------------------------------------------------------

def columnas_humedad(df: pd.DataFrame) -> list[str]:
    """Devuelve la lista de columnas de humedad media disponibles."""
    return sorted([c for c in df.columns if re.fullmatch(r"humedad_s\d+_media", c)])


def columnas_temp(df: pd.DataFrame, tipo: str = "media") -> list[str]:
    """Devuelve la lista de columnas de temperatura del tipo indicado.

    Parameters
    ----------
    tipo : str
        ``"media"``, ``"max"`` o ``"min"``.
    """
    return sorted([c for c in df.columns if re.fullmatch(rf"temp_s\d+_{tipo}", c)])


# ---------------------------------------------------------------------------
# 4. Limpieza y preparación
# ---------------------------------------------------------------------------

@dataclass
class InformeLimpieza:
    """Resumen estructurado de las decisiones tomadas durante la limpieza.

    Atributos
    ---------
    registros_iniciales : int
        Filas del dataset al entrar en la función.
    registros_finales : int
        Filas tras la limpieza.
    duplicados_eliminados : int
    fechas_invalidas_eliminadas : int
    valores_fuera_de_rango_anulados : int
        Valores que se han convertido a NaN por estar fuera de rango.
    incoherencias_temperatura : int
        Filas en las que ``min > promedio`` o ``promedio > max`` en algún
        sensor de temperatura.
    huecos_temporales : int
        Saltos temporales detectados (registros faltantes respecto a la
        cadencia mediana).
    """
    registros_iniciales: int
    registros_finales: int
    duplicados_eliminados: int
    fechas_invalidas_eliminadas: int
    valores_fuera_de_rango_anulados: int
    incoherencias_temperatura: int
    huecos_temporales: int

    def como_dict(self) -> dict:
        """Devuelve la información como diccionario serializable."""
        return self.__dict__


def limpiar(df: pd.DataFrame) -> tuple[pd.DataFrame, InformeLimpieza]:
    """Limpia el dataset siguiendo el apartado A3 del enunciado.

    Pasos aplicados:

    1. Eliminar registros con fecha nula o no parseable.
    2. Ordenar cronológicamente.
    3. Eliminar duplicados exactos y duplicados por fecha (conservando
       la primera lectura para no perder información).
    4. Convertir a NaN los valores fuera de los rangos físicos
       razonables (sin eliminar la fila completa).
    5. Detectar incoherencias entre temperatura mínima, promedio y
       máxima (no se modifican, se cuentan para el informe).
    6. Detectar huecos temporales respecto a la cadencia mediana.

    El motivo de no eliminar valores anómalos sino marcarlos como NaN
    es preservar las filas para el análisis temporal: el enunciado pide
    explícitamente justificar cada eliminación.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame normalizado.

    Returns
    -------
    tuple
        ``(df_limpio, informe)`` con el DataFrame procesado y el
        :class:`InformeLimpieza` con las cifras de la operación.
    """
    n0 = len(df)
    fechas_invalidas = df["fecha_hora"].isna().sum()
    df = df.dropna(subset=["fecha_hora"]).copy()

    # Orden cronológico y duplicados.
    df = df.sort_values("fecha_hora").reset_index(drop=True)
    duplicados = df.duplicated(subset=["fecha_hora"]).sum()
    df = df.drop_duplicates(subset=["fecha_hora"], keep="first").reset_index(drop=True)

    # Valores fuera de rango -> NaN.
    fuera_rango = 0
    for col in columnas_humedad(df):
        mask = (df[col] < RANGO_HUMEDAD[0]) | (df[col] > RANGO_HUMEDAD[1])
        fuera_rango += int(mask.sum())
        df.loc[mask, col] = np.nan
    for tipo in ("media", "max", "min"):
        for col in columnas_temp(df, tipo):
            mask = (df[col] < RANGO_TEMP[0]) | (df[col] > RANGO_TEMP[1])
            fuera_rango += int(mask.sum())
            df.loc[mask, col] = np.nan
    if "bateria_mv" in df:
        mask = (df["bateria_mv"] < RANGO_BATERIA_MV[0]) | (
            df["bateria_mv"] > RANGO_BATERIA_MV[1]
        )
        fuera_rango += int(mask.sum())
        df.loc[mask, "bateria_mv"] = np.nan
    if "panel_solar_mv" in df:
        mask = (df["panel_solar_mv"] < RANGO_PANEL_MV[0]) | (
            df["panel_solar_mv"] > RANGO_PANEL_MV[1]
        )
        fuera_rango += int(mask.sum())
        df.loc[mask, "panel_solar_mv"] = np.nan

    # Incoherencias de temperatura por sensor.
    incoherencias = 0
    for i in range(1, N_SENSORES_TEMP + 1):
        c_min, c_med, c_max = (f"temp_s{i}_min", f"temp_s{i}_media", f"temp_s{i}_max")
        if {c_min, c_med, c_max}.issubset(df.columns):
            mask = (df[c_min] > df[c_med]) | (df[c_med] > df[c_max])
            incoherencias += int(mask.fillna(False).sum())

    # Huecos temporales respecto a la cadencia mediana.
    diff_min = df["fecha_hora"].diff().dt.total_seconds().div(60)
    cadencia = diff_min.median()
    huecos = int(((diff_min > 1.5 * cadencia) & diff_min.notna()).sum()) if cadencia else 0

    informe = InformeLimpieza(
        registros_iniciales=n0,
        registros_finales=len(df),
        duplicados_eliminados=int(duplicados),
        fechas_invalidas_eliminadas=int(fechas_invalidas),
        valores_fuera_de_rango_anulados=int(fuera_rango),
        incoherencias_temperatura=int(incoherencias),
        huecos_temporales=int(huecos),
    )
    return df, informe


# ---------------------------------------------------------------------------
# 5. Indicadores
# ---------------------------------------------------------------------------

def calcular_indicadores(df: pd.DataFrame) -> pd.DataFrame:
    """Añade al DataFrame columnas de indicadores agregados por fila.

    Indicadores añadidos:

    * ``humedad_media_global`` — media de todos los sensores de humedad.
    * ``humedad_min_global`` — mínimo entre sensores.
    * ``humedad_max_global`` — máximo entre sensores.
    * ``humedad_rango`` — diferencia entre máximo y mínimo.
    * ``temp_media_global`` — media de las temperaturas medias.
    * ``temp_min_global`` — mínimo entre las temperaturas mínimas.
    * ``temp_max_global`` — máximo entre las temperaturas máximas.
    * ``temp_rango`` — rango térmico (máximo - mínimo) por fila.
    * ``bateria_v`` y ``panel_solar_v`` — conversión a voltios para
      facilitar la lectura humana (ver enunciado A8).
    """
    out = df.copy()
    hum = columnas_humedad(out)
    if hum:
        out["humedad_media_global"] = out[hum].mean(axis=1)
        out["humedad_min_global"] = out[hum].min(axis=1)
        out["humedad_max_global"] = out[hum].max(axis=1)
        out["humedad_rango"] = out["humedad_max_global"] - out["humedad_min_global"]

    tmedia = columnas_temp(out, "media")
    tmin = columnas_temp(out, "min")
    tmax = columnas_temp(out, "max")
    if tmedia:
        out["temp_media_global"] = out[tmedia].mean(axis=1)
    if tmin:
        out["temp_min_global"] = out[tmin].min(axis=1)
    if tmax:
        out["temp_max_global"] = out[tmax].max(axis=1)
    if tmin and tmax:
        out["temp_rango"] = out["temp_max_global"] - out["temp_min_global"]

    if "bateria_mv" in out:
        out["bateria_v"] = out["bateria_mv"] / 1000.0
    if "panel_solar_mv" in out:
        out["panel_solar_v"] = out["panel_solar_mv"] / 1000.0
    return out


# ---------------------------------------------------------------------------
# 6. Sistema de alertas (apartado B del enunciado)
# ---------------------------------------------------------------------------

@dataclass
class Alerta:
    """Representación canónica de una alerta generada por el sistema."""
    fecha_hora: pd.Timestamp
    tipo: str
    nivel: str  # "info" | "aviso" | "critico"
    variable: str
    descripcion: str
    recomendacion: str

    def como_dict(self) -> dict:
        d = self.__dict__.copy()
        d["fecha_hora"] = self.fecha_hora.isoformat() if pd.notna(self.fecha_hora) else None
        return d


def _serie_relativa(serie: pd.Series, cuantil_bajo: float, cuantil_alto: float
                    ) -> tuple[float, float]:
    """Devuelve los valores umbral (bajo, alto) basados en cuantiles."""
    s = serie.dropna()
    if s.empty:
        return (np.nan, np.nan)
    return (float(s.quantile(cuantil_bajo)), float(s.quantile(cuantil_alto)))


def generar_alertas(df: pd.DataFrame) -> pd.DataFrame:
    """Genera todas las alertas mínimas del apartado B1 del enunciado.

    La función trabaja contra un DataFrame que ya tenga indicadores
    (ver :func:`calcular_indicadores`). Las alertas se devuelven como
    DataFrame con una fila por alerta detectada.

    Tipos de alerta producidos:

    ``sequedad_relativa``
        Humedad media baja respecto al histórico **y** temperatura
        media alta respecto al histórico, en la misma lectura.

    ``humedad_baja_sensor``
        Un sensor concreto cae por debajo del cuantil 10% de su propio
        histórico.

    ``subida_brusca_humedad`` / ``caida_brusca_humedad``
        Variación entre lecturas consecutivas superior a
        :data:`UMBRAL_VARIACION_HUMEDAD` puntos porcentuales.

    ``temp_alta_relativa``
        Temperatura media global por encima del cuantil 90% histórico.

    ``temp_incoherente``
        Una lectura donde ``min > promedio`` o ``promedio > max`` en
        cualquier sensor.

    ``bateria_baja``
        Valor de batería por debajo del cuantil 5% histórico.

    ``panel_solar_diurno_bajo``
        Valor de panel solar muy bajo en horario diurno (apartado A8).

    ``sensor_bloqueado``
        Mismo valor exacto durante más de
        :data:`LECTURAS_BLOQUEO` lecturas consecutivas en un sensor.

    ``hueco_temporal``
        Salto temporal mayor a 1.5 veces la cadencia mediana.

    Returns
    -------
    pandas.DataFrame
        Columnas: ``fecha_hora``, ``tipo``, ``nivel``, ``variable``,
        ``descripcion``, ``recomendacion``.
    """
    alertas: list[Alerta] = []
    if df.empty:
        return pd.DataFrame(columns=["fecha_hora", "tipo", "nivel", "variable",
                                     "descripcion", "recomendacion"])

    df = df.sort_values("fecha_hora").reset_index(drop=True)

    # Umbrales relativos al histórico de la propia serie cargada.
    hum_low, hum_high = _serie_relativa(df.get("humedad_media_global", pd.Series(dtype=float)),
                                         UMBRAL_HUMEDAD_BAJA_CUANTIL,
                                         1 - UMBRAL_HUMEDAD_BAJA_CUANTIL)
    temp_low, temp_high = _serie_relativa(df.get("temp_media_global", pd.Series(dtype=float)),
                                           1 - UMBRAL_TEMP_ALTA_CUANTIL,
                                           UMBRAL_TEMP_ALTA_CUANTIL)
    bat_low, _ = _serie_relativa(df.get("bateria_mv", pd.Series(dtype=float)),
                                 UMBRAL_BATERIA_CUANTIL, 1 - UMBRAL_BATERIA_CUANTIL)

    # Para la alerta "sequedad relativa" se relajan los cuantiles porque, en
    # un histórico real, la coincidencia exacta de humedad <= cuantil 10 y
    # temperatura >= cuantil 90 es muy infrecuente (se trata de variables
    # estacionales con correlación inversa). Se utilizan cuantiles 30/70 para
    # que el sistema pueda señalar periodos secos relativos sin saturar.
    hum_low_seq, _ = _serie_relativa(df.get("humedad_media_global", pd.Series(dtype=float)),
                                      0.30, 0.70)
    _, temp_high_seq = _serie_relativa(df.get("temp_media_global", pd.Series(dtype=float)),
                                        0.30, 0.70)

    # ---- 1. Sequedad relativa: una alerta por DÍA en el que la condición
    #         se cumpla en alguna lectura. Esto evita ruido de miles de
    #         alertas por hora durante un periodo seco prolongado.
    if "humedad_media_global" in df and "temp_media_global" in df and not np.isnan(hum_low_seq):
        mask = (df["humedad_media_global"] <= hum_low_seq) & (df["temp_media_global"] >= temp_high_seq)
        dias = df.loc[mask].assign(_dia=df.loc[mask, "fecha_hora"].dt.date)
        for dia, grupo in dias.groupby("_dia"):
            peor = grupo.loc[grupo["humedad_media_global"].idxmin()]
            alertas.append(Alerta(
                fecha_hora=peor["fecha_hora"],
                tipo="sequedad_relativa",
                nivel="aviso",
                variable="humedad_media_global",
                descripcion=(
                    f"Día {dia}: humedad mínima del día {peor['humedad_media_global']:.1f}% "
                    f"(entre las más bajas del histórico) y temperatura "
                    f"{peor['temp_media_global']:.1f}°C entre las más altas. "
                    f"{len(grupo)} lecturas afectadas."
                ),
                recomendacion=(
                    "Revisar la zona monitorizada y contrastar con el equipo agrario "
                    "antes de tomar decisiones de riego."
                ),
            ))

    # ---- 2. Humedad muy baja por sensor: una alerta por sensor y por día.
    for col in columnas_humedad(df):
        serie = df[col].dropna()
        if serie.empty:
            continue
        umbral = serie.quantile(UMBRAL_HUMEDAD_BAJA_CUANTIL)
        mask = df[col] <= umbral
        if not mask.any():
            continue
        dias = df.loc[mask].assign(_dia=df.loc[mask, "fecha_hora"].dt.date)
        for dia, grupo in dias.groupby("_dia"):
            peor = grupo.loc[grupo[col].idxmin()]
            alertas.append(Alerta(
                fecha_hora=peor["fecha_hora"],
                tipo="humedad_baja_sensor",
                nivel="info",
                variable=col,
                descripcion=(
                    f"Día {dia}: el {col} registró un mínimo de {peor[col]:.1f}% "
                    f"(<= cuantil 10% del histórico, {umbral:.1f}%). "
                    f"{len(grupo)} lecturas por debajo del umbral."
                ),
                recomendacion="Comprobar la zona o profundidad asociada al sensor.",
            ))

    # ---- 3. Subidas y caídas bruscas de humedad ----
    if "humedad_media_global" in df:
        diff = df["humedad_media_global"].diff()
        for idx, valor in diff.items():
            if pd.isna(valor):
                continue
            if valor >= UMBRAL_VARIACION_HUMEDAD:
                alertas.append(Alerta(
                    fecha_hora=df.loc[idx, "fecha_hora"],
                    tipo="subida_brusca_humedad",
                    nivel="aviso",
                    variable="humedad_media_global",
                    descripcion=(
                        f"Subida de {valor:.1f} puntos de humedad media respecto a la "
                        f"lectura anterior."
                    ),
                    recomendacion="Verificar si hubo lluvia, riego, mantenimiento o anomalía.",
                ))
            elif valor <= -UMBRAL_VARIACION_HUMEDAD:
                alertas.append(Alerta(
                    fecha_hora=df.loc[idx, "fecha_hora"],
                    tipo="caida_brusca_humedad",
                    nivel="aviso",
                    variable="humedad_media_global",
                    descripcion=(
                        f"Caída de {abs(valor):.1f} puntos de humedad media respecto a la "
                        f"lectura anterior."
                    ),
                    recomendacion="Revisar posibles pérdidas rápidas o error de lectura.",
                ))

    # ---- 4. Temperatura alta relativa: una alerta por día con pico.
    if "temp_media_global" in df and not np.isnan(temp_high):
        mask = df["temp_media_global"] >= temp_high
        if mask.any():
            dias = df.loc[mask].assign(_dia=df.loc[mask, "fecha_hora"].dt.date)
            for dia, grupo in dias.groupby("_dia"):
                pico = grupo.loc[grupo["temp_media_global"].idxmax()]
                alertas.append(Alerta(
                    fecha_hora=pico["fecha_hora"],
                    tipo="temp_alta_relativa",
                    nivel="info",
                    variable="temp_media_global",
                    descripcion=(
                        f"Día {dia}: pico de temperatura media global "
                        f"{pico['temp_media_global']:.1f}°C, dentro del 10% más alto del "
                        f"histórico. {len(grupo)} lecturas elevadas."
                    ),
                    recomendacion="Vigilar el estrés térmico relativo de la zona.",
                ))

    # ---- 5. Temperaturas incoherentes ----
    for i in range(1, N_SENSORES_TEMP + 1):
        c_min, c_med, c_max = f"temp_s{i}_min", f"temp_s{i}_media", f"temp_s{i}_max"
        if not {c_min, c_med, c_max}.issubset(df.columns):
            continue
        mask = ((df[c_min] > df[c_med]) | (df[c_med] > df[c_max])).fillna(False)
        for _, fila in df.loc[mask].iterrows():
            alertas.append(Alerta(
                fecha_hora=fila["fecha_hora"],
                tipo="temp_incoherente",
                nivel="aviso",
                variable=f"temp_s{i}",
                descripcion=(
                    f"Sensor {i}: no se cumple mín ({fila[c_min]:.1f}) "
                    f"≤ promedio ({fila[c_med]:.1f}) ≤ máx ({fila[c_max]:.1f})."
                ),
                recomendacion="Revisar importación, sensor o registro original.",
            ))

    # ---- 6. Batería baja: una alerta por día con valores bajos.
    if "bateria_mv" in df and not np.isnan(bat_low):
        mask = df["bateria_mv"] <= bat_low
        if mask.any():
            dias = df.loc[mask].assign(_dia=df.loc[mask, "fecha_hora"].dt.date)
            for dia, grupo in dias.groupby("_dia"):
                peor = grupo.loc[grupo["bateria_mv"].idxmin()]
                alertas.append(Alerta(
                    fecha_hora=peor["fecha_hora"],
                    tipo="bateria_baja",
                    nivel="critico",
                    variable="bateria_mv",
                    descripcion=(
                        f"Día {dia}: batería mínima {peor['bateria_mv']:.0f} mV, "
                        f"dentro del 5% más bajo del histórico."
                    ),
                    recomendacion="Comprobar alimentación del nodo.",
                ))

    # ---- 7. Panel solar bajo en horario diurno: una alerta por día.
    if "panel_solar_mv" in df:
        hora = df["fecha_hora"].dt.hour
        mask = (
            (hora >= HORA_DIURNA_INICIO)
            & (hora <= HORA_DIURNA_FIN)
            & (df["panel_solar_mv"] < UMBRAL_PANEL_DIURNO_BAJO)
        )
        if mask.any():
            dias = df.loc[mask].assign(_dia=df.loc[mask, "fecha_hora"].dt.date)
            for dia, grupo in dias.groupby("_dia"):
                peor = grupo.loc[grupo["panel_solar_mv"].idxmin()]
                alertas.append(Alerta(
                    fecha_hora=peor["fecha_hora"],
                    tipo="panel_solar_diurno_bajo",
                    nivel="aviso",
                    variable="panel_solar_mv",
                    descripcion=(
                        f"Día {dia}: panel solar a {peor['panel_solar_mv']:.0f} mV en "
                        f"horario diurno ({peor['fecha_hora'].hour}h). "
                        f"{len(grupo)} lecturas afectadas."
                    ),
                    recomendacion="Revisar orientación, sombreado, suciedad o conexión del panel.",
                ))

    # ---- 8. Sensor bloqueado: mismo valor durante demasiado tiempo ----
    for col in columnas_humedad(df) + columnas_temp(df, "media"):
        serie = df[col]
        # Detectar tramos de valores constantes.
        cambios = serie.ne(serie.shift()).cumsum()
        for _, tramo in serie.groupby(cambios):
            if tramo.notna().sum() > LECTURAS_BLOQUEO and tramo.nunique(dropna=True) == 1:
                idx = tramo.index[0]
                alertas.append(Alerta(
                    fecha_hora=df.loc[idx, "fecha_hora"],
                    tipo="sensor_bloqueado",
                    nivel="aviso",
                    variable=col,
                    descripcion=(
                        f"{col} repite el mismo valor ({tramo.iloc[0]:.2f}) durante "
                        f"{len(tramo)} lecturas consecutivas."
                    ),
                    recomendacion="Revisar sensor, cableado o comunicación.",
                ))

    # ---- 9. Huecos temporales ----
    if len(df) > 1:
        diff_min = df["fecha_hora"].diff().dt.total_seconds().div(60)
        cadencia = diff_min.median()
        mask = (diff_min > 1.5 * cadencia) & diff_min.notna()
        for idx in df.index[mask]:
            alertas.append(Alerta(
                fecha_hora=df.loc[idx, "fecha_hora"],
                tipo="hueco_temporal",
                nivel="info",
                variable="fecha_hora",
                descripcion=(
                    f"Salto temporal de {diff_min.loc[idx]:.0f} minutos respecto a la "
                    f"cadencia mediana ({cadencia:.0f} min)."
                ),
                recomendacion="Revisar conectividad, energía o sistema de registro.",
            ))

    if not alertas:
        return pd.DataFrame(columns=["fecha_hora", "tipo", "nivel", "variable",
                                     "descripcion", "recomendacion"])

    return pd.DataFrame([a.como_dict() for a in alertas])


# ---------------------------------------------------------------------------
# 7. Resumen diario
# ---------------------------------------------------------------------------

def resumen_diario(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega el dataset a granularidad diaria.

    Útil para alinear con datos IFAPA-RIA (apartado A+ del enunciado) y
    para mostrar gráficos compactos en el dashboard de la web.

    Returns
    -------
    pandas.DataFrame
        Columnas mínimas: fecha, humedad media, humedad min, humedad max,
        variación de humedad, temperatura media/min/max del suelo,
        batería media, panel solar medio y nº de registros del día.
    """
    if df.empty:
        return df

    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha_hora"]).dt.date

    hum = columnas_humedad(df)
    tmedia = columnas_temp(df, "media")
    tmin = columnas_temp(df, "min")
    tmax = columnas_temp(df, "max")

    agg = {}
    if hum:
        df["__hum_media_fila"] = df[hum].mean(axis=1)
        agg["__hum_media_fila"] = ["mean", "min", "max"]
    if tmedia:
        df["__t_media_fila"] = df[tmedia].mean(axis=1)
        agg["__t_media_fila"] = ["mean"]
    if tmin:
        df["__t_min_fila"] = df[tmin].min(axis=1)
        agg["__t_min_fila"] = ["min"]
    if tmax:
        df["__t_max_fila"] = df[tmax].max(axis=1)
        agg["__t_max_fila"] = ["max"]
    if "bateria_mv" in df:
        agg["bateria_mv"] = ["mean"]
    if "panel_solar_mv" in df:
        agg["panel_solar_mv"] = ["mean"]

    diario = df.groupby("fecha").agg(agg)
    diario.columns = ["_".join(c).rstrip("_") for c in diario.columns]
    # Renombrar a un esquema más limpio.
    renombre = {
        "__hum_media_fila_mean": "humedad_media_dia",
        "__hum_media_fila_min": "humedad_min_dia",
        "__hum_media_fila_max": "humedad_max_dia",
        "__t_media_fila_mean": "temp_suelo_media_dia",
        "__t_min_fila_min": "temp_suelo_min_dia",
        "__t_max_fila_max": "temp_suelo_max_dia",
        "bateria_mv_mean": "bateria_media_dia_mv",
        "panel_solar_mv_mean": "panel_solar_media_dia_mv",
    }
    diario = diario.rename(columns=renombre)
    diario["variacion_humedad_dia"] = (
        diario.get("humedad_max_dia", 0) - diario.get("humedad_min_dia", 0)
    )
    diario["n_registros_dia"] = df.groupby("fecha").size()
    return diario.reset_index()


# ---------------------------------------------------------------------------
# 8. Pipeline completo
# ---------------------------------------------------------------------------

@dataclass
class ResultadoPipeline:
    """Empaqueta todos los productos del pipeline para uso externo."""
    df_limpio: pd.DataFrame
    df_indicadores: pd.DataFrame
    df_alertas: pd.DataFrame
    df_diario: pd.DataFrame
    informe: InformeLimpieza


def ejecutar_pipeline(ruta_csv: str | Path) -> ResultadoPipeline:
    """Ejecuta el pipeline completo: importar → normalizar → limpiar → indicadores → alertas → diario.

    Pensado para uso desde scripts (``main.py``), notebooks y management
    commands de Django.

    Parameters
    ----------
    ruta_csv : str | Path
        Ruta al CSV bruto de EnviroPro.

    Returns
    -------
    ResultadoPipeline
        Objeto con todos los DataFrames intermedios y el informe.
    """
    bruto = importar_csv(ruta_csv)
    normalizado = normalizar_columnas(bruto)
    limpio, informe = limpiar(normalizado)
    con_indicadores = calcular_indicadores(limpio)
    alertas = generar_alertas(con_indicadores)
    diario = resumen_diario(con_indicadores)
    return ResultadoPipeline(
        df_limpio=limpio,
        df_indicadores=con_indicadores,
        df_alertas=alertas,
        df_diario=diario,
        informe=informe,
    )


__all__ = [
    "importar_csv",
    "normalizar_columnas",
    "columnas_humedad",
    "columnas_temp",
    "limpiar",
    "calcular_indicadores",
    "generar_alertas",
    "resumen_diario",
    "ejecutar_pipeline",
    "InformeLimpieza",
    "ResultadoPipeline",
    "Alerta",
] 