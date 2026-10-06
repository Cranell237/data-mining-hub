# U2-T3 · Documento de análisis — Estalin Jaén García

Práctica *"Ingeniería sobre código existente"*. Entrega: Parte A (reimplementación
comparativa) + Parte B1 (extensión del módulo con detección MAD).

> Entorno: tabla cruda `customer_credit_transactions` con 2017 filas (9 base +
> 2008 sintéticas de `scripts/seed_synthetic.py --n 2000`, semilla 42).

---

## Parte A — Reimplementación comparativa

Mi versión de la *spec básica* vive en
[`apps/analytics/scripts/cleaning_jaengarcia.py`](../apps/analytics/scripts/cleaning_jaengarcia.py)
y escribe en la tabla `customer_credit_clean_jaengarcia`. Usa las firmas simples
(las funciones devuelven solo `pd.DataFrame`) y aplica, en orden: normalización
(región + rango de edad) → imputación (mediana / moda) → capping IQR de
`annual_income` y `loan_amount`.

### Resultado vs. la implementación del repo (`src/cleaning.py` → `customer_credit_clean`)

| Métrica                          | Repo (`customer_credit_clean`) | Mía (`..._jaengarcia`) |
| -------------------------------- | ------------------------------ | ---------------------- |
| Filas de salida                  | **2009**                       | **2017**               |
| Duplicados exactos remanentes    | 0                              | **8**                  |
| `credit_score` fuera de rango    | 0                              | **3** (valen 999)      |
| `max(credit_score)`              | 850                            | **999**                |
| `max(annual_income)`             | 74 924                         | 75 129                 |
| `max(loan_amount)`               | 30 180                         | 30 342                 |
| Varianza de `annual_income`      | 281 425 090                    | 283 236 295            |

### ¿Coinciden las filas? ¿Por qué difieren?

No coinciden: mi tabla tiene **8 filas más**. Las diferencias tienen tres causas
concretas, todas derivadas de que la spec básica es deliberadamente más simple:

1. **Deduplicación.** El repo elimina 8 duplicados exactos (inyectados a propósito
   por el seeder); mi versión básica no deduplica, así que los conserva. En un
   warehouse eso significa **contar 8 clientes dos veces**.

2. **Rangos de negocio.** La spec básica solo valida `age ∈ [18, 100]`. El repo
   valida las **cuatro** numéricas vía `VALID_RANGES`, por lo que convierte a `NaN`
   (y luego imputa) los `credit_score = 999` y los ingresos imposibles (500 000,
   620 000 > 300 000). Mi versión deja los **3 `credit_score = 999`** intactos
   (valor imposible que rompería cualquier modelo de scoring) y solo "disimula"
   los ingresos extremos con el capping IQR.

3. **Observabilidad.** El repo devuelve un reporte por paso (`steps` con before/
   after por columna); mi versión es una **caja negra**: hace la transformación
   pero no reporta cuántos valores tocó. Sin eso es imposible detectar que los
   datos de hoy llegaron distintos a los de ayer (*data drift*).

Los máximos y la varianza quedan apenas más altos en mi tabla porque el repo
elimina los ingresos imposibles **antes** de imputar, mientras yo los acoto por
IQR sobre la misma distribución — los límites resultan casi idénticos (~75 k).

### ¿Qué pasaría en producción si mi versión reemplazara a la del repo?

Sería una **regresión silenciosa**: el staging arrastraría 8 registros duplicados,
3 puntajes crediticios imposibles (999) y cero trazabilidad. Los modelos de la
Unidad 3 entrenarían sobre datos corruptos sin que nadie se entere, porque ningún
paso reporta lo que hizo. La versión del repo no es "más complicada por gusto":
cada extra (dedup, rangos, reportes) previene un fallo real de calidad de datos.

---

## Parte B1 — Extensión del módulo: detección de outliers por MAD

### Qué se agregó

Un tercer método de detección, **MAD (Median Absolute Deviation)**, en
[`src/cleaning.py`](../apps/analytics/src/cleaning.py):

- `DETECTION_METHODS` ahora es `("iqr", "zscore", "mad")` y se añadió la constante
  `MAD_SCALE = 1.4826`.
- `detect_outlier_mask(..., "mad")`: marca outlier si
  `|x − mediana| / (1.4826 · MAD) > 3`.
- `treat_outliers(..., method="mad", action="cap")`: acota con límites
  `mediana ± 3 · (1.4826 · MAD)`.
- Se extendió el **consumidor** `GET /api/cleaning/preview/outliers` para aceptar
  `method=mad` (regex `^(iqr|zscore|mad)$`), siguiendo el principio de "extender
  sin romper el contrato".
- Test propio en
  [`tests/test_cleaning_extension.py`](../apps/analytics/tests/test_cleaning_extension.py).
  **Los 5 tests heredados de `test_cleaning.py` siguen en verde** (30/30 en total).

### Por qué MAD — el efecto *masking*

El propio test heredado documenta que, en el frame sucio, **Z-score NO detecta el
ingreso de 500 000** (`detect_outlier_mask(..., "zscore").sum() == 0`). La razón es
el *masking*: un único valor extremo infla tanto la media y la desviación estándar
que el umbral `media ± 3σ` se agranda y el propio outlier queda "dentro". Z-score
asume una distribución aproximadamente normal y se auto-sabotea con colas pesadas.

**MAD usa la mediana y la desviación absoluta mediana**, estimadores con punto de
ruptura del 50 %: no se dejan arrastrar por valores extremos. Por eso MAD **sí**
captura ese outlier que Z-score enmascara, manteniendo la interpretación de "a
cuántas desviaciones típicas está" gracias al factor de escala 1.4826.

Mi test `test_mad_detecta_outlier_que_zscore_enmascara` lo demuestra sobre un caso
mínimo (ingresos ~30 k con un único 500 k): `zscore → 0` detectados, `mad → ≥ 1`.
También se cubre el caso borde de columna constante (MAD escalada = 0 → sin
outliers, sin excepción).

### Comparación de criterios de detección (sobre `annual_income` crudo)

| Método  | Idea                              | Robusto al masking |
| ------- | --------------------------------- | ------------------ |
| IQR     | Fuera de `[Q1−1.5·IQR, Q3+1.5·IQR]` | Sí                 |
| Z-score | `|z| > 3` con media y σ            | **No**             |
| MAD     | `|x−mediana| / (1.4826·MAD) > 3`   | **Sí**             |

---

## Reproducir

```bash
docker compose up -d --build postgres_db analytics
docker compose exec analytics python scripts/seed_synthetic.py --n 2000   # si la tabla está vacía
docker compose exec analytics python -m src.cleaning                      # pipeline del repo -> customer_credit_clean
docker compose exec analytics python scripts/cleaning_jaengarcia.py       # Parte A -> customer_credit_clean_jaengarcia
docker compose exec analytics pytest -q tests/                            # 30 passed
```
