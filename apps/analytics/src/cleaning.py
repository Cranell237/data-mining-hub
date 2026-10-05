"""Pipeline de limpieza y calidad de datos — CRISP-DM Fase 3 (U2·T3).

Implementa el tratamiento de la "Tríada Patológica de Datos" sobre la tabla
cruda ``customer_credit_transactions``:

    1. Inconsistencias   → :func:`normalize_inconsistencies`
    2. Valores faltantes → :func:`impute_column`
    3. Valores atípicos  → :func:`handle_outliers`

La función orquestadora :func:`run_cleaning_pipeline` encadena las tres etapas,
emite un reporte de auditoría por consola (varianza de ``annual_income`` antes y
después del tratamiento) y persiste el resultado en la tabla
``customer_credit_clean`` dentro de PostgreSQL.

Ejecución (desde la raíz del repo, con los contenedores levantados):

    docker compose exec analytics python -m src.cleaning
"""
from typing import Iterable, Optional

import numpy as np
import pandas as pd
from sklearn.impute import KNNImputer
from sqlalchemy.engine import Engine

from src.db_connector import extract_raw_data, get_database_engine

# Columnas objetivo del dominio de riesgo crediticio
NUMERIC_COLUMNS = ["age", "annual_income", "credit_score", "loan_amount"]
OUTLIER_COLUMNS = ["annual_income", "loan_amount"]
CATEGORICAL_COLUMNS = ["region"]

# Reglas de negocio (rangos válidos) para la validación estructural
AGE_RANGE = (18, 100)
CREDIT_SCORE_RANGE = (300, 850)

SOURCE_TABLE = "customer_credit_transactions"
TARGET_TABLE = "customer_credit_clean"


# ──────────────────────────────────────────────────────────────────────────
# Actividad 3.1 · Gestión de Inconsistencias (Normalización)
# ──────────────────────────────────────────────────────────────────────────
def normalize_inconsistencies(
    df: pd.DataFrame,
    region_col: str = "region",
    age_col: str = "age",
    age_range: tuple[int, int] = AGE_RANGE,
    credit_col: str = "credit_score",
    credit_range: tuple[int, int] = CREDIT_SCORE_RANGE,
) -> pd.DataFrame:
    """Estandariza formatos categóricos y valida reglas de negocio numéricas.

    - ``region``: elimina espacios accidentales (``strip``) y unifica el formato
      a *Title Case* (``"  costa "`` / ``"COSTA"`` → ``"Costa"``).
    - ``age`` y ``credit_score``: los valores que violan las reglas de negocio
      (fuera de rango) se reemplazan por ``NaN`` para forzar su paso por la
      etapa de imputación, en lugar de dejar valores imposibles en el dataset.

    Args:
        df: DataFrame crudo.
        region_col: nombre de la columna categórica a normalizar.
        age_col: columna de edad a validar.
        age_range: tupla ``(min, max)`` con el rango de edad admisible.
        credit_col: columna de puntaje crediticio a validar.
        credit_range: tupla ``(min, max)`` con el rango de score admisible.

    Returns:
        Una copia del DataFrame con los formatos normalizados y los valores
        fuera de rango convertidos en ``NaN``.
    """
    result = df.copy()

    # Normalización de la variable categórica
    if region_col in result.columns:
        result[region_col] = (
            result[region_col].astype("string").str.strip().str.title()
        )

    # Validación estructural de variables numéricas (reglas de negocio)
    if age_col in result.columns:
        low, high = age_range
        invalid_age = (result[age_col] < low) | (result[age_col] > high)
        result.loc[invalid_age, age_col] = np.nan

    if credit_col in result.columns:
        low, high = credit_range
        invalid_score = (result[credit_col] < low) | (result[credit_col] > high)
        result.loc[invalid_score, credit_col] = np.nan

    return result


# ──────────────────────────────────────────────────────────────────────────
# Actividad 3.2 · Tratamiento de Valores Faltantes (Imputación)
# ──────────────────────────────────────────────────────────────────────────
def impute_column(
    df: pd.DataFrame,
    column: str,
    strategy: str = "mean",
) -> pd.DataFrame:
    """Imputa los valores faltantes de una columna según la estrategia dada.

    Estrategias soportadas:
        - ``"mean"``   : media aritmética (μ), para numéricas continuas.
        - ``"median"`` : mediana, robusta ante outliers, para numéricas.
        - ``"mode"``   : moda, obligatoria para categóricas como ``region``.
        - ``"knn"``    : (reto avanzado) ``KNNImputer`` de Scikit-Learn, que
          deduce el faltante conservando las relaciones multivariables al
          apoyarse en el resto de columnas numéricas.

    Args:
        df: DataFrame de entrada.
        column: columna cuyos ``NaN`` se van a imputar.
        strategy: una de ``{"mean", "median", "mode", "knn"}``.

    Returns:
        Copia del DataFrame con la columna imputada.

    Raises:
        ValueError: si la estrategia no es reconocida.
    """
    result = df.copy()

    if strategy == "knn":
        # La imputación KNN opera sobre el subespacio numérico completo para
        # preservar las correlaciones entre variables.
        numeric = result.select_dtypes(include=np.number)
        n_neighbors = max(1, min(5, len(numeric) - 1))
        imputer = KNNImputer(n_neighbors=n_neighbors)
        imputed = imputer.fit_transform(numeric)
        imputed_df = pd.DataFrame(
            imputed, columns=numeric.columns, index=numeric.index
        )
        result[column] = imputed_df[column]
        return result

    serie = result[column]
    if strategy == "mean":
        fill_value = serie.mean()
    elif strategy == "median":
        fill_value = serie.median()
    elif strategy == "mode":
        modes = serie.mode(dropna=True)
        fill_value = modes.iloc[0] if not modes.empty else serie.iloc[0]
    else:
        raise ValueError(
            f"Estrategia de imputación no soportada: {strategy!r}. "
            "Use 'mean', 'median', 'mode' o 'knn'."
        )

    result[column] = serie.fillna(fill_value)
    return result


# ──────────────────────────────────────────────────────────────────────────
# Actividad 3.3 · Manejo Algorítmico de Outliers (Capping)
# ──────────────────────────────────────────────────────────────────────────
def handle_outliers(
    df: pd.DataFrame,
    columns: Iterable[str] = OUTLIER_COLUMNS,
    method: str = "iqr",
    factor: float = 1.5,
    sigma: float = 3.0,
) -> pd.DataFrame:
    """Detecta y acota (capping) valores atípicos preservando los registros.

    En lugar de eliminar filas, los valores que exceden los límites se fijan al
    umbral correspondiente (``Series.clip``), conservando así el tamaño del
    dataset — crítico cuando cada registro es un cliente real.

    Métodos de detección:
        - ``"iqr"``       : rango intercuartílico. Límites en
          ``[Q1 - factor·IQR, Q3 + factor·IQR]``.
        - ``"empirical"`` : regla empírica. Límites en ``μ ± sigma·σ``
          (la guía pide "distancia mayor a 3" desviaciones estándar).

    Args:
        df: DataFrame de entrada.
        columns: columnas numéricas sobre las que aplicar el tratamiento.
        method: ``"iqr"`` o ``"empirical"``.
        factor: multiplicador del IQR (típicamente 1.5).
        sigma: nº de desviaciones estándar para la regla empírica.

    Returns:
        Copia del DataFrame con los outliers acotados.

    Raises:
        ValueError: si el método no es reconocido.
    """
    result = df.copy()

    for column in columns:
        if column not in result.columns:
            continue
        serie = result[column]

        if method == "iqr":
            q1 = serie.quantile(0.25)
            q3 = serie.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - factor * iqr
            upper = q3 + factor * iqr
        elif method == "empirical":
            mean = serie.mean()
            std = serie.std()
            lower = mean - sigma * std
            upper = mean + sigma * std
        else:
            raise ValueError(
                f"Método de detección no soportado: {method!r}. "
                "Use 'iqr' o 'empirical'."
            )

        # Capping: fija los valores extremos a los umbrales calculados
        result[column] = serie.clip(lower=lower, upper=upper)

    return result


# ──────────────────────────────────────────────────────────────────────────
# Orquestación del pipeline (Sección 4)
# ──────────────────────────────────────────────────────────────────────────
def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica secuencialmente el pipeline de calidad a un DataFrame crudo.

    Orden (conforme a la guía):
        0. Deduplicación de registros exactos (higiene previa).
        1. Filtro de inconsistencias (normalización + reglas de negocio).
        2. Imputación estadística (mediana en numéricas, moda en categóricas).
        3. Detección y acotamiento (capping) de outliers.

    Args:
        df: DataFrame crudo extraído del warehouse.

    Returns:
        DataFrame limpio, sin nulos en las columnas tratadas y con los mismos
        (o menos, por deduplicación) registros.
    """
    result = df.copy()

    # 0. Deduplicación — ignora claves técnicas que siempre difieren
    dedup_ignore = [c for c in ("transaction_id", "created_at") if c in result.columns]
    subset = [c for c in result.columns if c not in dedup_ignore]
    result = result.drop_duplicates(subset=subset).reset_index(drop=True)

    # 1. Inconsistencias
    result = normalize_inconsistencies(result)

    # 2. Imputación — numéricas por mediana, categóricas por moda
    for column in NUMERIC_COLUMNS:
        if column in result.columns and result[column].isna().any():
            result = impute_column(result, column, strategy="median")
    for column in CATEGORICAL_COLUMNS:
        if column in result.columns and result[column].isna().any():
            result = impute_column(result, column, strategy="mode")

    # 3. Outliers (capping) sobre las variables monetarias
    result = handle_outliers(result, OUTLIER_COLUMNS, method="iqr")

    return result


def audit_variance_report(
    df_before: pd.DataFrame,
    df_after: pd.DataFrame,
    column: str = "annual_income",
) -> dict:
    """Imprime y devuelve la varianza de ``column`` antes y después del pipeline.

    Entregable de **Auditoría de Calidad**: evidencia el efecto del tratamiento
    de outliers e imputación sobre la dispersión de la variable.

    Args:
        df_before: DataFrame crudo (antes de la limpieza).
        df_after: DataFrame limpio (después de la limpieza).
        column: columna numérica a auditar.

    Returns:
        Diccionario con las varianzas y la reducción porcentual.
    """
    var_before = float(df_before[column].var())
    var_after = float(df_after[column].var())
    reduction = (
        (var_before - var_after) / var_before * 100 if var_before else 0.0
    )

    print("\n" + "=" * 70)
    print(f"AUDITORÍA DE CALIDAD · Varianza de '{column}'")
    print("=" * 70)
    print(f"  Varianza ANTES  (crudo)  : {var_before:,.2f}")
    print(f"  Varianza DESPUÉS (limpio): {var_after:,.2f}")
    print(f"  Reducción de varianza    : {reduction:.2f}%")
    print("=" * 70)

    return {
        "column": column,
        "variance_before": var_before,
        "variance_after": var_after,
        "reduction_pct": reduction,
    }


def run_cleaning_pipeline(
    engine: Optional[Engine] = None,
    source_table: str = SOURCE_TABLE,
    target_table: str = TARGET_TABLE,
    persist: bool = True,
) -> pd.DataFrame:
    """Ejecuta el pipeline end-to-end: extrae → limpia → audita → persiste.

    Lee los datos crudos de ``source_table``, aplica :func:`clean_dataframe`,
    imprime el reporte de auditoría y (si ``persist``) guarda el resultado en
    ``target_table`` dentro de PostgreSQL con ``if_exists="replace"``.

    Args:
        engine: motor SQLAlchemy a reutilizar; si es ``None`` se crea uno.
        source_table: tabla cruda de origen.
        target_table: tabla destino con los datos limpios.
        persist: si ``True``, escribe el resultado en la base de datos.

    Returns:
        El DataFrame limpio.
    """
    active_engine = engine or get_database_engine()

    raw = extract_raw_data(f"SELECT * FROM {source_table}", engine=active_engine)
    cleaned = clean_dataframe(raw)

    # Reporte de auditoría por consola (entregable)
    print("\n" + "=" * 70)
    print("PIPELINE DE LIMPIEZA · customer_credit_transactions")
    print("=" * 70)
    print(f"  Registros crudos   : {len(raw)}")
    print(f"  Registros limpios  : {len(cleaned)} (deduplicados)")
    print(f"  Nulos antes        : {int(raw[NUMERIC_COLUMNS].isna().sum().sum())}")
    print(f"  Nulos después      : {int(cleaned[NUMERIC_COLUMNS].isna().sum().sum())}")
    audit_variance_report(raw, cleaned, column="annual_income")

    if persist:
        cleaned.to_sql(
            target_table, active_engine, if_exists="replace", index=False
        )
        print(f"\n✔ Datos limpios persistidos en la tabla '{target_table}'.")

    return cleaned


if __name__ == "__main__":
    run_cleaning_pipeline()
