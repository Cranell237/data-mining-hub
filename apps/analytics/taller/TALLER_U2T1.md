# Taller U2-T1 · Extracción y Conexión a Fuentes de Datos

Resolución de la **Actividad Guiada en Parejas (pág. 17)** y las **Preguntas
Formativas de Cierre (pág. 18)** de la sesión *U2-T1 — Extracción y Conexión a
Fuentes de Datos* (PostgreSQL 16 + Docker + SQLAlchemy + Pandas).

- **Base de datos:** `enterprise_warehouse`
- **Tabla:** `customer_credit_transactions`
- **Entorno:** contenedores `dm_postgres` (PostgreSQL 16) y `dm_analytics` (Python 3.11)

---

## 1. Qué se hizo

### Página 17 — Taller en parejas (4 RETOS)

| Reto | Objetivo | Técnica |
|------|----------|---------|
| **RETO 1** — Conteo por Región | Agrupar clientes por región | Agregación SQL `GROUP BY` |
| **RETO 2** — Perfil de Riesgo | Extraer clientes con `credit_score < 650` | Filtro `WHERE` |
| **RETO 3** — Filtro y Orden | Clientes de `Costa` ordenados por ingreso anual (desc) | `WHERE` + `ORDER BY ... DESC` |
| **RETO 4** — Reconstrucción | Consolidar 3 chunks con `pd.concat()` y validar los 9 registros | Chunking + `pd.concat` |

Se resolvió por **dos vías equivalentes**:

1. **SQL puro** → [`retos.sql`](retos.sql) (RETOS 1–3), ejecutable con `psql`.
2. **Python + Pandas** → [`solucion_taller.py`](solucion_taller.py) (RETOS 1–4),
   reutilizando `extract_raw_data` y `extract_raw_data_in_chunks` de
   [`src/db_connector.py`](../src/db_connector.py).

### Página 18 — Evaluación continua (4 preguntas)

Respuestas argumentadas en la [sección 5](#5-evaluación-continua-página-18).

### Ajuste del entorno (importante)

El RETO 4 exige **validar los 9 registros** y la demo del PDF muestra
`chunk_size=3 → 3 lotes de 3 = 9`. El seed original ([`init-db/01_init.sql`](../../../init-db/01_init.sql))
solo traía **8 filas**, por lo que se añadió un noveno registro para que el
entorno coincida exactamente con el material del curso:

```sql
('CUST-1009', 38, 28500.00, 630, 9500.00, FALSE, 'Costa')
```

Este registro se agregó tanto al script de inicialización como a la base de
datos en ejecución. Si se recrea el volumen desde cero, el seed ya incluye
los 9 registros.

---

## 2. Cómo reproducir (paso a paso)

Desde la raíz del repositorio, con Docker Desktop abierto.

### Paso 0 — Levantar el entorno

```bash
docker compose up -d
```

Verificar que ambos contenedores estén `Up`:

```bash
docker compose ps
```

> Si es la primera vez o recreaste el volumen `pg_data`, el seed con los 9
> registros se carga automáticamente. Si el volumen ya existía con 8 filas,
> inserta el registro faltante una sola vez:
>
> ```bash
> docker compose exec postgres_db psql -U dm_user -d enterprise_warehouse -c "INSERT INTO customer_credit_transactions (customer_id, age, annual_income, credit_score, loan_amount, has_defaulted, region) SELECT 'CUST-1009', 38, 28500.00, 630, 9500.00, FALSE, 'Costa' WHERE NOT EXISTS (SELECT 1 FROM customer_credit_transactions WHERE customer_id='CUST-1009');"
> ```

### Paso 1 — Ejecutar los 4 RETOS con Python (recomendado)

```bash
docker compose exec analytics python taller/solucion_taller.py
```

### Paso 2 — (Alternativa) Ejecutar los RETOS 1–3 con SQL puro

```bash
docker compose exec -T postgres_db psql -U dm_user -d enterprise_warehouse < apps/analytics/taller/retos.sql
```

### Paso 3 — (Opcional) Ejecutar un reto suelto de forma interactiva

```bash
docker compose exec analytics python -c "from taller.solucion_taller import reto_1_conteo_por_region; reto_1_conteo_por_region()"
```

---

## 3. Consultas utilizadas (copia)

### RETO 1 — Conteo por Región

```sql
SELECT region, COUNT(*) AS total_clientes
FROM customer_credit_transactions
GROUP BY region
ORDER BY total_clientes DESC;
```

### RETO 2 — Perfil de Riesgo (`credit_score < 650`)

```sql
SELECT customer_id, credit_score, region, has_defaulted
FROM customer_credit_transactions
WHERE credit_score < 650
ORDER BY credit_score ASC;
```

### RETO 3 — Filtro y Orden (Costa por ingreso, desc)

```sql
SELECT customer_id, region, annual_income, credit_score
FROM customer_credit_transactions
WHERE region = 'Costa'
ORDER BY annual_income DESC;
```

### RETO 4 — Reconstrucción por chunks (Python)

```python
import pandas as pd
from src.db_connector import extract_raw_data_in_chunks

query = "SELECT * FROM customer_credit_transactions ORDER BY transaction_id"
partes = []
for idx, chunk in enumerate(extract_raw_data_in_chunks(query, chunk_size=3)):
    print(f"Lote #{idx} recibido: {len(chunk)} registros en memoria")
    partes.append(chunk)

df_completo = pd.concat(partes, ignore_index=True)
assert len(df_completo) == 9  # validación de los 9 registros
```

---

## 4. Resultados obtenidos

### RETO 1 · Conteo por Región

| region  | total_clientes |
|---------|----------------|
| Costa   | 5 |
| Sierra  | 2 |
| Oriente | 1 |
| Insular | 1 |

### RETO 2 · Perfil de Riesgo (`credit_score < 650`) → 4 clientes

| customer_id | credit_score | region  | has_defaulted |
|-------------|--------------|---------|---------------|
| CUST-1003   | 520 | Costa   | true  |
| CUST-1006   | 580 | Costa   | true  |
| CUST-1004   | 615 | Oriente | false |
| CUST-1009   | 630 | Costa   | false |

### RETO 3 · Filtro y Orden (Costa, ingreso DESC) → 5 clientes

| customer_id | region | annual_income | credit_score |
|-------------|--------|---------------|--------------|
| CUST-1007   | Costa | 62000.00 | 740 |
| CUST-1001   | Costa | 45000.00 | 710 |
| CUST-1009   | Costa | 28500.00 | 630 |
| CUST-1006   | Costa | 18500.00 | 580 |
| CUST-1003   | Costa | 15000.00 | 520 |

### RETO 4 · Reconstrucción

```
Lote #0 recibido: 3 registros en memoria
Lote #1 recibido: 3 registros en memoria
Lote #2 recibido: 3 registros en memoria
Registros consolidados: 9
Validación OK: se reconstruyeron los 9 registros correctamente.
```

### Pregunta de debate (pág. 17)

> **¿Qué cambios de arquitectura aplicarías si la tabla tuviera 10 millones de filas?**

- **Extracción por lotes (chunking) obligatoria** con `chunksize`, en lugar de
  `read_sql_query` completo, para mantener memoria constante y evitar *Out-Of-Memory*.
- **Filtrar y agregar en el motor** (empujar `WHERE`, `GROUP BY`, `LIMIT` al SQL)
  para no traer filas innecesarias a Python.
- **Índices** sobre las columnas de filtro/orden (`region`, `credit_score`,
  `annual_income`) para acelerar las consultas.
- **Paralelización / particionado** por claves (p. ej. por `region` o rangos de
  `transaction_id`) y, si aplica, lectura por *server-side cursor*.
- **Materializar resultados** intermedios (tablas resumen o vistas materializadas)
  y considerar formatos columnares (Parquet) para el consumo analítico posterior.
- **Ajuste del pool** (`pool_size`, `max_overflow`) y *timeouts* acordes a la
  concurrencia del pipeline ETL.

---

## 5. Evaluación continua (página 18)

### Pregunta 1 — ¿Qué componentes cambian en la URL si el motor pasa a ser MySQL?

Partiendo de la cadena RFC 3986:
`postgresql+psycopg2://dm_user:dm_password@postgres_db:5432/enterprise_warehouse`

- **Dialecto:** `postgresql` → `mysql`.
- **Driver (DBAPI):** `psycopg2` → `pymysql` (o `mysqlclient`), quedando
  `mysql+pymysql`.
- **Puerto estándar:** `5432` (PostgreSQL) → `3306` (MySQL).

Las **credenciales**, el **host** y el **nombre de la base** conservan su
posición; solo cambia el prefijo `dialecto+driver` y el puerto por defecto:
`mysql+pymysql://usuario:clave@host:3306/base`.

### Pregunta 2 — ¿Por qué en aplicaciones multiusuario `pool_size` debe ser mayor a 1?

Porque en un entorno multiusuario hay **múltiples hilos/solicitudes concurrentes**.
Con `pool_size = 1` solo existiría una conexión reutilizable: las peticiones se
**serializarían**, cada cliente tendría que esperar a que se libere la única
conexión, aumentando la latencia y creando un cuello de botella. Un `pool_size`
mayor a 1 mantiene **varias conexiones vivas** listas para atender consultas en
paralelo, y `max_overflow` permite absorber picos de demanda sin abrir/cerrar
sockets constantemente.

### Pregunta 3 — ¿Dónde NUNCA debe almacenarse la contraseña de la base de datos?

**Nunca en texto plano dentro del código fuente ni en lo que llega al
repositorio Git:** ni "quemada" en constantes/variables del script, ni en
*docstrings* o comentarios, ni en archivos versionados. Tampoco en el historial
de *commits*. Debe vivir en **variables de entorno** (`.env` inyectado por
Docker Compose, ignorado con `.gitignore`) o en un gestor de secretos, siguiendo
el principio *12-Factor App*. Concatenarla o exponerla en logs/URLs también es un
riesgo.

### Pregunta 4 — ¿La técnica de chunking hace la extracción más rápida? ¿Por qué?

**No necesariamente; su objetivo no es la velocidad sino el control de memoria.**
El chunking optimiza el **consumo de RAM**: procesa un lote, lo libera y pide el
siguiente (generador perezoso con `yield`), evitando cargar millones de filas a
la vez. La **latencia de I/O de red** frente a la base de datos sigue siendo la
misma —incluso puede haber una ligera sobrecarga por múltiples viajes—. Como dice
la analogía del PDF: *"Chunking protege la memoria; no acelera la red"* — es como
leer un libro página por página en vez de fotocopiar las 500 páginas de golpe.

---

## 6. Archivos de esta entrega

| Archivo | Contenido |
|---------|-----------|
| [`solucion_taller.py`](solucion_taller.py) | Script Python con los 4 RETOS ejecutables |
| [`retos.sql`](retos.sql) | Consultas SQL puras de los RETOS 1–3 |
| [`TALLER_U2T1.md`](TALLER_U2T1.md) | Este documento (guía + respuestas) |
| [`init-db/01_init.sql`](../../../init-db/01_init.sql) | Seed actualizado a 9 registros |
