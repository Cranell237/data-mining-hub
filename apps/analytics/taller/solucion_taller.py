"""Solución del Taller en Clase U2-T1 (pág. 17 del PDF).

Actividad Guiada en Parejas — 4 RETOS ejecutados sobre el entorno Docker
activo, reutilizando las funciones de extracción de ``src.db_connector``.

Ejecución (desde la raíz del repo, con los contenedores levantados):

    docker compose exec analytics python taller/solucion_taller.py
"""
import pandas as pd

from src.db_connector import extract_raw_data, extract_raw_data_in_chunks

TABLE = "customer_credit_transactions"


def _titulo(texto: str) -> None:
    """Imprime un encabezado legible para separar cada reto en la salida."""
    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)


def reto_1_conteo_por_region() -> pd.DataFrame:
    """RETO 1 · Agrupar clientes por región usando agregación SQL (GROUP BY)."""
    query = f"""
        SELECT region, COUNT(*) AS total_clientes
        FROM {TABLE}
        GROUP BY region
        ORDER BY total_clientes DESC
    """
    df = extract_raw_data(query)
    _titulo("RETO 1 · Conteo por Región (GROUP BY region)")
    print(df.to_string(index=False))
    return df


def reto_2_perfil_de_riesgo() -> pd.DataFrame:
    """RETO 2 · Extraer solo clientes con puntaje crítico: credit_score < 650."""
    query = f"""
        SELECT customer_id, credit_score, region, has_defaulted
        FROM {TABLE}
        WHERE credit_score < 650
        ORDER BY credit_score ASC
    """
    df = extract_raw_data(query)
    _titulo("RETO 2 · Perfil de Riesgo (credit_score < 650)")
    print(df.to_string(index=False))
    print(f"\nClientes en riesgo: {len(df)}")
    return df


def reto_3_filtro_y_orden() -> pd.DataFrame:
    """RETO 3 · Filtrar clientes de Costa ordenados por ingreso anual (desc)."""
    query = f"""
        SELECT customer_id, region, annual_income, credit_score
        FROM {TABLE}
        WHERE region = 'Costa'
        ORDER BY annual_income DESC
    """
    df = extract_raw_data(query)
    _titulo("RETO 3 · Filtro y Orden (region = 'Costa', ingreso DESC)")
    print(df.to_string(index=False))
    return df


def reto_4_reconstruccion(chunk_size: int = 3) -> pd.DataFrame:
    """RETO 4 · Consolidar los chunks con pd.concat() y validar los 9 registros."""
    query = f"SELECT * FROM {TABLE} ORDER BY transaction_id"
    _titulo("RETO 4 · Reconstrucción (pd.concat de los chunks)")

    partes = []
    for idx, chunk in enumerate(extract_raw_data_in_chunks(query, chunk_size=chunk_size)):
        print(f"Lote #{idx} recibido: {len(chunk)} registros en memoria")
        partes.append(chunk)

    df_completo = pd.concat(partes, ignore_index=True)
    print(f"\nRegistros consolidados: {len(df_completo)}")

    # Validación de la reconstrucción
    assert len(df_completo) == 9, f"Se esperaban 9 registros, se obtuvieron {len(df_completo)}"
    print("Validación OK: se reconstruyeron los 9 registros correctamente.")
    return df_completo


def main() -> None:
    """Ejecuta secuencialmente los cuatro retos del taller."""
    reto_1_conteo_por_region()
    reto_2_perfil_de_riesgo()
    reto_3_filtro_y_orden()
    reto_4_reconstruccion()


if __name__ == "__main__":
    main()
