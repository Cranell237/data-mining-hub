"""U2-T3 · Parte B1 — Test de la extensión MAD sobre src/cleaning.py.

Verifica el nuevo método de detección ``mad`` (Median Absolute Deviation)
añadido a ``detect_outlier_mask`` y ``treat_outliers``. El caso central
documenta por qué MAD es más robusto que Z-score ante el efecto *masking*:
un único valor extremo infla la desviación estándar y hace que Z-score "no
vea" el outlier, mientras que la mediana y la MAD no se dejan arrastrar.

Los 5 tests heredados de ``test_cleaning.py`` siguen pasando sin cambios.
"""
import numpy as np
import pandas as pd

from src.cleaning import (
    DETECTION_METHODS,
    detect_outlier_mask,
    treat_outliers,
)


def _frame_con_outlier_extremo() -> pd.DataFrame:
    """Ingresos ~homogéneos con un único outlier extremo (500K)."""
    return pd.DataFrame(
        {
            "annual_income": [
                30_000, 31_000, 29_500, 32_000, 30_500,
                31_500, 28_000, 33_000, 30_000, 500_000,
            ],
        }
    )


def test_mad_registrado_en_metodos():
    """La extensión queda expuesta en el contrato público del módulo."""
    assert "mad" in DETECTION_METHODS


def test_mad_detecta_outlier_que_zscore_enmascara():
    """MAD captura el 500K; Z-score lo pierde por masking (efecto clave)."""
    df = _frame_con_outlier_extremo()
    assert detect_outlier_mask(df, "annual_income", "zscore").sum() == 0
    assert detect_outlier_mask(df, "annual_income", "mad").sum() >= 1


def test_mad_cap_acota_el_extremo_y_preserva_filas():
    """El capping por MAD reduce el máximo y conserva todas las filas."""
    df = _frame_con_outlier_extremo()
    out, rep = treat_outliers(df, "annual_income", "mad", "cap")
    assert out["annual_income"].max() < 500_000
    assert rep["detected"] >= 1
    assert len(out) == len(df)


def test_mad_columna_constante_sin_outliers():
    """Columna constante → MAD escalada 0 → sin outliers y sin excepción."""
    df = pd.DataFrame({"annual_income": [100.0] * 8})
    assert detect_outlier_mask(df, "annual_income", "mad").sum() == 0
