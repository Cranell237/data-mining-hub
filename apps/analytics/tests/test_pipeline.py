import pytest
import pandas as pd
import numpy as np
from src.pipeline import load_and_preprocess_dataset, calculate_feature_metrics, scale_features


def test_load_and_preprocess_dataset():
    X, y = load_and_preprocess_dataset()
    assert not X.empty
    assert len(X) == len(y)
    assert X.isna().sum().sum() == 0


def test_calculate_feature_metrics():
    X, _ = load_and_preprocess_dataset()
    metrics = calculate_feature_metrics(X)
    assert isinstance(metrics, pd.DataFrame)
    assert "mean" in metrics.columns
    assert "std" in metrics.columns


def test_scale_features():
    X, _ = load_and_preprocess_dataset()
    scaled = scale_features(X)

    # Verificar que devuelve un DataFrame
    assert isinstance(scaled, pd.DataFrame)

    # Verificar que mantiene las mismas columnas e índice
    assert list(scaled.columns) == list(X.columns)
    assert list(scaled.index) == list(X.index)

    # Verificar que la normalización fue correcta (media ≈ 0, std ≈ 1)
    assert np.allclose(scaled.mean(), 0, atol=1e-10)
    assert np.allclose(scaled.std(), 1, atol=1e-2)

    # Verificar que no hay valores nulos
    assert scaled.isna().sum().sum() == 0
