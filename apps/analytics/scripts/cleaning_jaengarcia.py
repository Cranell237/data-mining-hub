"""U2-T3 · Parte A — Reimplementación comparativa de la *spec básica*.

Autor: Estalin Jaén García

Este script implementa la especificación básica de limpieza (sección 1.2 del
enunciado) con las **firmas simples** (las funciones devuelven solo
``pd.DataFrame``, salvo el orquestador que devuelve un ``dict``). Es una versión
intencionalmente minimalista: NO deduplica, NO valida rangos extra ni emite
reportes por paso — justamente para contrastarla con la implementación heredada
y más robusta de ``src/cleaning.py``.

El resultado se materializa en una tabla propia, ``customer_credit_clean_jaengarcia``,
sin tocar ni la tabla cruda ni la tabla ``customer_credit_clean`` del repo.

Uso (desde el host, con los contenedores levantados):

    docker compose exec analytics python scripts/cleaning_jaengarcia.py
"""
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.impute import KNNImputer

from src.db_connector import extract_raw_data, get_database_engine

RAW_TABLE = "customer_credit_transactions"
CLEAN_TABLE = "customer_credit_clean_jaengarcia"

NUMERIC_COLS = ["age", "annual_income", "credit_score", "loan_amount"]
OUTLIER_COLS = ["annual_income", "loan_amount"]

# La spec básica solo exige validar el rango de la edad.
AGE_RANGE = (18, 100)


def load_table(table: str = RAW_TABLE) -> pd.DataFrame:
    """Carga la tabla completa desde PostgreSQL a un DataFrame."""
    return extract_raw_data(f"SELECT * FROM {table} ORDER BY transaction_id")


def normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza inconsistencias según la spec básica.

    - ``region``: ``strip`` + *Title Case*.
    - ``age`` fuera de [18, 100] → ``NaN`` (pasa a imputación).

    Returns:
        Una copia del DataFrame normalizado.
    """
    out = df.copy()
    if "region" in out.columns:
        out["region"] = out["region"].astype("string").str.strip().str.title()
    if "age" in out.columns:
        lo, hi = AGE_RANGE
        out.loc[(out["age"] < lo) | (out["age"] > hi), "age"] = np.nan
    return out


def impute_column(df: pd.DataFrame, column: str, strategy: str) -> pd.DataFrame:
    """Imputa los ``NaN`` de ``column`` con la estrategia indicada.

    Estrategias: ``mean``, ``median``, ``mode`` (categóricas) y ``knn``
    (``KNNImputer`` con ``n_neighbors=5`` sobre las columnas numéricas).

    Returns:
        Copia del DataFrame con la columna imputada.

    Raises:
        ValueError: si la estrategia no es reconocida.
    """
    out = df.copy()
    series = out[column]

    if strategy == "mean":
        out[column] = series.fillna(series.mean())
    elif strategy == "median":
        out[column] = series.fillna(series.median())
    elif strategy == "mode":
        out[column] = series.fillna(series.mode(dropna=True).iloc[0])
    elif strategy == "knn":
        out[NUMERIC_COLS] = KNNImputer(n_neighbors=5).fit_transform(
            out[NUMERIC_COLS]
        )
    else:
        raise ValueError(f"Estrategia no soportada: {strategy}")

    return out


def treat_outliers(
    df: pd.DataFrame,
    column: str,
    method: str = "iqr",
    action: str = "cap",
) -> pd.DataFrame:
    """Detecta (``iqr`` 1.5·IQR o ``zscore`` 3σ) y trata (``cap``) outliers.

    El acotamiento (capping) fija los valores extremos al límite del criterio,
    preservando todas las filas.

    Returns:
        Copia del DataFrame con la columna acotada.

    Raises:
        ValueError: si el método o la acción no son reconocidos.
    """
    out = df.copy()
    s = out[column].dropna()

    if method == "iqr":
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    elif method == "zscore":
        mean, std = s.mean(), s.std()
        lower, upper = mean - 3 * std, mean + 3 * std
    else:
        raise ValueError(f"Método no soportado: {method}")

    if action == "cap":
        out[column] = out[column].clip(lower=lower, upper=upper)
    else:
        raise ValueError(f"Acción no soportada: {action}")

    return out


def run_cleaning_pipeline() -> dict:
    """Orquesta el pipeline básico raw → clean y escribe ``CLEAN_TABLE``.

    Pasos (spec básica, sin deduplicación ni rangos extra):
      1. Normalización (región + rango de edad).
      2. Imputación por mediana en numéricas y por moda en ``region``.
      3. Acotamiento (capping IQR) de outliers en ingresos y préstamos.

    Returns:
        Resumen con la tabla destino y el conteo de filas de entrada/salida.
    """
    raw = load_table(RAW_TABLE)

    clean = normalize_frame(raw)
    for col in NUMERIC_COLS:
        clean = impute_column(clean, col, "median")
    clean = impute_column(clean, "region", "mode")
    for col in OUTLIER_COLS:
        clean = treat_outliers(clean, col, method="iqr", action="cap")

    engine = get_database_engine()
    clean.to_sql(CLEAN_TABLE, engine, if_exists="replace", index=False)

    return {
        "clean_table": CLEAN_TABLE,
        "rows_in": int(len(raw)),
        "rows_out": int(len(clean)),
        "nulls_out": int(clean[NUMERIC_COLS].isna().sum().sum()),
        "income_variance_in": round(float(raw["annual_income"].var()), 2),
        "income_variance_out": round(float(clean["annual_income"].var()), 2),
    }


def main() -> None:
    """Ejecuta el pipeline básico e imprime el resumen por consola."""
    summary = run_cleaning_pipeline()
    print("=" * 60)
    print(f"Parte A · Pipeline básico (Jaén García)")
    print("=" * 60)
    print(f"  Tabla destino      : {summary['clean_table']}")
    print(f"  Filas entrada      : {summary['rows_in']}")
    print(f"  Filas salida       : {summary['rows_out']}")
    print(f"  Nulos restantes    : {summary['nulls_out']}")
    print(f"  Var. ingreso ANTES : {summary['income_variance_in']:,.2f}")
    print(f"  Var. ingreso DESPUÉS: {summary['income_variance_out']:,.2f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
