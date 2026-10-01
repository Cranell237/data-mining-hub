-- =====================================================================
-- Taller en Clase U2-T1 · Actividad Guiada en Parejas (pág. 17 del PDF)
-- Consultas SQL de referencia para los RETOS 1, 2 y 3.
-- Base de datos: enterprise_warehouse  ·  Tabla: customer_credit_transactions
-- =====================================================================

-- ---------------------------------------------------------------------
-- RETO 1 · Conteo por Región
-- Agrupar clientes usando agregación SQL (GROUP BY region).
-- ---------------------------------------------------------------------
SELECT
    region,
    COUNT(*) AS total_clientes
FROM customer_credit_transactions
GROUP BY region
ORDER BY total_clientes DESC;


-- ---------------------------------------------------------------------
-- RETO 2 · Perfil de Riesgo
-- Extraer únicamente clientes con puntaje crítico: credit_score < 650.
-- ---------------------------------------------------------------------
SELECT
    customer_id,
    credit_score,
    region,
    has_defaulted
FROM customer_credit_transactions
WHERE credit_score < 650
ORDER BY credit_score ASC;


-- ---------------------------------------------------------------------
-- RETO 3 · Filtro y Orden
-- Filtrar clientes de Costa ordenados descendentemente por ingreso anual.
-- ---------------------------------------------------------------------
SELECT
    customer_id,
    region,
    annual_income,
    credit_score
FROM customer_credit_transactions
WHERE region = 'Costa'
ORDER BY annual_income DESC;
