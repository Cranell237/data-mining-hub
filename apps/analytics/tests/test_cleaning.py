"""Pruebas unitarias del pipeline de limpieza (U2·T3).

Cada función se valida con DataFrames sintéticos que contienen a propósito la
"Tríada Patológica": inconsistencias de formato, valores faltantes y outliers.
El test de integración ejerce el pipeline completo contra la base de datos viva.
"""
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text

from src.cleaning import (
    audit_variance_report,
    clean_dataframe,
    handle_outliers,
    impute_column,
    normalize_inconsistencies,
    run_cleaning_pipeline,
)
from src.db_connector import get_database_engine


@pytest.fixture
def dirty_df() -> pd.DataFrame:
    """DataFrame crudo con los tres tipos de defecto."""
    return pd.DataFrame(
        {
            "customer_id": [f"CUST-{i}" for i in range(8)],
            "age": [34, 150, 15, np.nan, 45, 29, 52, 41],      # 150/15 fuera de rango
            "annual_income": [45000, 82000, np.nan, 500000, 32000, 18500, 62000, 999],
            "credit_score": [710, 680, 999, 615, np.nan, 580, 740, 630],  # 999 inválido
            "loan_amount": [12000, 25000, 5000, 400000, 8500, 3500, 18000, 9500],
            "region": [" costa ", "SIERRA", "Oriente", "costa", "Sierra  ", "Costa", "Insular", "costa"],
        }
    )


# ── Actividad 3.1 · Normalización ──────────────────────────────────────────
def test_normalize_region_strip_and_titlecase(dirty_df):
    out = normalize_inconsistencies(dirty_df)
    assert set(out["region"].unique()) <= {"Costa", "Sierra", "Oriente", "Insular"}
    assert " costa " not in out["region"].tolist()
    assert "SIERRA" not in out["region"].tolist()


def test_normalize_age_out_of_range_to_nan(dirty_df):
    out = normalize_inconsistencies(dirty_df)
    # Las edades 150 y 15 deben convertirse en NaN
    assert out.loc[1, "age"] != out.loc[1, "age"]  # NaN != NaN
    assert out.loc[2, "age"] != out.loc[2, "age"]
    # Una edad válida se conserva
    assert out.loc[0, "age"] == 34


def test_normalize_credit_score_out_of_range_to_nan(dirty_df):
    out = normalize_inconsistencies(dirty_df)
    assert np.isnan(out.loc[2, "credit_score"])  # 999 inválido → NaN


def test_normalize_does_not_mutate_original(dirty_df):
    original = dirty_df.copy()
    normalize_inconsistencies(dirty_df)
    pd.testing.assert_frame_equal(dirty_df, original)


# ── Actividad 3.2 · Imputación ──────────────────────────────────────────────
def test_impute_mean_fills_nan():
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, np.nan]})
    out = impute_column(df, "x", strategy="mean")
    assert out["x"].isna().sum() == 0
    assert out.loc[3, "x"] == pytest.approx(2.0)


def test_impute_median_fills_nan():
    df = pd.DataFrame({"x": [1.0, 2.0, 100.0, np.nan]})
    out = impute_column(df, "x", strategy="median")
    assert out.loc[3, "x"] == pytest.approx(2.0)


def test_impute_mode_for_categorical():
    df = pd.DataFrame({"region": ["Costa", "Costa", "Sierra", None]})
    out = impute_column(df, "region", strategy="mode")
    assert out["region"].isna().sum() == 0
    assert out.loc[3, "region"] == "Costa"


def test_impute_knn_fills_nan():
    df = pd.DataFrame(
        {
            "a": [1.0, 2.0, 3.0, 4.0, np.nan],
            "b": [2.0, 4.0, 6.0, 8.0, 10.0],
        }
    )
    out = impute_column(df, "a", strategy="knn")
    assert out["a"].isna().sum() == 0


def test_impute_invalid_strategy_raises():
    df = pd.DataFrame({"x": [1.0, np.nan]})
    with pytest.raises(ValueError):
        impute_column(df, "x", strategy="inexistente")


# ── Actividad 3.3 · Outliers (capping) ──────────────────────────────────────
def test_handle_outliers_iqr_caps_extremes():
    df = pd.DataFrame({"annual_income": [10, 11, 12, 13, 14, 15, 1000]})
    out = handle_outliers(df, ["annual_income"], method="iqr")
    # El valor extremo 1000 queda acotado por debajo de su valor original
    assert out["annual_income"].max() < 1000
    # Se preserva el número de filas (no se elimina ninguna)
    assert len(out) == len(df)


def test_handle_outliers_reduces_variance():
    df = pd.DataFrame({"annual_income": [10, 11, 12, 13, 14, 15, 1_000_000]})
    out = handle_outliers(df, ["annual_income"], method="iqr")
    assert out["annual_income"].var() < df["annual_income"].var()


def test_handle_outliers_empirical_method():
    df = pd.DataFrame({"loan_amount": [100, 110, 120, 130, 140, 5000]})
    out = handle_outliers(df, ["loan_amount"], method="empirical", sigma=2.0)
    assert out["loan_amount"].max() < 5000
    assert len(out) == len(df)


def test_handle_outliers_invalid_method_raises():
    df = pd.DataFrame({"annual_income": [1, 2, 3]})
    with pytest.raises(ValueError):
        handle_outliers(df, ["annual_income"], method="zzz")


# ── Orquestador clean_dataframe ─────────────────────────────────────────────
def test_clean_dataframe_leaves_no_nulls(dirty_df):
    out = clean_dataframe(dirty_df)
    for column in ["age", "annual_income", "credit_score", "loan_amount", "region"]:
        assert out[column].isna().sum() == 0, f"Quedaron nulos en {column}"


def test_clean_dataframe_normalizes_region(dirty_df):
    out = clean_dataframe(dirty_df)
    assert set(out["region"].unique()) <= {"Costa", "Sierra", "Oriente", "Insular"}


def test_clean_dataframe_removes_duplicates():
    base = pd.DataFrame(
        {
            "customer_id": ["CUST-1", "CUST-1", "CUST-2"],
            "age": [30, 30, 40],
            "annual_income": [40000.0, 40000.0, 60000.0],
            "credit_score": [700, 700, 720],
            "loan_amount": [10000.0, 10000.0, 20000.0],
            "region": ["Costa", "Costa", "Sierra"],
        }
    )
    out = clean_dataframe(base)
    assert len(out) == 2  # el duplicado exacto se elimina


def test_audit_variance_report_returns_values(dirty_df):
    cleaned = clean_dataframe(dirty_df)
    report = audit_variance_report(dirty_df, cleaned, column="annual_income")
    assert report["variance_after"] <= report["variance_before"]
    assert set(report) == {
        "column", "variance_before", "variance_after", "reduction_pct"
    }


# ── Integración end-to-end contra la base de datos viva ─────────────────────
def test_run_cleaning_pipeline_creates_clean_table():
    engine = get_database_engine()
    cleaned = run_cleaning_pipeline(engine=engine, persist=True)

    assert not cleaned.empty
    # La tabla destino existe y no tiene nulos en las columnas tratadas
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM customer_credit_clean")
        ).scalar()
        null_income = conn.execute(
            text("SELECT COUNT(*) FROM customer_credit_clean WHERE annual_income IS NULL")
        ).scalar()
    assert count == len(cleaned)
    assert null_income == 0
