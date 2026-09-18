-- Repara las vigencias que quedaron selladas con la fecha de ingesta.
--
-- El publicador usaba la fecha de observación como inicio de `valid_during`,
-- de modo que cada entidad afirmaba haber nacido el día en que se descargó su
-- fuente. El efecto visible era que una consulta `as_of` anterior a la última
-- ingesta devolvía un Estado casi vacío: al 1 de enero de 2026 sólo existían
-- 21 de 243 nodos.
--
-- La fecha de creación real no está en las fuentes ya capturadas, así que el
-- rango queda abierto por abajo: no afirmar nada es correcto, afirmar el día
-- del scrapeo no lo es. `recorded_at` conserva cuándo lo supo el sistema.
--
-- Criterio: sólo se tocan las filas cuyo inicio de vigencia coincide
-- exactamente con su fecha de registro, que es la huella del error. Las filas
-- con fechas reales (1917 para los poderes, nacimientos, tomas de protesta)
-- no cumplen esa condición y quedan intactas.

BEGIN;

UPDATE nodes
SET valid_during = daterange(NULL, upper(valid_during), '[)')
WHERE lower(valid_during) = date(recorded_at);

UPDATE relationships
SET valid_during = daterange(NULL, upper(valid_during), '[)')
WHERE lower(valid_during) = date(recorded_at);

COMMIT;
