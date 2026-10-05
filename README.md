# Data Mining Hub

Plataforma contenerizada de **Minería de Datos** (UPSE · FACSISTEL · Séptimo Semestre)
que acompaña la metodología **CRISP-DM** sobre un *enterprise warehouse* de riesgo
crediticio. El proyecto integra un almacén PostgreSQL, un backend analítico en Python
(extracción, EDA, limpieza y una API REST) y un frontend React para explorar los datos.

> Repositorio de trabajo del estudiante, derivado del repositorio base de la asignatura
> (`software-cemm/mineria`). Ver [Créditos y sincronización](#créditos-y-sincronización).

---

## Arquitectura

Monorepo con ejecución 100 % contenerizada vía Docker Compose:

```
data-mining-hub/
├── apps/
│   ├── analytics/            # Backend analítico (Python 3.11)
│   │   ├── src/
│   │   │   ├── db_connector.py   # Conexión y extracción (SQLAlchemy + pooling)
│   │   │   ├── pipeline.py       # Preprocesamiento base (Iris, scaling)
│   │   │   ├── eda.py            # Análisis Exploratorio (U2-T2)
│   │   │   ├── cleaning.py       # Limpieza y calidad de datos (U2-T3)  ← esta práctica
│   │   │   └── api.py            # API REST FastAPI
│   │   ├── scripts/
│   │   │   └── seed_synthetic.py # Generador de datos sintéticos "sucios"
│   │   ├── taller/               # Taller en clase U2-T1
│   │   └── tests/                # Suite pytest
│   └── web/                  # Frontend React + Vite (dashboard, EDA, laboratorio)
├── init-db/
│   └── 01_init.sql           # DDL + seed inicial de customer_credit_transactions
├── packages/                 # Código compartido
└── docker-compose.yml        # Orquestación: postgres_db + analytics + web
```

### Servicios

| Servicio      | Contenedor     | Puerto (host)        | Descripción                              |
|---------------|----------------|----------------------|------------------------------------------|
| `postgres_db` | `dm_postgres`  | `127.0.0.1:5437`     | PostgreSQL 16 (`enterprise_warehouse`)   |
| `analytics`   | `dm_analytics` | `127.0.0.1:8000`     | API FastAPI (uvicorn) + backend Python   |
| `web`         | `dm_web`       | `127.0.0.1:5173`     | Frontend React + Vite                    |

---

## Requisitos

- Docker y Docker Compose v2.

## Puesta en marcha

```bash
# Levantar toda la plataforma (postgres + analytics + web)
docker compose up -d --build

# O solo el backend analítico (suficiente para esta práctica)
docker compose up -d --build postgres_db analytics
```

- API: http://localhost:8000 — documentación interactiva en http://localhost:8000/docs
- Frontend: http://localhost:5173

### Variables de entorno

Dentro de Docker, `docker-compose.yml` inyecta automáticamente `DB_URL`. Para ejecutar
Python **fuera** del contenedor, copia `apps/analytics/.env.example` a `.env` y ajusta la
URL (ver el ejemplo). Las credenciales **no** se escriben en el código fuente.

---

## Base de datos

Tabla cruda `customer_credit_transactions` (sembrada por `init-db/01_init.sql`):

| Columna          | Tipo            | Notas                                  |
|------------------|-----------------|----------------------------------------|
| `transaction_id` | SERIAL PK       | Clave primaria                         |
| `customer_id`    | VARCHAR(15)     | Identificador de cliente               |
| `age`            | INT             | Edad (regla de negocio: 18–100)        |
| `annual_income`  | NUMERIC(12,2)   | Ingreso anual                          |
| `credit_score`   | INT             | Puntaje crediticio (300–850)           |
| `loan_amount`    | NUMERIC(12,2)   | Monto del préstamo                     |
| `has_defaulted`  | BOOLEAN         | Incumplimiento                         |
| `region`         | VARCHAR(50)     | Costa / Sierra / Oriente / Insular     |
| `created_at`     | TIMESTAMP       | Fecha de alta                          |

### Datos sintéticos (para EDA y limpieza)

El script `scripts/seed_synthetic.py` agrega registros realistas e **inyecta defectos
deliberados** (nulos, outliers imposibles, categorías inconsistentes y duplicados) para
dar material a las prácticas. Es reejecutable (hace `append`):

```bash
docker compose exec analytics python scripts/seed_synthetic.py --n 2000
```

---

## Práctica U2·T3 — Limpieza y Calidad de Datos (CRISP-DM Fase 3)

Módulo [`apps/analytics/src/cleaning.py`](apps/analytics/src/cleaning.py): pipeline
algorítmico para tratar la **Tríada Patológica de Datos**.

| Actividad | Función                      | Qué hace                                                                 |
|-----------|------------------------------|--------------------------------------------------------------------------|
| 3.1       | `normalize_inconsistencies`  | `region` → `strip` + *Title Case*; `age`/`credit_score` fuera de rango → `NaN` |
| 3.2       | `impute_column`              | Imputación `mean` / `median` / `mode` / `knn` (`KNNImputer`)             |
| 3.3       | `handle_outliers`            | Detección IQR o regla empírica (μ ± 3σ) + **capping** (preserva filas)   |
| Sección 4 | `run_cleaning_pipeline`      | Orquesta dedup → normalización → imputación → capping → persiste          |

El pipeline lee `customer_credit_transactions`, limpia y guarda el resultado en la tabla
**`customer_credit_clean`**.

### Ejecutar el pipeline

```bash
# 1. Poblar la tabla con datos "sucios"
docker compose exec analytics python scripts/seed_synthetic.py --n 2000

# 2. Ejecutar el pipeline de limpieza + reporte de auditoría
docker compose exec analytics python -m src.cleaning

# 3. Verificar la tabla limpia resultante
docker exec dm_postgres psql -U dm_user -d enterprise_warehouse \
  -c "SELECT COUNT(*) FROM customer_credit_clean;"
```

### Pruebas

```bash
# Toda la suite
docker compose exec analytics pytest -v tests/

# Solo la práctica U2-T3
docker compose exec analytics pytest -v tests/test_cleaning.py
```

---

## Entregables U2·T3

### 1. Auditoría de Calidad (reporte por consola)

Salida real de `python -m src.cleaning` sobre 2000 registros sintéticos:

```
======================================================================
PIPELINE DE LIMPIEZA · customer_credit_transactions
======================================================================
  Registros crudos   : 2017
  Registros limpios  : 2009 (deduplicados)
  Nulos antes        : 144
  Nulos después      : 0

======================================================================
AUDITORÍA DE CALIDAD · Varianza de 'annual_income'
======================================================================
  Varianza ANTES  (crudo)  : 710,911,718.21
  Varianza DESPUÉS (limpio): 283,972,302.61
  Reducción de varianza    : 60.06%
======================================================================
```

La varianza de `annual_income` se reduce ~60 % tras el tratamiento, confirmando que el
capping y la imputación estabilizan la dispersión sin descartar registros.

### 2. Reflexión — ¿por qué *capping* en lugar de eliminar los atípicos?

En el contexto de **riesgo crediticio**, eliminar directamente los registros atípicos sería
contraproducente: los clientes con ingresos o montos de préstamo extremos no son "ruido", sino
precisamente el segmento donde la exposición al riesgo es mayor y más informativa para el
modelo. Borrarlos reduciría el tamaño muestral —debilitando el poder estadístico— e
introduciría un **sesgo de supervivencia** que haría al modelo ciego ante los casos límite que
más importa predecir (p. ej., grandes incumplimientos). El **acotamiento (capping)** conserva
el 100 % de las observaciones y, a la vez, neutraliza el efecto desproporcionado de los valores
extremos sobre medias y varianzas, preservando las relaciones lineales que aprenderán los
algoritmos de la fase de Machine Learning. Así se mantiene la integridad del dataset y la
representatividad de toda la cartera de clientes.

---

## Créditos y sincronización

Este repositorio parte del repositorio base de la asignatura
[`software-cemm/mineria`](https://github.com/software-cemm/mineria) (práctica docente de
**Ing. Carlos Eduardo Muñoz Mendoza**), configurado como remoto `upstream` de solo lectura.
La infraestructura, el conector de base de datos, el módulo EDA, la API y el frontend
provienen de esa base (hasta U2-T2); el **Taller U2-T1** (`apps/analytics/taller/`) y la
**práctica U2-T3** (`apps/analytics/src/cleaning.py`) son desarrollo propio del estudiante.
